"""parties.create_customer / parties.create_supplier as MCP tools. Both are
single-phase (creating a party record isn't money/stock/document-affecting per
GUARDRAILS.md §3), so neither takes a mode/confirm_token argument.
"""

from __future__ import annotations

from typing import Any

from app.modules.parties.commands.create_customer import CreateCustomer, CreateCustomerInput
from app.modules.parties.commands.create_supplier import CreateSupplier, CreateSupplierInput
from mcp.server.mcpserver import Context, MCPServer
from mcp_types import ToolAnnotations

from ..registry import call_command_tool, register_tool_sku

SKU = "core.parties"


def register(server: MCPServer[Any]) -> None:
    @server.tool(
        name="parties.create_customer",
        description="Create a customer record for this tenant.",
        annotations=ToolAnnotations(
            title="Create customer",
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
        ),
    )
    async def create_customer(
        ctx: Context,
        name: str,
        email: str | None = None,
        vat_id: str | None = None,
    ) -> dict[str, Any]:
        input_ = CreateCustomerInput(name=name, email=email, vat_id=vat_id)
        return await call_command_tool(
            ctx, CreateCustomer, input_, required_scope="parties:write", sku=SKU
        )

    @server.tool(
        name="parties.create_supplier",
        description="Create a supplier record for this tenant.",
        annotations=ToolAnnotations(
            title="Create supplier",
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
        ),
    )
    async def create_supplier(
        ctx: Context,
        name: str,
        email: str | None = None,
        vat_id: str | None = None,
    ) -> dict[str, Any]:
        input_ = CreateSupplierInput(name=name, email=email, vat_id=vat_id)
        return await call_command_tool(
            ctx, CreateSupplier, input_, required_scope="parties:write", sku=SKU
        )

    register_tool_sku("parties.create_customer", SKU)
    register_tool_sku("parties.create_supplier", SKU)
