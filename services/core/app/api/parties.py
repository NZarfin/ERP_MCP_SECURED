"""Read endpoints backing the customer/supplier pickers in filter bars. Deliberately
thin: full parties CRUD + filtering is a REST API of its own later, not needed yet.
"""

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_db
from app.modules.parties.models.customer import Customer
from app.modules.parties.models.supplier import Supplier

router = APIRouter(prefix="/api/parties", tags=["parties"])


class PartySummary(BaseModel):
    id: uuid.UUID
    name: str


@router.get("/customers", response_model=list[PartySummary])
async def list_customers(session: AsyncSession = Depends(get_tenant_db)) -> list[PartySummary]:
    rows = (await session.execute(select(Customer.id, Customer.name).order_by(Customer.name))).all()
    return [PartySummary(id=row.id, name=row.name) for row in rows]


@router.get("/suppliers", response_model=list[PartySummary])
async def list_suppliers(session: AsyncSession = Depends(get_tenant_db)) -> list[PartySummary]:
    rows = (await session.execute(select(Supplier.id, Supplier.name).order_by(Supplier.name))).all()
    return [PartySummary(id=row.id, name=row.name) for row in rows]
