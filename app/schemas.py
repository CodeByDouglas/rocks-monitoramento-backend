from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class Message(BaseModel):
    message: str


class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None


class UserCreate(UserBase):
    password: str


class UserRead(UserBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    token: str
    type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    mac_address: str
    username: str
    c: str = Field(description="Operating system reported by the desktop agent")


class MachineCreate(BaseModel):
    mac_address: str
    name: Optional[str] = None
    type: str = "pc"


class MachineRead(BaseModel):
    id: int
    mac_address: str
    name: Optional[str]
    type: str

    model_config = ConfigDict(from_attributes=True)


class MachineConfigPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    name: str = Field(alias="Nome")
    mac: str = Field(alias="MAC")
    type: str = Field(alias="type")
    notify: bool = Field(alias="Notificar")
    frequency: int = Field(alias="Frequency")
    start_with_os: bool = Field(alias="iniciarSO")
    status: dict[str, Any]


class MachineConfigResponse(BaseModel):
    data: dict[str, Any]
    updated_at: datetime


class MetricPayload(BaseModel):
    data: dict[str, Any]


class MetricsQuery(BaseModel):
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    limit: int = 100


class MonitoringDataRead(BaseModel):
    timestamp: datetime
    metrics: dict[str, Any]
    reference_id: str

    model_config = ConfigDict(from_attributes=True)


class MetricsAggregate(BaseModel):
    metric: str
    minimum: float | None
    maximum: float | None
    average: float | None
