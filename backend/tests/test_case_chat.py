import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.db import get_db
from app.models import Case, CaseChatMessage


@pytest.fixture
def client(db_session):
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_case_chat_endpoints(client, db_session):
    # Setup mock case
    case = Case(
        client_name="Test Impresa Srl",
        client_tax_code="09876543210",
        code="PRAT-TEST-CHAT",
    )
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)

    # 1. GET chat initially empty
    res = client.get(f"/api/cases/{case.id}/chat")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 0
    assert data["messages"] == []

    # 2. Mock call_chat_llm and send message
    with patch("app.services.case_chat_service.call_chat_llm") as mock_llm:
        mock_llm.return_value = "Il dato proviene dal bilancio 2025 allegato alla voce A1."

        post_res = client.post(
            f"/api/cases/{case.id}/chat",
            json={"message": "Come hai ottenuto i ricavi del 2025?"},
        )
        assert post_res.status_code == 200
        post_data = post_res.json()
        assert post_data["user_message"]["sender"] == "user"
        assert post_data["user_message"]["content"] == "Come hai ottenuto i ricavi del 2025?"
        assert post_data["assistant_message"]["sender"] == "assistant"
        assert "voce A1" in post_data["assistant_message"]["content"]

    # 3. GET chat history returns 2 messages
    res2 = client.get(f"/api/cases/{case.id}/chat")
    assert res2.status_code == 200
    assert res2.json()["total"] == 2

    # 4. DELETE chat history
    del_res = client.delete(f"/api/cases/{case.id}/chat")
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True

    # 5. GET chat history is empty again
    res3 = client.get(f"/api/cases/{case.id}/chat")
    assert res3.status_code == 200
    assert res3.json()["total"] == 0

