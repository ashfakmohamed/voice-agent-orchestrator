import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import RLock
from typing import ClassVar
from uuid import uuid4

from app.models import (
    AuditEvent,
    CallDirection,
    Intent,
    SessionResponse,
    SessionState,
    TranscriptEntry,
)

APPOINTMENT_DATE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")
ACCOUNT_REFERENCE = re.compile(r"\b(ACC-\d{4,12})\b", re.IGNORECASE)


class IntentRouter:
    KEYWORDS: ClassVar[dict[Intent, tuple[str, ...]]] = {
        Intent.escalation: ("human", "agent", "representative", "supervisor"),
        Intent.appointment: ("appointment", "schedule", "booking", "reschedule"),
        Intent.billing: ("bill", "billing", "invoice", "payment", "refund"),
        Intent.support: ("help", "support", "broken", "issue", "problem", "error"),
        Intent.goodbye: ("goodbye", "bye", "that is all", "thanks, bye"),
    }

    def classify(self, text: str) -> Intent:
        normalized = text.lower()
        for intent, keywords in self.KEYWORDS.items():
            if any(keyword in normalized for keyword in keywords):
                return intent
        return Intent.unknown


@dataclass
class VoiceSession:
    id: str
    caller_id: str
    direction: CallDirection
    state: SessionState
    intent: Intent
    created_at: datetime
    updated_at: datetime
    slots: dict[str, str] = field(default_factory=dict)
    transcript: list[TranscriptEntry] = field(default_factory=list)
    events: list[AuditEvent] = field(default_factory=list)

    def response(self) -> SessionResponse:
        return SessionResponse(
            id=self.id,
            caller_id=self.caller_id,
            direction=self.direction,
            state=self.state,
            intent=self.intent,
            slots=dict(self.slots),
            transcript=list(self.transcript),
            events=list(self.events),
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


class VoiceOrchestrator:
    def __init__(self) -> None:
        self._sessions: dict[str, VoiceSession] = {}
        self._router = IntentRouter()
        self._lock = RLock()

    def create(self, caller_id: str, direction: CallDirection) -> SessionResponse:
        now = datetime.now(UTC)
        session = VoiceSession(
            id=str(uuid4()),
            caller_id=caller_id,
            direction=direction,
            state=SessionState.greeting,
            intent=Intent.unknown,
            created_at=now,
            updated_at=now,
        )
        self._append_assistant(session, "Hello. How can I help you today?")
        self._event(session, "session.created", f"{direction.value} call created")
        with self._lock:
            self._sessions[session.id] = session
        return session.response()

    def get(self, session_id: str) -> SessionResponse | None:
        with self._lock:
            session = self._sessions.get(session_id)
            return session.response() if session else None

    def handle_message(self, session_id: str, text: str) -> SessionResponse | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            if session.state in {SessionState.completed, SessionState.escalated}:
                return session.response()

            self._append_user(session, text)
            detected_intent = self._router.classify(text)
            intent = (
                session.intent
                if detected_intent is Intent.unknown and session.intent is not Intent.unknown
                else detected_intent
            )
            session.intent = intent
            self._collect_slots(session, text)
            response_text = self._transition(session, intent)
            self._append_assistant(session, response_text)
            session.updated_at = datetime.now(UTC)
            return session.response()

    def complete(self, session_id: str) -> SessionResponse | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            session.state = SessionState.completed
            session.updated_at = datetime.now(UTC)
            self._event(session, "session.completed", "session marked complete")
            return session.response()

    def _transition(self, session: VoiceSession, intent: Intent) -> str:
        if intent is Intent.escalation:
            session.state = SessionState.escalated
            self._event(session, "session.escalated", "caller requested a human agent")
            return "I am transferring you to a human agent."
        if intent is Intent.goodbye:
            session.state = SessionState.completed
            self._event(session, "session.completed", "caller ended the conversation")
            return "Thank you for calling. Goodbye."
        if intent is Intent.appointment:
            if "appointment_date" in session.slots:
                session.state = SessionState.resolving
                self._event(session, "appointment.ready", "required date collected")
                return f"I can help with the appointment on {session.slots['appointment_date']}."
            session.state = SessionState.collecting_details
            return "What date would you prefer? Please use YYYY-MM-DD."
        if intent in {Intent.billing, Intent.support}:
            session.state = SessionState.resolving
            return "I have enough information to route this request for resolution."
        session.state = SessionState.collecting_details
        return "Please tell me whether this is about an appointment, billing, or support."

    @staticmethod
    def _collect_slots(session: VoiceSession, text: str) -> None:
        if date_match := APPOINTMENT_DATE.search(text):
            session.slots["appointment_date"] = date_match.group(1)
        if account_match := ACCOUNT_REFERENCE.search(text):
            session.slots["account_reference"] = account_match.group(1).upper()

    @staticmethod
    def _event(session: VoiceSession, event: str, detail: str) -> None:
        session.events.append(
            AuditEvent(event=event, detail=detail, created_at=datetime.now(UTC))
        )

    @staticmethod
    def _append_user(session: VoiceSession, text: str) -> None:
        session.transcript.append(
            TranscriptEntry(role="user", text=text, created_at=datetime.now(UTC))
        )

    @staticmethod
    def _append_assistant(session: VoiceSession, text: str) -> None:
        session.transcript.append(
            TranscriptEntry(role="assistant", text=text, created_at=datetime.now(UTC))
        )
