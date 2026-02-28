from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class ProviderCreate(BaseModel):
    name: str
    business_name: Optional[str] = None
    email: str
    phone: Optional[str] = None
    trade: str
    city: Optional[str] = None
    county: Optional[str] = None
    state: str = "VA"
    license_number: Optional[str] = None
    password: str


class ProviderLogin(BaseModel):
    email: str
    password: str


class DPORResult(BaseModel):
    success: bool
    license_number: str
    holder_name: Optional[str] = None
    license_class: Optional[str] = None
    status: Optional[str] = None
    expiration_date: Optional[str] = None
    initial_date: Optional[str] = None
    firm_type: Optional[str] = None
    specialties: Optional[str] = None
    address: Optional[str] = None
    error: Optional[str] = None
    raw_html: Optional[str] = None
