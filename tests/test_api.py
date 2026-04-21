import sys
from importlib import import_module
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _load_test_client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("FROGGY_ADMIN_USERNAME", "frog_admin")
    monkeypatch.setenv("FROGGY_ADMIN_PASSWORD", "test-admin-secret")
    monkeypatch.setenv("FROGGY_DB_PATH", str(tmp_path / "froggy-test.db"))
    monkeypatch.setenv("FROGGY_ALLOWED_ORIGINS", "http://testserver")
    monkeypatch.setenv("FROGGY_COOKIE_SECURE", "false")
    monkeypatch.setenv("FROGGY_COOKIE_SAMESITE", "lax")

    for module_name in [name for name in list(sys.modules) if name == "backend" or name.startswith("backend.")]:
        sys.modules.pop(module_name, None)

    app_module = import_module("backend.main")
    return TestClient(app_module.app)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    with _load_test_client(tmp_path, monkeypatch) as test_client:
        yield test_client


def csrf_headers(client: TestClient) -> dict[str, str]:
    return {
        "X-CSRF-Token": client.cookies.get("froggy_csrf", ""),
    }


def login_admin(client: TestClient):
    response = client.post(
        "/api/auth/login",
        json={"username": "frog_admin", "password": "test-admin-secret"},
    )
    assert response.status_code == 200
    return response


def test_register_sets_cookie_session_and_restores_it(client: TestClient):
    response = client.post(
        "/api/auth/register",
        json={"username": "frog_student", "password": "super-secret"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert "token" not in payload
    assert payload["user"]["full_username"].startswith("frog_student#")
    assert payload["csrf_token"] == client.cookies.get("froggy_csrf")

    set_cookie_header = response.headers.get("set-cookie", "")
    assert "HttpOnly" in set_cookie_header
    assert "SameSite=lax" in set_cookie_header
    assert client.cookies.get("froggy_session")

    session_response = client.get("/api/auth/session")
    assert session_response.status_code == 200
    assert session_response.json()["user"]["full_username"] == payload["user"]["full_username"]


def test_mutating_endpoints_require_csrf(client: TestClient):
    client.post(
        "/api/auth/register",
        json={"username": "frog_player", "password": "super-secret"},
    )

    missing_csrf = client.post("/api/game/reset-all")
    assert missing_csrf.status_code == 403

    ok_response = client.post("/api/game/reset-all", headers=csrf_headers(client))
    assert ok_response.status_code == 200
    assert isinstance(ok_response.json()["items"], list)

    logout_response = client.post("/api/auth/logout", headers=csrf_headers(client))
    assert logout_response.status_code == 204
    assert client.get("/api/auth/session").status_code == 401


def test_admin_rejects_unknown_topic_and_supports_crud(client: TestClient):
    login_admin(client)

    invalid_payload = {
        "topic": "missing-topic",
        "type": "choice",
        "prompt": "Какой ответ правильный?",
        "explanation": "Потому что так.",
        "placeholder": None,
        "order_index": 0,
        "options": ["A", "B"],
        "correct_answers": ["A"],
    }
    invalid_response = client.post(
        "/api/admin/questions",
        json=invalid_payload,
        headers=csrf_headers(client),
    )
    assert invalid_response.status_code == 400
    assert "topic" in invalid_response.json()["detail"]

    list_invalid_topic = client.get("/api/admin/questions", params={"topic": "missing-topic"})
    assert list_invalid_topic.status_code == 400

    create_payload = {
        "topic": "python-easy",
        "type": "choice",
        "prompt": "Какой оператор выводит текст в Python?",
        "explanation": "print выводит строку в stdout.",
        "placeholder": None,
        "order_index": 999,
        "options": ["echo", "print"],
        "correct_answers": ["print"],
    }
    create_response = client.post(
        "/api/admin/questions",
        json=create_payload,
        headers=csrf_headers(client),
    )
    assert create_response.status_code == 201
    created_question = create_response.json()
    assert created_question["topic"] == "python-easy"
    assert created_question["language"] == "Python"

    update_payload = {
        "topic": "python-easy",
        "type": "input",
        "prompt": "Напиши функцию для вывода текста.",
        "explanation": "Правильный ответ: print.",
        "placeholder": "print('frog')",
        "order_index": 999,
        "options": [],
        "correct_answers": ["print"],
    }
    update_response = client.put(
        f"/api/admin/questions/{created_question['id']}",
        json=update_payload,
        headers=csrf_headers(client),
    )
    assert update_response.status_code == 200
    assert update_response.json()["type"] == "input"

    delete_response = client.delete(
        f"/api/admin/questions/{created_question['id']}",
        headers=csrf_headers(client),
    )
    assert delete_response.status_code == 204
