from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class CallDirection(StrEnum):
    inbound = "inbound"
    outbound = "outbound"


class SessionState(StrEnum):
    greeting = "greeting"
    collecting_details = "collecting_details"
    resolving = "resolving"
    escalated = "escalated"
    completed = "completed"


class Intent(StrEnum):
    appointment = "appointment"
    billing = "billing"
    support = "support"
    escalation = "escalation"
    goodbye = "goodbye"
    unknown = "unknown"


class SessionCreate(BaseModel):
    caller_id: str = Field(min_length=3, max_length=80)
    direction: CallDirection = CallDirection.inbound


class MessageCreate(BaseModel):
    text: str = Field(min_length=1, max_length=2_000)


class TranscriptEntry(BaseModel):
    role: str
    text: str
    created_at: datetime


class AuditEvent(BaseModel):
    event: str
    detail: str
    created_at: datetime


class SessionResponse(BaseModel):
    id: str
    caller_id: str
    direction: CallDirection
    state: SessionState
    intent: Intent
    slots: dict[str, str]
    transcript: list[TranscriptEntry]
    events: list[AuditEvent]
    created_at: datetime
    updated_at: datetime
