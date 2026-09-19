"""Read endpoint backing the product picker."""

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_db
from app.core.money import from_minor_units
from app.modules.catalog.models.product import Product

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


class ProductSummary(BaseModel):
    id: uuid.UUID
    sku: str
    name: str
    unit: str
    base_price: Decimal
    currency: str


@router.get("/products", response_model=list[ProductSummary])
async def list_products(session: AsyncSession = Depends(get_tenant_db)) -> list[ProductSummary]:
    products = (
        (await session.execute(select(Product).where(Product.active).order_by(Product.name)))
        .scalars()
        .all()
    )
    return [
        ProductSummary(
            id=p.id,
            sku=p.sku,
            name=p.name,
            unit=p.unit,
            base_price=from_minor_units(p.base_price_amount),
            currency=p.base_price_currency,
        )
        for p in products
    ]
