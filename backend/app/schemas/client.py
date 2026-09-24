"""
Client schemas
"""
from pydantic import BaseModel, EmailStr, Field, model_validator

CONTACT_REQUIRED = "Add a phone number or an email so the client can be reached."


class ClientCreate(BaseModel):
    """Create client"""
    name: str = Field(..., max_length=100)
    phone_number: str | None = Field(default=None, max_length=20)
    email: EmailStr | None = None
    address: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def require_a_way_to_reach_them(self) -> "ClientCreate":
        """
        One contact method, either one. Phone alone was mandatory for a while so the
        crew always had a number on the job card, but that walls off an estimate for a
        prospect who has only ever given an email. No format rule on the phone -
        extensions and site offices all have to survive.
        """
        if not (self.phone_number or "").strip() and not self.email:
            raise ValueError(CONTACT_REQUIRED)
        return self


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
    phone_number: str | None = None
    address: str

    class Config:
        from_attributes = True
