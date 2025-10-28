from __future__ import annotations

from datetime import datetime, timezone
from statistics import mean
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.database import get_session
from app.dependencies import ensure_machine_ownership, get_current_user
from app.models import Machine, MachineConfiguration, MonitoringData, User
from app.schemas import (
    LoginRequest,
    MachineConfigPayload,
    MachineConfigResponse,
    MachineCreate,
    MachineRead,
    MetricPayload,
    MetricsAggregate,
    MonitoringDataRead,
    Token,
    UserCreate,
    UserRead,
)
from app.security import create_access_token, get_password_hash, verify_password

settings = get_settings()
router = APIRouter(prefix=settings.api_prefix)


@router.get("/health", tags=["status"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/register", response_model=UserRead, tags=["auth"])
async def register_user(user_in: UserCreate, session: AsyncSession = Depends(get_session)) -> UserRead:
    existing_user = await session.scalar(select(User).where(User.email == user_in.email))
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    user = User(email=user_in.email, full_name=user_in.full_name, hashed_password=get_password_hash(user_in.password))
    session.add(user)
    await session.commit()
    await session.refresh(user)
    logger.info("Registered new user {email}", email=user.email)
    return UserRead.model_validate(user)


async def _get_or_create_machine(
    *,
    session: AsyncSession,
    user: User,
    mac_address: str,
    name: str,
    machine_type: str,
) -> Machine:
    machine = await session.scalar(select(Machine).where(Machine.mac_address == mac_address))
    if machine:
        if machine.owner_id != user.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Machine belongs to another user")
        updated = False
        if machine.name != name:
            machine.name = name
            updated = True
        if machine.type != machine_type:
            machine.type = machine_type
            updated = True
        if updated:
            await session.commit()
            await session.refresh(machine)
        return machine

    machine = Machine(mac_address=mac_address, name=name, type=machine_type, owner=user)
    session.add(machine)
    await session.commit()
    await session.refresh(machine)
    return machine


@router.post("/login", response_model=Token, tags=["auth"])
async def login(request: LoginRequest, session: AsyncSession = Depends(get_session)) -> Token:
    user = await session.scalar(select(User).where(User.email == request.email))
    if user is None or not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    machine_type = "server" if "server" in request.c.lower() else "pc"
    machine = await _get_or_create_machine(
        session=session,
        user=user,
        mac_address=request.mac_address,
        name=request.username,
        machine_type=machine_type,
    )

    token = create_access_token(
        subject=user.email,
        machine_mac=machine.mac_address,
        machine_type=machine.type,
        user_id=user.id,
    )
    logger.info(
        "User {email} authenticated machine {mac} ({type})",
        email=user.email,
        mac=machine.mac_address,
        type=machine.type,
    )
    return Token(token=token, type=machine.type)


@router.post("/machines", response_model=MachineRead, tags=["machines"])
async def register_machine(
    machine_in: MachineCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MachineRead:
    machine = await _get_or_create_machine(
        session=session,
        user=current_user,
        mac_address=machine_in.mac_address,
        name=machine_in.name or machine_in.mac_address,
        machine_type=machine_in.type,
    )
    return MachineRead.model_validate(machine)


@router.get("/machines", response_model=list[MachineRead], tags=["machines"])
async def list_machines(
    current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> list[MachineRead]:
    result = await session.scalars(select(Machine).where(Machine.owner_id == current_user.id))
    machines = result.all()
    return [MachineRead.model_validate(machine) for machine in machines]


class ConfigUpdateRequest(BaseModel):
    data: MachineConfigPayload


@router.post("/update_confg_maquina", tags=["config"])
async def update_machine_config(
    payload: ConfigUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    config_data = payload.data
    machine = await ensure_machine_ownership(config_data.mac, current_user, session)

    raw_payload = config_data.model_dump(by_alias=True)
    configuration = await session.scalar(
        select(MachineConfiguration).where(MachineConfiguration.machine_id == machine.id)
    )
    if configuration:
        configuration.raw_payload = raw_payload
    else:
        configuration = MachineConfiguration(machine=machine, raw_payload=raw_payload)
        session.add(configuration)

    await session.commit()
    await session.refresh(configuration)
    logger.info("Updated configuration for machine {mac}", mac=machine.mac_address)
    return {"status": "success", "data": configuration.raw_payload, "updated_at": configuration.updated_at}


@router.get("/machine/{mac}", response_model=MachineConfigResponse, tags=["config"])
async def get_machine_config(
    mac: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MachineConfigResponse:
    machine = await ensure_machine_ownership(mac, current_user, session)
    configuration = await session.scalar(
        select(MachineConfiguration).where(MachineConfiguration.machine_id == machine.id)
    )
    if configuration is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Configuration not found")
    return MachineConfigResponse(data=configuration.raw_payload, updated_at=configuration.updated_at)


@router.put("/maquina/status", tags=["metrics"])
async def update_machine_status(
    payload: MetricPayload,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    mac = payload.data.get("machine_info", {}).get("mac") or payload.data.get("mac_address")
    if not mac:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="MAC address missing in payload")

    machine = await ensure_machine_ownership(mac, current_user, session)

    timestamp_str = payload.data.get("timestamp")
    if isinstance(timestamp_str, str):
        timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
    else:
        timestamp = datetime.utcnow().replace(tzinfo=timezone.utc)

    metric_record = MonitoringData(machine=machine, timestamp=timestamp, metrics=payload.data)
    session.add(metric_record)
    await session.commit()
    await session.refresh(metric_record)

    logger.debug(
        "Stored monitoring data for machine {mac} at {timestamp}",
        mac=machine.mac_address,
        timestamp=metric_record.timestamp.isoformat(),
    )
    return {
        "status": "success",
        "reference_id": metric_record.reference_id,
        "timestamp": metric_record.timestamp,
    }


@router.get("/metrics/{mac}", response_model=list[MonitoringDataRead], tags=["metrics"])
async def list_machine_metrics(
    mac: str,
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    limit: int = Query(default=100, le=1000),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[MonitoringDataRead]:
    machine = await ensure_machine_ownership(mac, current_user, session)

    stmt = select(MonitoringData).where(MonitoringData.machine_id == machine.id).order_by(MonitoringData.timestamp.desc())
    if start:
        stmt = stmt.where(MonitoringData.timestamp >= start)
    if end:
        stmt = stmt.where(MonitoringData.timestamp <= end)
    stmt = stmt.limit(limit)

    result = await session.scalars(stmt)
    records = result.all()
    return [MonitoringDataRead.model_validate(record) for record in records]


@router.get("/metrics/{mac}/aggregate", response_model=list[MetricsAggregate], tags=["metrics"])
async def aggregate_metrics(
    mac: str,
    metric_keys: list[str] = Query(default=["cpu", "memory", "disk"]),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[MetricsAggregate]:
    machine = await ensure_machine_ownership(mac, current_user, session)
    result = await session.scalars(select(MonitoringData).where(MonitoringData.machine_id == machine.id))
    records = result.all()

    aggregates: list[MetricsAggregate] = []
    for key in metric_keys:
        values: list[float] = []
        for record in records:
            value = record.metrics.get(key)
            if isinstance(value, (int, float)):
                values.append(float(value))
            elif isinstance(value, dict):
                for candidate in ("usage", "percent", "value"):
                    nested = value.get(candidate)
                    if isinstance(nested, (int, float)):
                        values.append(float(nested))
                        break
        if not values:
            aggregates.append(MetricsAggregate(metric=key, minimum=None, maximum=None, average=None))
        else:
            aggregates.append(
                MetricsAggregate(
                    metric=key,
                    minimum=min(values),
                    maximum=max(values),
                    average=mean(values),
                )
            )
    return aggregates
