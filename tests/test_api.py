from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def create_session() -> dict:
    response = client.post(
        "/sessions", json={"caller_id": "+15550001111", "direction": "inbound"}
    )
    assert response.status_code == 201
    return response.json()


def test_session_starts_with_greeting():
    session = create_session()
    assert session["state"] == "greeting"
    assert session["transcript"][0]["role"] == "assistant"


def test_appointment_collects_date_and_moves_to_resolving():
    session = create_session()
    response = client.post(
        f"/sessions/{session['id']}/messages",
        json={"text": "Schedule an appointment for 2026-11-15"},
    )
    payload = response.json()
    assert payload["intent"] == "appointment"
    assert payload["state"] == "resolving"
    assert payload["slots"]["appointment_date"] == "2026-11-15"


def test_appointment_without_date_collects_details():
    session = create_session()
    response = client.post(
        f"/sessions/{session['id']}/messages", json={"text": "I need an appointment"}
    )
    assert response.json()["state"] == "collecting_details"


def test_date_only_follow_up_keeps_appointment_context():
    session = create_session()
    client.post(
        f"/sessions/{session['id']}/messages", json={"text": "I need an appointment"}
    )
    response = client.post(
        f"/sessions/{session['id']}/messages", json={"text": "2026-11-15"}
    )
    payload = response.json()
    assert payload["intent"] == "appointment"
    assert payload["state"] == "resolving"
    assert payload["slots"]["appointment_date"] == "2026-11-15"


def test_human_request_escalates_with_audit_event():
    session = create_session()
    response = client.post(
        f"/sessions/{session['id']}/messages",
        json={"text": "Please transfer me to a human agent"},
    )
    payload = response.json()
    assert payload["state"] == "escalated"
    assert payload["events"][-1]["event"] == "session.escalated"


def test_unknown_session_returns_404():
    response = client.get("/sessions/not-found")
    assert response.status_code == 404
