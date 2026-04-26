"""
API routes
"""
from . import auth, workers, clients, jobs, timesheets, invoices, purchases, inspections

__all__ = [
    "auth",
    "workers",
    "clients",
    "jobs",
    "timesheets",
    "invoices",
    "purchases",
    "inspections",
]
