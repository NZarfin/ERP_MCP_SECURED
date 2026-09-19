"""Bearer token -> (tenant_id, scopes). See
services/core/app/modules/gateway/commands/create_access_token.py for the token
format (`"<tenant_id>.<secret>"`) and why it's shaped that way: the access_token
table is RLS-scoped, so verifying a token means a SELECT that itself needs
`app.tenant_id` set first -- the tenant id embedded in the token is what lets this
verifier set that scope *before* the lookup, so RLS is the actual enforcement
rather than the app needing a bypass role.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

from app.db.session import tenant_session
from app.modules.gateway.models.access_token import AccessToken as AccessTokenRow
from mcp.server.auth.provider import AccessToken, TokenVerifier
from sqlalchemy import select


class GatewayTokenVerifier(TokenVerifier):
    async def verify_token(self, token: str) -> AccessToken | None:
        tenant_id_str, sep, secret = token.partition(".")
        if not sep or not secret:
            return None
        try:
            tenant_id = uuid.UUID(tenant_id_str)
        except ValueError:
            return None

        token_hash = hashlib.sha256(token.encode()).hexdigest()

        async with tenant_session(tenant_id) as session:
            row = (
                await session.execute(
                    select(AccessTokenRow).where(
                        AccessTokenRow.token_hash == token_hash,
                        AccessTokenRow.revoked_at.is_(None),
                    )
                )
            ).scalar_one_or_none()
            if row is None:
                return None
            row.last_used_at = datetime.now(UTC)
            access_token_id = row.id
            scopes = list(row.scopes)

        return AccessToken(
            token=token,
            client_id=str(tenant_id),
            scopes=scopes,
            subject=str(access_token_id),
        )
