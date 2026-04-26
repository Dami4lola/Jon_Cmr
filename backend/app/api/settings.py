"""
Application settings API endpoints
"""
from fastapi import APIRouter
from pydantic import BaseModel

from ..models.settings import AppSettings
from .deps import DBSession, ManagerUser

router = APIRouter()


class InvoiceStartNumberUpdate(BaseModel):
    value: int


@router.get("/invoice-start-number")
def get_invoice_start_number(
    session: DBSession,
    current_user: ManagerUser,
):
    """Get the configured invoice starting number"""
    setting = session.get(AppSettings, "invoice_start_number")
    return {"value": int(setting.value) if setting else 1}


@router.put("/invoice-start-number")
def set_invoice_start_number(
    data: InvoiceStartNumberUpdate,
    session: DBSession,
    current_user: ManagerUser,
):
    """Set the minimum invoice starting number"""
    setting = session.get(AppSettings, "invoice_start_number")
    if setting:
        setting.value = str(data.value)
    else:
        setting = AppSettings(key="invoice_start_number", value=str(data.value))
    session.add(setting)
    session.commit()
    return {"value": int(setting.value)}
