import re
import sys
from importlib import import_module
from datetime import datetime
from pathlib import Path
from typing import Optional

import pytest
from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _load_test_client(
    tmp_path,
    monkeypatch,
    *,
    admin_username: str = "frog_admin",
    admin_password: str = "test-admin-secret",
    db_path: Optional[Path] = None,
) -> TestClient:
    monkeypatch.setenv("FROGGY_ADMIN_USERNAME", admin_username)
    monkeypatch.setenv("FROGGY_ADMIN_PASSWORD", admin_password)
    monkeypatch.setenv("FROGGY_DB_PATH", str(db_path or (tmp_path / "froggy-test.db")))
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
    token = getattr(client, "_csrf_token", None) or client.cookies.get("froggy_csrf", "")
    return {
        "X-CSRF-Token": token,
    }


def login_admin(client: TestClient):
    response = client.post(
        "/api/auth/login",
        json={"username": "frog_admin", "password": "test-admin-secret"},
    )
    assert response.status_code == 200
    setattr(client, "_csrf_token", response.json()["csrf_token"])
    return response


def logout_current_session(client: TestClient):
    response = client.post("/api/auth/logout", headers=csrf_headers(client))
    assert response.status_code == 204
    setattr(client, "_csrf_token", None)
    return response


def register_user(client: TestClient, username: str, password: str = "super-secret") -> dict:
    response = client.post(
        "/api/auth/register",
        json={"username": username, "password": password},
    )
    assert response.status_code == 201
    payload = response.json()
    setattr(client, "_csrf_token", payload["csrf_token"])
    return payload


def get_correct_answer(question_id: int, question_type: str) -> str:
    db_module = import_module("backend.db")
    conn = db_module.get_connection()
    try:
        answers = db_module.get_correct_answers(conn, question_id, question_type)
        return answers[0]
    finally:
        conn.close()


def submit_correct_answer_for_topic(client: TestClient, topic: str) -> dict:
    bootstrap_response = client.get("/api/game/bootstrap", params={"topic": topic})
    assert bootstrap_response.status_code == 200
    bootstrap_payload = bootstrap_response.json()
    current_index = bootstrap_payload["progress"]["current_index"]
    question = bootstrap_payload["questions"][current_index]
    answer = get_correct_answer(question["id"], question["type"])

    submit_response = client.post(
        "/api/game/submit-answer",
        json={
            "topic": topic,
            "question_id": question["id"],
            "answer": answer,
        },
        headers=csrf_headers(client),
    )
    assert submit_response.status_code == 200
    return submit_response.json()


def test_register_sets_cookie_session_and_restores_it(client: TestClient):
    response = client.post(
        "/api/auth/register",
        json={"username": "frog_student", "password": "super-secret"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert "token" not in payload
    assert payload["user"]["full_username"].startswith("frog_student#")
    assert payload["csrf_token"]
    assert client.cookies.get("froggy_csrf") is None

    set_cookie_header = response.headers.get("set-cookie", "")
    assert "HttpOnly" in set_cookie_header
    assert "SameSite=lax" in set_cookie_header
    assert client.cookies.get("froggy_session")
    assert "froggy_csrf" not in set_cookie_header

    session_response = client.get("/api/auth/session")
    assert session_response.status_code == 200
    assert session_response.json()["user"]["full_username"] == payload["user"]["full_username"]
    assert session_response.json()["csrf_token"] == payload["csrf_token"]


def test_register_rejects_short_password_with_russian_message(client: TestClient):
    response = client.post(
        "/api/auth/register",
        json={"username": "frog_short", "password": "123"},
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "Пароль" in detail
    assert "не короче 6 символов" in detail
    assert "String should have at least 6 characters" not in detail


def test_mutating_endpoints_require_csrf(client: TestClient):
    register_response = client.post(
        "/api/auth/register",
        json={"username": "frog_player", "password": "super-secret"},
    )
    assert register_response.status_code == 201
    setattr(client, "_csrf_token", register_response.json()["csrf_token"])

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


def test_admin_password_is_synced_from_env_on_startup(tmp_path, monkeypatch):
    db_path = tmp_path / "froggy-test.db"

    with _load_test_client(
        tmp_path,
        monkeypatch,
        admin_password="old-admin-secret",
        db_path=db_path,
    ) as test_client:
        first_login = test_client.post(
            "/api/auth/login",
            json={"username": "frog_admin", "password": "old-admin-secret"},
        )
        assert first_login.status_code == 200

    with _load_test_client(
        tmp_path,
        monkeypatch,
        admin_password="new-admin-secret",
        db_path=db_path,
    ) as test_client:
        stale_login = test_client.post(
            "/api/auth/login",
            json={"username": "frog_admin", "password": "old-admin-secret"},
        )
        assert stale_login.status_code == 401

        synced_login = test_client.post(
            "/api/auth/login",
            json={"username": "frog_admin", "password": "new-admin-secret"},
        )
        assert synced_login.status_code == 200


def test_registration_retries_when_generated_tag_collides(client: TestClient, monkeypatch):
    first_user = register_user(client, "frog_alpha")
    first_tag = first_user["user"]["tag"]
    fallback_tag = "9876" if first_tag != "9876" else "6789"

    db_module = import_module("backend.db")
    generated_tags = iter([first_tag, fallback_tag])
    monkeypatch.setattr(
        db_module,
        "generate_unique_user_tag",
        lambda conn: next(generated_tags),
    )

    second_response = client.post(
        "/api/auth/register",
        json={"username": "frog_beta", "password": "super-secret"},
    )

    assert second_response.status_code == 201
    second_payload = second_response.json()
    assert second_payload["user"]["tag"] == fallback_tag
    assert second_payload["user"]["full_username"] == f"frog_beta#{fallback_tag}"


def test_leaderboard_coins_filters_by_topic(client: TestClient):
    python_user = register_user(client, "python_runner")
    python_handle = python_user["user"]["full_username"]
    python_answer = submit_correct_answer_for_topic(client, "python-easy")
    assert python_answer["coins_awarded"] == 10

    logout_current_session(client)

    javascript_user = register_user(client, "js_runner")
    javascript_handle = javascript_user["user"]["full_username"]
    javascript_answer = submit_correct_answer_for_topic(client, "javascript-easy")
    assert javascript_answer["coins_awarded"] == 10

    python_leaderboard = client.get(
        "/api/leaderboard",
        params={"topic": "python-easy", "metric": "coins"},
    )
    assert python_leaderboard.status_code == 200
    python_payload = python_leaderboard.json()
    python_handles = [entry["full_username"] for entry in python_payload["entries"]]
    assert python_payload["scope"] == "route"
    assert python_handle in python_handles
    assert javascript_handle not in python_handles

    javascript_leaderboard = client.get(
        "/api/leaderboard",
        params={"topic": "javascript-easy", "metric": "coins"},
    )
    assert javascript_leaderboard.status_code == 200
    javascript_payload = javascript_leaderboard.json()
    javascript_handles = [entry["full_username"] for entry in javascript_payload["entries"]]
    assert javascript_payload["scope"] == "route"
    assert javascript_handle in javascript_handles
    assert python_handle not in javascript_handles


def test_partial_progress_keeps_best_score_above_zero_after_reset(client: TestClient):
    register_user(client, "partial_score_player")

    answer_response = submit_correct_answer_for_topic(client, "python-easy")
    assert answer_response["next_progress"]["current_score"] == 1
    assert answer_response["next_progress"]["best_score"] == 1

    reset_response = client.post(
        "/api/game/reset-level",
        json={"topic": "python-easy"},
        headers=csrf_headers(client),
    )
    assert reset_response.status_code == 200
    assert reset_response.json()["best_score"] == 1


def test_locale_parameter_translates_bootstrap_and_routes(client: TestClient, monkeypatch):
    register_user(client, "locale_player")

    translation_module = import_module("backend.translation")

    def fake_translate_questions(questions, locale):
        translated_questions = []
        for question in questions:
            translated_question = dict(question)
            translated_question["prompt"] = f"{locale}::{question['prompt']}"
            if isinstance(question.get("options"), list):
                translated_question["options"] = [
                    f"{locale}::{option}" for option in question["options"]
                ]
            translated_questions.append(translated_question)
        return translated_questions

    def fake_translate_route_options(routes, locale):
        return [
            {**route, "difficulty_label": f"{locale}::{route['difficulty_label']}"}
            for route in routes
        ]

    monkeypatch.setattr(translation_module, "translate_questions", fake_translate_questions)
    monkeypatch.setattr(translation_module, "translate_route_options", fake_translate_route_options)

    routes_response = client.get("/api/game/routes", params={"locale": "en"})
    assert routes_response.status_code == 200
    routes_payload = routes_response.json()
    assert routes_payload["items"]
    assert routes_payload["items"][0]["difficulty_label"].startswith("en::")

    bootstrap_response = client.get(
        "/api/game/bootstrap",
        params={"topic": "python-easy", "locale": "en"},
    )
    assert bootstrap_response.status_code == 200
    bootstrap_payload = bootstrap_response.json()
    assert all(question["prompt"].startswith("en::") for question in bootstrap_payload["questions"])


def test_locale_parameter_translates_shop_and_daily(client: TestClient, monkeypatch):
    register_user(client, "locale_shop_player")

    translation_module = import_module("backend.translation")

    def fake_translate_shop_items(items, locale):
        return [
            {
                **item,
                "name": f"{locale}::{item['name']}",
                "description": f"{locale}::{item['description']}",
            }
            for item in items
        ]

    def fake_translate_question(question, locale):
        translated_question = dict(question)
        translated_question["prompt"] = f"{locale}::{question['prompt']}"
        return translated_question

    monkeypatch.setattr(translation_module, "translate_shop_items", fake_translate_shop_items)
    monkeypatch.setattr(translation_module, "translate_question", fake_translate_question)

    shop_response = client.get("/api/shop", params={"locale": "en"})
    assert shop_response.status_code == 200
    shop_payload = shop_response.json()
    assert shop_payload["items"]
    assert all(item["name"].startswith("en::") for item in shop_payload["items"])
    assert all(item["description"].startswith("en::") for item in shop_payload["items"])

    daily_response = client.get("/api/game/daily-challenge", params={"locale": "en"})
    assert daily_response.status_code == 200
    daily_payload = daily_response.json()
    assert daily_payload["question"]["prompt"].startswith("en::")


def test_leaderboard_metric_label_translates(client: TestClient, monkeypatch):
    register_user(client, "locale_leaderboard_player")

    translation_module = import_module("backend.translation")
    monkeypatch.setattr(
        translation_module,
        "translate_text",
        lambda text, locale: f"{locale}::{text}",
    )

    response = client.get(
        "/api/leaderboard",
        params={"topic": "python-easy", "metric": "coins", "locale": "en"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["metric_label"].startswith("en::")


def test_translate_batch_endpoint(client: TestClient, monkeypatch):
    translation_module = import_module("backend.translation")

    def fake_translate_texts(texts, locale):
        return [f"{locale}::{text}" for text in texts]

    monkeypatch.setattr(translation_module, "translate_texts", fake_translate_texts)

    response = client.post(
        "/api/i18n/translate",
        json={"texts": ["Привет", "Мир"], "locale": "en"},
    )

    assert response.status_code == 200
    assert response.json()["texts"] == ["en::Привет", "en::Мир"]


def test_local_translation_base_url_disables_public_fallback(monkeypatch):
    translation_module = import_module("backend.translation")

    monkeypatch.setattr(
        translation_module,
        "get_translation_api_base_url",
        lambda: "http://translator:5000",
    )
    monkeypatch.setattr(translation_module, "get_translation_api_key", lambda: "")

    assert translation_module._candidate_translation_urls() == [
        "http://translator:5000/translate"
    ]


def test_translation_has_no_public_fallback_without_configuration(monkeypatch):
    translation_module = import_module("backend.translation")

    monkeypatch.setattr(translation_module, "get_translation_api_base_url", lambda: "")
    monkeypatch.setattr(translation_module, "get_translation_api_key", lambda: "")

    assert translation_module._candidate_translation_urls() == []


def test_admin_translation_endpoints_honor_locale(client: TestClient, monkeypatch):
    login_admin(client)

    translation_module = import_module("backend.translation")

    def fake_translate_questions(questions, locale):
        translated_questions = []
        for question in questions:
            translated_question = dict(question)
            translated_question["prompt"] = f"{locale}::{question['prompt']}"
            if "explanation" in question:
                translated_question["explanation"] = f"{locale}::{question['explanation']}"
            translated_questions.append(translated_question)
        return translated_questions

    def fake_translate_promo_codes(promos, locale):
        return [
            {**promo, "description": f"{locale}::{promo['description']}"}
            for promo in promos
        ]

    monkeypatch.setattr(translation_module, "translate_questions", fake_translate_questions)
    monkeypatch.setattr(translation_module, "translate_promo_codes", fake_translate_promo_codes)

    questions_response = client.get(
        "/api/admin/questions",
        params={"topic": "python-easy", "locale": "en"},
    )
    assert questions_response.status_code == 200
    questions_payload = questions_response.json()
    assert questions_payload
    assert questions_payload[0]["prompt"].startswith("en::")
    assert questions_payload[0]["explanation"].startswith("en::")

    create_response = client.post(
        "/api/admin/promos",
        json={
            "code": "LOCALE77",
            "description": "Промо для перевода",
            "reward_coins": 77,
            "unlock_all_levels": False,
            "is_active": True,
        },
        headers=csrf_headers(client),
    )
    assert create_response.status_code == 201

    promos_response = client.get("/api/admin/promos", params={"locale": "en"})
    assert promos_response.status_code == 200
    promos_payload = promos_response.json()
    assert promos_payload["items"]
    assert any(item["description"].startswith("en::") for item in promos_payload["items"])


def test_admin_promos_support_crud_and_redemption(client: TestClient):
    login_admin(client)

    create_payload = {
        "code": "MARSH450",
        "description": "Тестовый бонус для QA.",
        "reward_coins": 450,
        "unlock_all_levels": False,
        "is_active": True,
    }
    create_response = client.post(
        "/api/admin/promos",
        json=create_payload,
        headers=csrf_headers(client),
    )
    assert create_response.status_code == 201
    assert create_response.json()["code"] == "MARSH450"

    update_payload = {
        "code": "MARSH450",
        "description": "Обновленный тестовый бонус.",
        "reward_coins": 450,
        "unlock_all_levels": True,
        "is_active": True,
    }
    update_response = client.put(
        "/api/admin/promos/MARSH450",
        json=update_payload,
        headers=csrf_headers(client),
    )
    assert update_response.status_code == 200
    updated_promo = update_response.json()
    assert updated_promo["code"] == "MARSH450"
    assert updated_promo["unlock_all_levels"] is True
    assert updated_promo["redemptions_count"] == 0

    list_response = client.get("/api/admin/promos")
    assert list_response.status_code == 200
    assert any(item["code"] == "MARSH450" for item in list_response.json()["items"])

    logout_current_session(client)

    redeeming_user = register_user(client, "promo_player")
    redeem_response = client.post(
        "/api/auth/redeem-promo",
        json={"code": "MARSH450"},
        headers=csrf_headers(client),
    )
    assert redeem_response.status_code == 200
    redeem_payload = redeem_response.json()
    assert redeem_payload["user"]["coins"] == redeeming_user["user"]["coins"] + 450
    assert "MARSH450" in redeem_payload["message"]
    assert all(
        item["total_questions"] == 0 or item["unlocked_level_index"] == item["levels_total"] - 1
        for item in redeem_payload["progresses"]
    )

    duplicate_redeem = client.post(
        "/api/auth/redeem-promo",
        json={"code": "MARSH450"},
        headers=csrf_headers(client),
    )
    assert duplicate_redeem.status_code == 400

    logout_current_session(client)
    login_admin(client)

    list_after_redeem = client.get("/api/admin/promos")
    assert list_after_redeem.status_code == 200
    marsh_promo = next(
        item for item in list_after_redeem.json()["items"] if item["code"] == "MARSH450"
    )
    assert marsh_promo["redemptions_count"] == 1

    delete_response = client.delete("/api/admin/promos/MARSH450", headers=csrf_headers(client))
    assert delete_response.status_code == 204

    final_list = client.get("/api/admin/promos")
    assert final_list.status_code == 200
    assert all(item["code"] != "MARSH450" for item in final_list.json()["items"])


def test_daily_challenge_and_progress_report(client: TestClient):
    register_user(client, "daily_player")

    daily_response = client.get("/api/game/daily-challenge")
    assert daily_response.status_code == 200
    daily_payload = daily_response.json()
    question = daily_payload["question"]
    answer = get_correct_answer(question["id"], question["type"])

    submit_response = client.post(
        "/api/game/daily-challenge",
        json={"answer": answer},
        headers=csrf_headers(client),
    )
    assert submit_response.status_code == 200
    submit_payload = submit_response.json()
    assert submit_payload["is_correct"] is True
    assert submit_payload["reward_coins"] == 25
    assert submit_payload["user"]["coins"] == 25
    assert submit_payload["leaderboard"][0]["full_username"].startswith("daily_player#")
    assert "Подсказка из desktop-версии:" not in submit_payload["explanation"]

    second_submit = client.post(
        "/api/game/daily-challenge",
        json={"answer": answer},
        headers=csrf_headers(client),
    )
    assert second_submit.status_code == 409

    repeated_fetch = client.get("/api/game/daily-challenge")
    assert repeated_fetch.status_code == 200
    repeated_payload = repeated_fetch.json()
    assert repeated_payload["already_answered"] is True
    assert repeated_payload["result"]["reward_coins"] == 25
    assert "Подсказка из desktop-версии:" not in repeated_payload["result"]["explanation"]

    report_response = client.get("/api/auth/progress-report", params={"locale": "zh"})
    assert report_response.status_code == 200
    assert report_response.headers["content-type"].startswith("application/pdf")
    assert re.search(
        r'attachment; filename="froggy-progress-report-zh-\d+\.pdf"',
        report_response.headers["content-disposition"],
    )
    assert report_response.content.startswith(b"%PDF")
    media_box = re.search(rb"/MediaBox\s*\[\s*0\s+0\s+([0-9.]+)\s+([0-9.]+)\s*\]", report_response.content)
    assert media_box is not None
    assert float(media_box.group(1)) > float(media_box.group(2))
    assert b"STSong-Light" in report_response.content


def test_progress_report_locale_copy_and_font_are_localized(client: TestClient):
    app_module = import_module("backend.main")
    copy = app_module.get_progress_report_copy("zh")

    assert copy["title"] == "Froggy Coder 进度报告"
    assert copy["summary_labels"] == ["路线", "已打开", "运行次数", "最佳"]
    assert copy["difficulty_labels"]["hard"] == "困难"
    assert copy["page_label_template"] == "第 {page} 页"
    assert app_module.get_pdf_font_name("zh") == "STSong-Light"
    assert app_module.get_progress_report_copy("ru")["subtitle_timezone"] == "(МСК)"


def test_progress_report_timestamp_format_is_compact():
    app_module = import_module("backend.main")

    assert app_module.format_report_timestamp(
        datetime(2026, 4, 23, 7, 8, 9)
    ) == "07:08:09 23.04.2026"


def test_daily_challenge_leaderboard_keeps_only_correct_answers_and_orders_by_speed(
    client: TestClient, monkeypatch
):
    first_user = register_user(client, "daily_speed_one")
    first_handle = first_user["user"]["full_username"]
    daily_response = client.get("/api/game/daily-challenge")
    assert daily_response.status_code == 200
    daily_payload = daily_response.json()
    question = daily_payload["question"]
    answer = get_correct_answer(question["id"], question["type"])

    db_module = import_module("backend.db")

    monkeypatch.setattr(db_module, "utc_now_iso", lambda: "2026-04-23T10:00:00Z")
    first_submit = client.post(
        "/api/game/daily-challenge",
        json={"answer": answer},
        headers=csrf_headers(client),
    )
    assert first_submit.status_code == 200
    first_payload = first_submit.json()
    assert first_payload["is_correct"] is True
    assert first_payload["leaderboard"][0]["full_username"] == first_handle

    logout_current_session(client)
    second_user = register_user(client, "daily_speed_two")
    second_handle = second_user["user"]["full_username"]
    monkeypatch.setattr(db_module, "utc_now_iso", lambda: "2026-04-23T10:05:00Z")
    second_submit = client.post(
        "/api/game/daily-challenge",
        json={"answer": answer},
        headers=csrf_headers(client),
    )
    assert second_submit.status_code == 200
    second_payload = second_submit.json()
    assert second_payload["is_correct"] is True
    assert [entry["full_username"] for entry in second_payload["leaderboard"]] == [
        first_handle,
        second_handle,
    ]
    assert [entry["rank"] for entry in second_payload["leaderboard"]] == [1, 2]

    logout_current_session(client)
    wrong_user = register_user(client, "daily_speed_wrong")
    wrong_handle = wrong_user["user"]["full_username"]
    monkeypatch.setattr(db_module, "utc_now_iso", lambda: "2026-04-23T10:10:00Z")
    wrong_submit = client.post(
        "/api/game/daily-challenge",
        json={"answer": "definitely-wrong-answer"},
        headers=csrf_headers(client),
    )
    assert wrong_submit.status_code == 200
    wrong_payload = wrong_submit.json()
    assert wrong_payload["is_correct"] is False
    assert wrong_payload["reward_coins"] == 0
    leaderboard_handles = [entry["full_username"] for entry in wrong_payload["leaderboard"]]
    assert leaderboard_handles == [first_handle, second_handle]
    assert wrong_handle not in leaderboard_handles
