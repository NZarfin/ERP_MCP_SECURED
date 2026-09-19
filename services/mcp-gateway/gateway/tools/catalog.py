"""catalog.create_product as an MCP tool. Single-phase, same reasoning as
parties.create_customer.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.modules.catalog.commands.create_product import CreateProduct, CreateProductInput
from mcp.server.mcpserver import Context, MCPServer
from mcp_types import ToolAnnotations

from ..registry import call_command_tool, register_tool_sku

SKU = "core.catalog"


def register(server: MCPServer[Any]) -> None:
    @server.tool(
        name="catalog.create_product",
        description="Create a product in this tenant's catalog.",
        annotations=ToolAnnotations(
            title="Create product",
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
        ),
    )
    async def create_product(
        ctx: Context,
        sku: str,
        name: str,
        unit: str,
        base_price: Decimal,
        currency: str = "EUR",
    ) -> dict[str, Any]:
        input_ = CreateProductInput(
            sku=sku, name=name, unit=unit, base_price=base_price, currency=currency
        )
        return await call_command_tool(
            ctx, CreateProduct, input_, required_scope="catalog:write", sku=SKU
        )

    register_tool_sku("catalog.create_product", SKU)
