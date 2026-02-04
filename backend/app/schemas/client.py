"""
Client schemas
"""
from pydantic import BaseModel, EmailStr, Field


class ClientCreate(BaseModel):
    """Create client"""
    name: str = Field(..., max_length=100)
    phone_number: str | None = Field(default=None, max_length=20)
    email: EmailStr | None = None
    address: str = Field(..., min_length=1)


class ClientUpdate(BaseModel):
    """Update client"""
    name: str | None = Field(default=None, max_length=100)
    phone_number: str | None = Field(default=None, max_length=20)
    email: EmailStr | None = None
    address: str | None = None


class ClientResponse(BaseModel):
    """Client response"""
    id: int
    name: str
    phone_number: str | None
    email: str | None
    address: str

    class Config:
        from_attributes = True


class ClientBrief(BaseModel):
    """Brief client info for nested responses"""
    id: int
    name: str
    address: str

    class Config:
        from_attributes = True
