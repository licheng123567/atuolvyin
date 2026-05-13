"""Sprint 16.2 — 律所池 schema (PRD §20.4)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class LawFirmLawyerOut(BaseModel):
    id: int
    law_firm_id: int
    name: str
    license_no: str | None
    phone: str | None
    specialties: list[str] | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LawFirmOut(BaseModel):
    id: int
    name: str
    license_no: str | None
    region: str | None
    contact_name: str | None
    contact_phone: str | None
    address: str | None
    specialties: list[str] | None
    enabled: bool
    accepting_orders: bool
    rating_avg: Decimal
    completed_orders: int
    notes: str | None
    created_at: datetime
    updated_at: datetime
    lawyers: list[LawFirmLawyerOut] = []

    model_config = {"from_attributes": True}


class LawFirmCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    license_no: str | None = Field(None, max_length=64)
    region: str | None = Field(None, max_length=64)
    contact_name: str | None = Field(None, max_length=120)
    contact_phone: str | None = Field(None, max_length=32)
    address: str | None = Field(None, max_length=300)
    specialties: list[str] | None = None
    notes: str | None = Field(None, max_length=2000)


class LawFirmPatch(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=200)
    license_no: str | None = Field(None, max_length=64)
    region: str | None = Field(None, max_length=64)
    contact_name: str | None = Field(None, max_length=120)
    contact_phone: str | None = Field(None, max_length=32)
    address: str | None = Field(None, max_length=300)
    specialties: list[str] | None = None
    enabled: bool | None = None
    accepting_orders: bool | None = None
    notes: str | None = Field(None, max_length=2000)


class LawyerCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    license_no: str | None = Field(None, max_length=64)
    phone: str | None = Field(None, max_length=32)
    specialties: list[str] | None = None


class LawyerPatch(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=120)
    license_no: str | None = Field(None, max_length=64)
    phone: str | None = Field(None, max_length=32)
    specialties: list[str] | None = None
    is_active: bool | None = None
