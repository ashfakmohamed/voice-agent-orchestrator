from fastapi import FastAPI, HTTPException

from app.models import MessageCreate, SessionCreate, SessionResponse
from app.orchestrator import VoiceOrchestrator

orchestrator = VoiceOrchestrator()
app = FastAPI(
    title="Voice Agent Orchestrator",
    description="Deterministic orchestration core for enterprise voice-agent sessions.",
    version="1.0.0",
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/sessions", response_model=SessionResponse, status_code=201)
async def create_session(payload: SessionCreate) -> SessionResponse:
    return orchestrator.create(payload.caller_id, payload.direction)


@app.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str) -> SessionResponse:
    session = orchestrator.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.post("/sessions/{session_id}/messages", response_model=SessionResponse)
async def add_message(session_id: str, payload: MessageCreate) -> SessionResponse:
    session = orchestrator.handle_message(session_id, payload.text)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.post("/sessions/{session_id}/complete", response_model=SessionResponse)
async def complete_session(session_id: str) -> SessionResponse:
    session = orchestrator.complete(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session
