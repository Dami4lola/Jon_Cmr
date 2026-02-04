"""
Pydantic schemas for API request/response validation
"""
from .auth import Token, TokenData, LoginRequest, RegisterRequest, UserResponse
from .worker import WorkerCreate, WorkerUpdate, WorkerResponse
from .client import ClientCreate, ClientUpdate, ClientResponse, ClientBrief
from .job import JobCreate, JobUpdate, JobResponse, JobBrief, CalendarEvent
from .timesheet import TimesheetCreate, TimesheetUpdate, TimesheetResponse
from .invoice import InvoiceCreate, InvoiceResponse, InvoiceStatusUpdate
from .purchase import PurchaseItemCreate, PurchaseItemResponse
from .inspection import (
    InspectionCreate,
    InspectionUpdate,
    InspectionResponse,
    InspectionPhotoResponse,
)

__all__ = [
    "Token",
    "TokenData",
    "LoginRequest",
    "RegisterRequest",
    "UserResponse",
    "WorkerCreate",
    "WorkerUpdate",
    "WorkerResponse",
    "ClientCreate",
    "ClientUpdate",
    "ClientResponse",
    "ClientBrief",
    "JobCreate",
    "JobUpdate",
    "JobResponse",
    "JobBrief",
    "CalendarEvent",
    "TimesheetCreate",
    "TimesheetUpdate",
    "TimesheetResponse",
    "InvoiceCreate",
    "InvoiceResponse",
    "InvoiceStatusUpdate",
    "PurchaseItemCreate",
    "PurchaseItemResponse",
    "InspectionCreate",
    "InspectionUpdate",
    "InspectionResponse",
    "InspectionPhotoResponse",
]
