from contextlib import asynccontextmanager
from collections import deque
from datetime import datetime, timedelta, timezone
from io import BytesIO
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional
from threading import Lock
import time

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from sqlite3 import Connection, IntegrityError

import backend.translation as translation
from backend.auth import (
    clear_session_cookies,
    create_session_tokens,
    hash_password,
    require_csrf,
    require_admin,
    require_session,
    require_user,
    set_session_cookies,
    verify_password,
)
from backend.config import get_admin_password, get_admin_username, get_allowed_origins
from backend.db import (
    DAILY_CHALLENGE_REWARD_COINS,
    HEARTS_PER_LEVEL,
    apply_answer_result,
    buy_or_equip_item,
    bootstrap_database,
    can_user_access_topic,
    create_question,
    create_session,
    create_user_with_generated_tag,
    delete_question,
    delete_promo_code_record,
    delete_session,
    evaluate_answer,
    get_daily_challenge_attempt,
    get_daily_challenge_row,
    get_correct_answers,
    get_db,
    get_promo_code,
    get_user_by_display_name_and_tag,
    get_question_by_id,
    get_question_by_index,
    get_user_shop_state,
    get_user_by_id,
    get_user_by_username,
    is_valid_user_tag,
    init_db,
    list_admin_questions,
    list_daily_challenge_leaderboard,
    list_leaderboard,
    list_promo_codes,
    list_public_questions,
    list_route_options,
    list_user_progress,
    normalize_question_explanation,
    redeem_promo_code,
    reset_level_progress,
    reset_all_progress,
    reset_progress,
    select_level_progress,
    serialize_public_question,
    serialize_user_row,
    serialize_progress,
    submit_daily_challenge_answer,
    utc_now_iso,
    update_question,
    update_user_profile,
    upsert_promo_code,
    ensure_progress_row,
)
from backend.game_meta import get_metric_meta, serialize_shop_items
from backend.seed_data import AVAILABLE_ROUTES, get_route_meta
from backend.schemas import (
    AdminQuestionIn,
    AnswerResponse,
    AuthResponse,
    BootstrapResponse,
    CredentialsIn,
    DailyChallengeResponse,
    DailyChallengeSubmitIn,
    DailyChallengeSubmitResponse,
    LeaderboardResponse,
    ProfileUpdateIn,
    PromoCodeIn,
    PromoCodeListResponse,
    PromoCodeOut,
    ProgressListResponse,
    PromoRedeemIn,
    PromoRedeemResponse,
    ProgressOut,
    RouteListResponse,
    SessionOut,
    SelectLevelIn,
    ShopResponse,
    TranslationBatchIn,
    TranslationBatchOut,
    TopicIn,
    SubmitAnswerIn,
    UserOut,
)


TOPIC_SLUG = AVAILABLE_ROUTES[0]["topic"] if AVAILABLE_ROUTES else "python-easy"
DEFAULT_ADMIN_USERNAME = get_admin_username()
DEFAULT_ADMIN_PASSWORD = get_admin_password()
TRANSLATION_MAX_TEXTS = 500
TRANSLATION_MAX_TOTAL_CHARS = 100000
TRANSLATION_RATE_LIMIT_WINDOW_SECONDS = 60.0
TRANSLATION_RATE_LIMIT_MAX_REQUESTS = 120
_TRANSLATION_RATE_LIMITS: dict[str, deque[float]] = {}
_TRANSLATION_RATE_LIMITS_LOCK = Lock()
MOSCOW_TIMEZONE = timezone(timedelta(hours=3), name="MSK")

VALIDATION_FIELD_LABELS = {
    "username": "Имя пользователя",
    "password": "Пароль",
    "display_name": "Имя пользователя",
    "current_password": "Текущий пароль",
    "new_password": "Новый пароль",
    "locale": "Язык",
    "topic": "Тема",
    "type": "Тип вопроса",
    "prompt": "Формулировка вопроса",
    "explanation": "Пояснение",
    "placeholder": "Подсказка",
    "code": "Код",
    "description": "Описание",
    "answer": "Ответ",
    "options": "Варианты ответа",
    "correct_answers": "Правильные ответы",
    "order_index": "Порядок",
    "reward_coins": "Количество монет",
    "unlock_all_levels": "Разблокировать все уровни",
    "is_active": "Активность",
}


def pluralize_ru(value: int, one: str, few: str, many: str) -> str:
    absolute = abs(value)
    remainder_10 = absolute % 10
    remainder_100 = absolute % 100

    if remainder_10 == 1 and remainder_100 != 11:
        return one

    if 2 <= remainder_10 <= 4 and not 12 <= remainder_100 <= 14:
        return few

    return many


def get_validation_field_label(location: object) -> str:
    if not isinstance(location, (list, tuple)):
        return "Поле"

    skipped = {"body", "query", "path", "header", "cookie"}
    for part in reversed(location):
        if isinstance(part, int):
            continue

        field_name = str(part)
        if field_name in skipped:
            continue

        return VALIDATION_FIELD_LABELS.get(
            field_name,
            field_name.replace("_", " ").capitalize(),
        )

    return "Поле"


def translate_validation_error(error: dict) -> str:
    field_label = get_validation_field_label(error.get("loc"))
    error_type = str(error.get("type", ""))
    context = error.get("ctx") or {}

    if error_type == "missing":
        return f"Поле «{field_label}» обязательно."

    if error_type == "string_too_short":
        min_length = context.get("min_length")
        if isinstance(min_length, int):
            return (
                f"{field_label} должен быть не короче {min_length} "
                f"{pluralize_ru(min_length, 'символ', 'символа', 'символов')}."
            )
        return f"{field_label} слишком короткий."

    if error_type == "string_too_long":
        max_length = context.get("max_length")
        if isinstance(max_length, int):
            return (
                f"{field_label} должен быть не длиннее {max_length} "
                f"{pluralize_ru(max_length, 'символ', 'символа', 'символов')}."
            )
        return f"{field_label} слишком длинный."

    if error_type in {"string_type", "bytes_type"}:
        return f"Поле «{field_label}» должно быть строкой."

    if error_type in {"int_parsing", "int_type"}:
        return f"Поле «{field_label}» должно быть числом."

    if error_type in {"bool_parsing", "bool_type"}:
        return f"Поле «{field_label}» должно быть true или false."

    if error_type in {"list_type", "set_type", "tuple_type"}:
        return f"Поле «{field_label}» должно быть списком."

    return f"Некорректное значение в поле «{field_label}»."


def _is_allowed_origin(origin: str) -> bool:
    normalized_origin = origin.rstrip("/").lower()
    allowed_origins = {item.rstrip("/").lower() for item in get_allowed_origins()}
    return normalized_origin in allowed_origins


def _enforce_translation_limits(request: Request, payload: TranslationBatchIn) -> None:
    origin = (request.headers.get("origin") or "").strip()
    if origin and not _is_allowed_origin(origin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Запрос из недоверенного origin.",
        )

    text_count = len(payload.texts)
    total_chars = sum(len(text) for text in payload.texts if isinstance(text, str))
    if text_count > TRANSLATION_MAX_TEXTS or total_chars > TRANSLATION_MAX_TOTAL_CHARS:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Слишком большой запрос перевода.",
        )

    client_host = (request.client.host if request.client else "unknown") or "unknown"
    now = time.monotonic()
    with _TRANSLATION_RATE_LIMITS_LOCK:
        bucket = _TRANSLATION_RATE_LIMITS.setdefault(client_host, deque())
        while bucket and now - bucket[0] > TRANSLATION_RATE_LIMIT_WINDOW_SECONDS:
            bucket.popleft()

        if len(bucket) >= TRANSLATION_RATE_LIMIT_MAX_REQUESTS:
            retry_after = max(
                1,
                int(TRANSLATION_RATE_LIMIT_WINDOW_SECONDS - (now - bucket[0])),
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Слишком много запросов перевода. Попробуй позже.",
                headers={"Retry-After": str(retry_after)},
            )

        bucket.append(now)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    admin_salt, admin_hash = hash_password(DEFAULT_ADMIN_PASSWORD)
    bootstrap_database(
        admin_username=DEFAULT_ADMIN_USERNAME,
        admin_password=DEFAULT_ADMIN_PASSWORD,
        admin_password_hash=admin_hash,
        admin_password_salt=admin_salt,
    )
    yield


app = FastAPI(
    title="Froggy Coder API",
    version="0.1.0",
    description="Backend API for the Froggy Coder portfolio project.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)


@app.exception_handler(RequestValidationError)
async def handle_validation_error(_: Request, exc: RequestValidationError):
    messages = [translate_validation_error(error) for error in exc.errors()]
    detail = "; ".join(messages) if messages else "Некорректные данные запроса."
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": detail},
    )


def sanitize_credentials(payload: CredentialsIn) -> Dict:
    username = payload.username.strip()
    password = payload.password.strip()

    if len(username) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Имя пользователя должно быть не короче 3 символов.",
        )

    if len(password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пароль должен быть не короче 6 символов.",
        )

    return {"username": username, "password": password}


def sanitize_registration_credentials(payload: CredentialsIn) -> Dict:
    cleaned = sanitize_credentials(payload)
    username = cleaned["username"]

    if len(username) > 32:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Имя пользователя должно быть не длиннее 32 символов.",
        )

    if "#" in username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Символ # использовать в имени нельзя: тэг выдаётся автоматически.",
        )

    return cleaned


def sanitize_profile_payload(payload: ProfileUpdateIn) -> Dict:
    display_name = payload.display_name.strip()
    current_password = payload.current_password.strip() if payload.current_password else None
    new_password = payload.new_password.strip() if payload.new_password else None

    if len(display_name) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Имя пользователя должно быть не короче 3 символов.",
        )

    if len(display_name) > 32:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Имя пользователя должно быть не длиннее 32 символов.",
        )

    if "#" in display_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Символ # использовать в имени нельзя: тэг остаётся отдельной частью логина.",
        )

    if current_password and not new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Чтобы сменить пароль, укажи новый пароль.",
        )

    if new_password and not current_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Для смены пароля нужен текущий пароль.",
        )

    if new_password and len(new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Новый пароль должен быть не короче 6 символов.",
        )

    return {
        "display_name": display_name,
        "current_password": current_password,
        "new_password": new_password,
    }


def sanitize_login_credentials(payload: CredentialsIn) -> Dict:
    cleaned = sanitize_credentials(payload)
    username = cleaned["username"]

    if "#" in username:
        display_name, tag = username.rsplit("#", 1)
        normalized_display_name = display_name.strip()
        normalized_tag = tag.strip()

        if not normalized_display_name or not is_valid_user_tag(normalized_tag):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Для входа укажи логин в формате имя#1234, где тэг состоит из 4 разных цифр.",
            )

    return cleaned


def ensure_known_topic(topic: str) -> Dict:
    normalized_topic = topic.strip().lower()
    route_meta = get_route_meta(normalized_topic)
    if route_meta is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Такого topic не существует.",
        )
    return route_meta


def sanitize_admin_payload(payload: AdminQuestionIn) -> Dict:
    topic = payload.topic.strip().lower()
    question_type = payload.type.strip().lower()
    prompt = payload.prompt.strip()
    explanation = payload.explanation.strip()
    placeholder = payload.placeholder.strip() if payload.placeholder else None
    options = [item.strip() for item in payload.options if item.strip()]
    correct_answers = [item.strip() for item in payload.correct_answers if item.strip()]

    if question_type not in {"choice", "input"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Тип вопроса должен быть choice или input.",
        )

    if question_type == "choice":
        if len(options) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Для choice-вопроса нужно минимум 2 варианта ответа.",
            )
        if len(correct_answers) != 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Для choice-вопроса нужен ровно один правильный ответ.",
            )
        if correct_answers[0] not in options:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Правильный ответ должен входить в список options.",
            )
    else:
        if not correct_answers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Для input-вопроса нужен хотя бы один правильный вариант.",
            )
        options = []

    route_meta = ensure_known_topic(topic)
    order_index = payload.order_index
    level_index = max(0, order_index // 5)
    task_index = max(0, order_index % 5)

    if order_index >= 100:
        level_index = order_index // 100
        task_index = order_index % 100

    return {
        "topic": topic,
        "language": route_meta["language"],
        "difficulty": route_meta["difficulty"],
        "level_index": level_index,
        "task_index": task_index,
        "type": question_type,
        "prompt": prompt,
        "explanation": explanation,
        "hint": explanation,
        "placeholder": placeholder,
        "order_index": order_index,
        "options": options,
        "correct_answers": correct_answers,
    }


def sanitize_promo_payload(payload: PromoCodeIn) -> Dict:
    code = payload.code.strip().upper()
    description = payload.description.strip()

    if len(code) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Код промокода должен быть не короче 3 символов.",
        )

    if not code.isalnum():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Промокод должен состоять только из букв и цифр.",
        )

    if len(description) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Описание промокода слишком короткое.",
        )

    return {
        "code": code,
        "description": description,
        "reward_coins": payload.reward_coins,
        "unlock_all_levels": payload.unlock_all_levels,
        "is_active": payload.is_active,
    }


def build_daily_challenge_response(conn: Connection, user_id: int, locale: str = "ru") -> Dict:
    question_row, challenge_date = get_daily_challenge_row(conn)
    if question_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ежедневный вопрос пока недоступен.",
        )

    attempt = get_daily_challenge_attempt(conn, user_id, challenge_date)
    result = None
    if attempt is not None:
        correct_answers = get_correct_answers(conn, question_row["id"], question_row["type"])
        result = {
            "is_correct": bool(attempt["is_correct"]),
            "correct_answers": correct_answers,
            "explanation": normalize_question_explanation(question_row["explanation"]),
            "reward_coins": DAILY_CHALLENGE_REWARD_COINS if bool(attempt["is_correct"]) else 0,
            "answered_at": attempt["answered_at"],
        }

    return {
        "challenge_date": challenge_date,
        "question": translation.translate_question(
            serialize_public_question(conn, question_row),
            locale,
        ),
        "reward_coins": DAILY_CHALLENGE_REWARD_COINS,
        "already_answered": attempt is not None,
        "result": translation.translate_question_feedback(result, locale) if result else None,
        "leaderboard": list_daily_challenge_leaderboard(conn, challenge_date),
    }


@lru_cache(maxsize=4)
def get_pdf_font_name(locale: Optional[str] = None) -> str:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.pdfbase.ttfonts import TTFont

    if translation.normalize_locale(locale) == "zh":
        font_name = "STSong-Light"
        if font_name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(UnicodeCIDFont(font_name))
        return font_name

    for candidate in [
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
        Path("/Library/Fonts/Arial Unicode.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/local/share/fonts/DejaVuSans.ttf"),
    ]:
        if not candidate.exists():
            continue

        font_name = "FroggyUnicode"
        if font_name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(font_name, str(candidate)))
        return font_name

    return "Helvetica"


def format_report_timestamp(now: Optional[datetime] = None) -> str:
    timestamp = now or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=MOSCOW_TIMEZONE)
    else:
        timestamp = timestamp.astimezone(MOSCOW_TIMEZONE)
    return timestamp.strftime("%H:%M:%S %d.%m.%Y")


def safe_pdf_text(value: str, font_name: str) -> str:
    if font_name != "Helvetica":
        return value

    try:
        value.encode("latin-1")
        return value
    except UnicodeEncodeError:
        return value.encode("latin-1", "replace").decode("latin-1")


REPORT_COPY = {
    "ru": {
        "title": "Отчёт по прогрессу Froggy Coder",
        "subtitle_user": "Пользователь",
        "subtitle_coins": "Монеты",
        "subtitle_generated": "Сгенерировано",
        "subtitle_timezone": "(МСК)",
        "summary_labels": ["Маршрутов", "Открыто", "Проходов", "Лучший результат"],
        "route_prefix": "Маршрут",
        "topic_label": "Тема",
        "difficulty_labels": {
            "easy": "Лёгкая",
            "medium": "Средняя",
            "hard": "Сложная",
        },
        "stat_labels": {
            "opened": "Открыто",
            "best_score": "Лучший результат",
            "runs": "Проходов",
            "current_score": "Текущий счёт",
            "unlocked_level": "Открытый уровень",
            "hearts": "Сердца",
        },
        "progress_label": "Прогресс",
        "empty_state": "Пока нет прогресса по маршрутам.",
        "page_label_template": "Страница {page}",
    },
    "en": {
        "title": "Froggy Coder Progress Report",
        "subtitle_user": "User",
        "subtitle_coins": "Coins",
        "subtitle_generated": "Generated",
        "subtitle_timezone": "(MSK)",
        "summary_labels": ["Routes", "Opened", "Runs", "Best"],
        "route_prefix": "Route",
        "topic_label": "Topic",
        "difficulty_labels": {
            "easy": "Easy",
            "medium": "Medium",
            "hard": "Hard",
        },
        "stat_labels": {
            "opened": "Opened",
            "best_score": "Best score",
            "runs": "Runs",
            "current_score": "Current score",
            "unlocked_level": "Unlocked level",
            "hearts": "Hearts",
        },
        "progress_label": "Progress",
        "empty_state": "No route progress recorded yet.",
        "page_label_template": "Page {page}",
    },
    "zh": {
        "title": "Froggy Coder 进度报告",
        "subtitle_user": "用户",
        "subtitle_coins": "金币",
        "subtitle_generated": "生成时间",
        "subtitle_timezone": "(莫斯科时间)",
        "summary_labels": ["路线", "已打开", "运行次数", "最佳"],
        "route_prefix": "路线",
        "topic_label": "主题",
        "difficulty_labels": {
            "easy": "简单",
            "medium": "中等",
            "hard": "困难",
        },
        "stat_labels": {
            "opened": "已打开",
            "best_score": "最佳分数",
            "runs": "运行次数",
            "current_score": "当前分数",
            "unlocked_level": "解锁等级",
            "hearts": "心数",
        },
        "progress_label": "进度",
        "empty_state": "尚未记录任何路线进度。",
        "page_label_template": "第 {page} 页",
    },
}


def get_progress_report_copy(locale: Optional[str]) -> dict:
    normalized_locale = translation.normalize_locale(locale)
    return REPORT_COPY[normalized_locale]


def build_progress_report_pdf(user: dict, progresses: list[dict], locale: Optional[str] = "ru") -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.pdfgen import canvas

    normalized_locale = translation.normalize_locale(locale)
    copy = get_progress_report_copy(normalized_locale)
    buffer = BytesIO()
    page_width, page_height = landscape(A4)
    pdf = canvas.Canvas(buffer, pagesize=(page_width, page_height))
    pdf.setTitle(copy["title"])
    font_name = get_pdf_font_name(normalized_locale)
    margin_x = 32
    margin_y = 28
    header_height = 78
    summary_height = 48
    summary_gap = 14
    card_gap_x = 14
    card_gap_y = 14
    card_columns = 3
    card_rows = 2
    card_width = (page_width - (margin_x * 2) - card_gap_x) / card_columns
    card_height = (
        page_height
        - (margin_y * 2)
        - header_height
        - summary_height
        - summary_gap
        - (card_gap_y * (card_rows - 1))
    ) / card_rows

    page_bg = colors.HexColor("#f4fbf5")
    page_mint = colors.HexColor("#d7f0e2")
    page_sun = colors.HexColor("#ffe6a6")
    page_coral = colors.HexColor("#ffd9d2")
    page_sky = colors.HexColor("#dcecff")

    header_bg = colors.HexColor("#143824")
    header_band = colors.HexColor("#1f5d3c")
    header_text_secondary = colors.HexColor("#d7e7da")

    card_bg = colors.HexColor("#fcfdfb")
    card_border = colors.HexColor("#d8e5dc")
    title_color = colors.HexColor("#132018")
    muted_color = colors.HexColor("#5a6a60")
    track_color = colors.HexColor("#e4ede7")

    summary_palette = [
        {
            "main": colors.HexColor("#4bb56e"),
            "tint": colors.HexColor("#def5e5"),
            "deep": colors.HexColor("#207444"),
        },
        {
            "main": colors.HexColor("#4fa1d8"),
            "tint": colors.HexColor("#dceffd"),
            "deep": colors.HexColor("#2d6f9a"),
        },
        {
            "main": colors.HexColor("#efb13f"),
            "tint": colors.HexColor("#fff0ca"),
            "deep": colors.HexColor("#b37310"),
        },
        {
            "main": colors.HexColor("#e56b5b"),
            "tint": colors.HexColor("#fde1dc"),
            "deep": colors.HexColor("#be4739"),
        },
    ]
    difficulty_palettes = {
        "easy": summary_palette[0],
        "medium": summary_palette[2],
        "hard": summary_palette[3],
    }

    total_routes = len(progresses)
    total_opened_questions = sum(item["opened_questions"] for item in progresses)
    total_completed_runs = sum(item["completed_runs"] for item in progresses)
    best_score = max((item["best_score"] for item in progresses), default=0)

    def draw_text(x: float, y: float, text: str, *, size: int, color) -> None:
        pdf.setFillColor(color)
        pdf.setFont(font_name, size)
        pdf.drawString(x, y, safe_pdf_text(text, font_name))

    def draw_page_background() -> None:
        pdf.setFillColor(page_bg)
        pdf.rect(0, 0, page_width, page_height, fill=1, stroke=0)

        decorations = [
            (-34, page_height + 14, 118, page_mint),
            (page_width + 30, page_height - 14, 104, page_sun),
            (page_width - 6, -18, 98, page_coral),
            (42, -36, 72, page_sky),
        ]
        for center_x, center_y, radius, fill_color in decorations:
            pdf.setFillColor(fill_color)
            pdf.circle(center_x, center_y, radius, fill=1, stroke=0)

        for dot_x, dot_y, dot_radius, fill_color in [
            (88, page_height - 70, 5, page_sun),
            (124, page_height - 56, 3, page_coral),
            (162, page_height - 88, 4, page_sky),
            (page_width - 132, 54, 4, page_mint),
            (page_width - 92, 86, 3, page_sun),
        ]:
            pdf.setFillColor(fill_color)
            pdf.circle(dot_x, dot_y, dot_radius, fill=1, stroke=0)

    def draw_frog_mascot(origin_x: float, origin_y: float, scale: float = 1.0) -> None:
        def px(value: float) -> float:
            return origin_x + value * scale

        def py(value: float) -> float:
            return origin_y + value * scale

        def pr(value: float) -> float:
            return value * scale

        pdf.saveState()
        pdf.setLineJoin(1)
        pdf.setLineCap(1)

        # Stylized frog built only from primitive PDF shapes.
        pdf.setFillColor(colors.HexColor("#f4d15a"))
        pdf.circle(px(46), py(28), pr(24), fill=1, stroke=0)

        pdf.setFillColor(colors.HexColor("#78d86c"))
        pdf.setStrokeColor(colors.HexColor("#4a8d42"))
        pdf.setLineWidth(pr(1.2))
        pdf.ellipse(px(10), py(3), px(90), py(22), fill=1, stroke=1)

        pdf.setFillColor(colors.HexColor("#2f8b46"))
        pdf.setStrokeColor(colors.HexColor("#2f8b46"))
        pdf.ellipse(px(24), py(14), px(72), py(42), fill=1, stroke=0)

        pdf.setFillColor(colors.HexColor("#caef9e"))
        pdf.ellipse(px(31), py(17), px(65), py(35), fill=1, stroke=0)

        pdf.setFillColor(colors.HexColor("#26763d"))
        pdf.ellipse(px(14), py(11), px(28), py(22), fill=1, stroke=0)
        pdf.ellipse(px(70), py(11), px(84), py(22), fill=1, stroke=0)

        pdf.setFillColor(colors.white)
        pdf.circle(px(37), py(42), pr(6), fill=1, stroke=0)
        pdf.circle(px(58), py(42), pr(6), fill=1, stroke=0)
        pdf.setFillColor(colors.HexColor("#183120"))
        pdf.circle(px(38), py(40.5), pr(2.3), fill=1, stroke=0)
        pdf.circle(px(59), py(40.5), pr(2.3), fill=1, stroke=0)
        pdf.setFillColor(colors.white)
        pdf.circle(px(39), py(41.8), pr(0.8), fill=1, stroke=0)
        pdf.circle(px(60), py(41.8), pr(0.8), fill=1, stroke=0)

        pdf.setFillColor(colors.HexColor("#f29aa6"))
        pdf.circle(px(30), py(25), pr(2.7), fill=1, stroke=0)
        pdf.circle(px(64), py(25), pr(2.7), fill=1, stroke=0)

        pdf.setStrokeColor(colors.HexColor("#183120"))
        pdf.setLineWidth(pr(1.3))
        pdf.bezier(px(39), py(23), px(44), py(17), px(52), py(17), px(57), py(23))

        pdf.setStrokeColor(colors.HexColor("#98d96e"))
        pdf.setLineWidth(pr(2.2))
        pdf.line(px(34), py(23), px(28), py(28))
        pdf.line(px(62), py(23), px(68), py(28))

        pdf.restoreState()

    def route_palette_for(item: dict, index: int) -> dict:
        route_meta = get_route_meta(item["topic"])
        difficulty = (route_meta["difficulty"] if route_meta is not None else "").lower()
        if difficulty in difficulty_palettes:
            return difficulty_palettes[difficulty]
        return summary_palette[index % len(summary_palette)]

    def start_page() -> None:
        draw_page_background()

    def draw_header() -> float:
        header_y = page_height - margin_y - header_height
        pdf.setFillColor(header_bg)
        pdf.roundRect(
            margin_x,
            header_y,
            page_width - (margin_x * 2),
            header_height,
            18,
            fill=1,
            stroke=0,
        )
        pdf.setFillColor(header_band)
        pdf.roundRect(margin_x + 10, header_y + 14, 6, header_height - 28, 3, fill=1, stroke=0)
        pdf.setFillColor(summary_palette[2]["main"])
        pdf.roundRect(margin_x + 20, header_y + 20, 6, header_height - 40, 3, fill=1, stroke=0)
        pdf.setFillColor(summary_palette[3]["main"])
        pdf.roundRect(margin_x + 30, header_y + 26, 6, header_height - 52, 3, fill=1, stroke=0)

        header_text_x = margin_x + 60
        draw_text(header_text_x, header_y + 42, copy["title"], size=20, color=colors.white)
        subtitle = (
            f"{copy['subtitle_user']}: {user['full_username']}   |   "
            f"{copy['subtitle_coins']}: {user['coins']}   |   "
            f"{copy['subtitle_generated']}: {format_report_timestamp()} {copy['subtitle_timezone']}"
        )
        draw_text(
            header_text_x,
            header_y + 19,
            subtitle,
            size=10,
            color=header_text_secondary,
        )
        draw_frog_mascot(page_width - margin_x - 112, header_y + 8, scale=0.82)
        return header_y

    def draw_summary_row(top_y: float) -> float:
        chip_gap = 10
        chip_width = (page_width - (margin_x * 2) - (chip_gap * 3)) / 4
        chip_height = summary_height
        chip_y = top_y - chip_height

        chips = [
            (copy["summary_labels"][0], str(total_routes), summary_palette[0]),
            (copy["summary_labels"][1], str(total_opened_questions), summary_palette[1]),
            (copy["summary_labels"][2], str(total_completed_runs), summary_palette[2]),
            (copy["summary_labels"][3], str(best_score), summary_palette[3]),
        ]

        for index, (label, value, palette) in enumerate(chips):
            chip_x = margin_x + index * (chip_width + chip_gap)
            pdf.setFillColor(palette["tint"])
            pdf.roundRect(chip_x, chip_y, chip_width, chip_height, 14, fill=1, stroke=0)
            pdf.setFillColor(palette["main"])
            pdf.rect(chip_x, chip_y + chip_height - 6, chip_width, 6, fill=1, stroke=0)
            draw_text(chip_x + 12, chip_y + 25, label.upper(), size=8, color=palette["deep"])
            draw_text(chip_x + 12, chip_y + 9, value, size=13, color=title_color)

        return chip_y

    def draw_empty_state(card_y: float, available_width: float) -> None:
        pdf.setFillColor(card_bg)
        pdf.setStrokeColor(card_border)
        pdf.roundRect(margin_x, card_y, available_width, card_height, 16, fill=1, stroke=1)
        draw_text(
            margin_x + 18,
            card_y + card_height / 2 - 5,
            copy["empty_state"],
            size=12,
            color=title_color,
        )

    def draw_stat_line(x: float, y: float, label: str, value: str, *, value_color=title_color) -> None:
        label_text = f"{label}: "
        label_size = 6.8
        value_size = 9.8
        pdf.setFillColor(muted_color)
        pdf.setFont(font_name, label_size)
        pdf.drawString(x, y, safe_pdf_text(label_text, font_name))
        label_width = pdf.stringWidth(safe_pdf_text(label_text, font_name), font_name, label_size)
        pdf.setFillColor(value_color)
        pdf.setFont(font_name, value_size)
        pdf.drawString(x + label_width, y - 0.8, safe_pdf_text(value, font_name))

    def draw_route_card(item: dict, card_x: float, card_y: float, card_number: int) -> None:
        route_meta = get_route_meta(item["topic"])
        palette = route_palette_for(item, card_number - 1)
        accent = palette["main"]
        accent_tint = palette["tint"]
        accent_deep = palette["deep"]
        difficulty_key = (route_meta["difficulty"] if route_meta is not None else "").lower()
        route_label = route_meta["language"] if route_meta is not None else item["topic"]

        pdf.setFillColor(card_bg)
        pdf.setStrokeColor(card_border)
        pdf.roundRect(card_x, card_y, card_width, card_height, 16, fill=1, stroke=1)
        pdf.setFillColor(accent)
        pdf.rect(card_x, card_y + card_height - 12, card_width, 12, fill=1, stroke=0)
        pdf.setFillColor(accent_tint)
        pdf.circle(card_x + card_width - 24, card_y + card_height - 28, 13, fill=1, stroke=0)
        pdf.setFillColor(accent_deep)
        pdf.setFont(font_name, 10)
        pdf.drawCentredString(card_x + card_width - 24, card_y + card_height - 32, f"{card_number:02d}")

        draw_text(card_x + 14, card_y + card_height - 28, route_label, size=13, color=title_color)

        stat_gap_x = 10
        stat_gap_y = 22
        stat_left = card_x + 14
        stat_cell_width = (card_width - 28 - stat_gap_x) / 2
        stat_xs = [
            stat_left,
            stat_left + stat_cell_width + stat_gap_x,
        ]
        stat_rows_top = card_y + card_height - 64
        stats = [
            (stat_xs[0], stat_rows_top, copy["stat_labels"]["opened"], f"{item['opened_questions']} / {item['total_questions']}"),
            (stat_xs[1], stat_rows_top, copy["stat_labels"]["best_score"], str(item["best_score"])),
            (stat_xs[0], stat_rows_top - stat_gap_y, copy["stat_labels"]["runs"], str(item["completed_runs"])),
            (stat_xs[1], stat_rows_top - stat_gap_y, copy["stat_labels"]["current_score"], str(item["current_score"])),
        ]

        for x, y, label, value in stats:
            draw_stat_line(x, y, label, value)
        draw_stat_line(
            stat_left,
            stat_rows_top - (stat_gap_y * 2),
            copy["stat_labels"]["unlocked_level"],
            f"{item['unlocked_level_index'] + 1} / {item['levels_total']}",
        )

        bar_x = card_x + 14
        bar_y = card_y + 14
        bar_width = card_width - 28
        bar_height = 9
        progress_ratio = (
            item["opened_questions"] / item["total_questions"]
            if item["total_questions"] > 0
            else 0.0
        )
        progress_text_y = card_y + 31
        pdf.setFillColor(track_color)
        pdf.roundRect(bar_x, bar_y, bar_width, bar_height, 4, fill=1, stroke=0)
        if progress_ratio > 0:
            pdf.setFillColor(accent)
            pdf.roundRect(
                bar_x,
                bar_y,
                max(bar_height, bar_width * progress_ratio),
                bar_height,
                4,
                fill=1,
                stroke=0,
            )
        draw_text(bar_x, progress_text_y, copy["progress_label"], size=7, color=muted_color)
        pdf.setFillColor(accent_deep)
        pdf.setFont(font_name, 7)
        pdf.drawRightString(
            bar_x + bar_width,
            progress_text_y,
            safe_pdf_text(f"{item['opened_questions']} / {item['total_questions']}", font_name),
        )

    items_per_page = card_columns * card_rows
    pages = [progresses[index : index + items_per_page] for index in range(0, len(progresses), items_per_page)] or [[]]
    for page_index, page_items in enumerate(pages):
        start_page()
        header_y = draw_header()
        summary_y = draw_summary_row(header_y - 12)
        grid_top = summary_y - summary_gap

        if not page_items:
            draw_empty_state(grid_top - card_height, page_width - (margin_x * 2))
        else:
            for item_index, item in enumerate(page_items):
                column = item_index % card_columns
                row = item_index // card_columns
                card_x = margin_x + column * (card_width + card_gap_x)
                card_y = grid_top - ((row + 1) * card_height) - (row * card_gap_y)
                draw_route_card(item, card_x, card_y, page_index * 6 + item_index + 1)

        footer_label = copy["page_label_template"].format(page=page_index + 1)
        footer_width = pdf.stringWidth(footer_label, font_name, 8) + 20
        footer_x = page_width - margin_x - footer_width
        footer_y = 4
        pdf.setFillColor(page_mint)
        pdf.roundRect(footer_x, footer_y, footer_width, 18, 9, fill=1, stroke=0)
        draw_text(footer_x + 10, footer_y + 5, footer_label, size=8, color=muted_color)
        if page_index < len(pages) - 1:
            pdf.showPage()
            pdf.setPageSize((page_width, page_height))

    pdf.save()
    return buffer.getvalue()


def ensure_topic_access(topic: str, user: dict) -> str:
    normalized_topic = topic.strip().lower()
    if not can_user_access_topic(user["id"], normalized_topic):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Маршрут не найден.",
        )
    return normalized_topic


@app.get("/api/health")
def healthcheck() -> Dict:
    return {"status": "ok", "topic": TOPIC_SLUG}


@app.post("/api/i18n/translate", response_model=TranslationBatchOut)
def translate_batch(payload: TranslationBatchIn, request: Request):
    _enforce_translation_limits(request, payload)
    return {
        "texts": translation.translate_texts(payload.texts, payload.locale),
    }


@app.get("/api/game/routes", response_model=RouteListResponse)
def game_routes(
    locale: str = Query(default="ru"),
    user: dict = Depends(require_user),
    conn: Connection = Depends(get_db),
):
    return {
        "items": translation.translate_route_options(
            list_route_options(conn, user["id"]),
            locale,
        )
    }


@app.post("/api/auth/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: CredentialsIn,
    response: Response,
    conn: Connection = Depends(get_db),
):
    cleaned = sanitize_registration_credentials(payload)
    password_salt, password_hash = hash_password(cleaned["password"])

    try:
        user = create_user_with_generated_tag(
            conn,
            display_name=cleaned["username"],
            password_hash=password_hash,
            password_salt=password_salt,
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Не удалось создать пользователя.",
        ) from exc

    session_token, csrf_token, expires_at = create_session_tokens()
    create_session(conn, user["id"], session_token, csrf_token, expires_at)
    set_session_cookies(response, session_token)
    return {"user": serialize_user_row(user), "csrf_token": csrf_token}


@app.post("/api/auth/login", response_model=AuthResponse)
def login(
    payload: CredentialsIn,
    response: Response,
    conn: Connection = Depends(get_db),
):
    cleaned = sanitize_login_credentials(payload)
    user = get_user_by_username(conn, cleaned["username"])
    if user is None and "#" in cleaned["username"]:
        display_name, tag = cleaned["username"].rsplit("#", 1)
        user = get_user_by_display_name_and_tag(conn, display_name.strip(), tag.strip())

    if user is None or not verify_password(
        cleaned["password"],
        user["password_salt"],
        user["password_hash"],
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль.",
        )

    session_token, csrf_token, expires_at = create_session_tokens()
    create_session(conn, user["id"], session_token, csrf_token, expires_at)
    set_session_cookies(response, session_token)
    return {"user": serialize_user_row(user), "csrf_token": csrf_token}


@app.get("/api/auth/session", response_model=SessionOut)
def session_state(session: dict = Depends(require_session)):
    return {
        "user": session["user"],
        "csrf_token": session["csrf_token"],
    }


@app.get("/api/auth/me", response_model=UserOut)
def me(user: dict = Depends(require_user)):
    return user


@app.get("/api/auth/progress-report")
def progress_report(
    user: dict = Depends(require_user),
    conn: Connection = Depends(get_db),
    locale: str = Query(default="ru"),
):
    pdf_bytes = build_progress_report_pdf(
        user,
        list_user_progress(conn, user["id"]),
        locale,
    )
    report_locale = translation.normalize_locale(locale)
    filename = f"froggy-progress-report-{report_locale}-{user['id']}.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@app.put("/api/auth/profile", response_model=UserOut)
def update_profile(
    payload: ProfileUpdateIn,
    session: dict = Depends(require_csrf),
    user: dict = Depends(require_user),
    conn: Connection = Depends(get_db),
):
    _ = session
    cleaned = sanitize_profile_payload(payload)
    user_row = get_user_by_id(conn, user["id"])

    if user_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден.",
        )

    password_hash = user_row["password_hash"]
    password_salt = user_row["password_salt"]

    if cleaned["new_password"]:
        if not verify_password(
            cleaned["current_password"],
            user_row["password_salt"],
            user_row["password_hash"],
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Текущий пароль указан неверно.",
            )

        password_salt, password_hash = hash_password(cleaned["new_password"])

    try:
        updated_user = update_user_profile(
            conn,
            user_id=user_row["id"],
            display_name=cleaned["display_name"],
            password_hash=password_hash,
            password_salt=password_salt,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден.",
        ) from exc
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Не удалось обновить профиль.",
        ) from exc

    return serialize_user_row(updated_user)


@app.post("/api/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    session: dict = Depends(require_csrf),
    conn: Connection = Depends(get_db),
):
    delete_session(conn, session["token"])
    clear_session_cookies(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@app.get("/api/game/bootstrap", response_model=BootstrapResponse)
def game_bootstrap(
    topic: str = Query(default=TOPIC_SLUG),
    locale: str = Query(default="ru"),
    user: dict = Depends(require_user),
    conn: Connection = Depends(get_db),
):
    topic = ensure_topic_access(topic, user)
    progress_row = ensure_progress_row(conn, user["id"], topic)
    questions = translation.translate_questions(list_public_questions(conn, topic), locale)
    progress = serialize_progress(conn, progress_row, topic)
    return {
        "user": user,
        "questions": questions,
        "progress": progress,
    }


@app.get("/api/game/progress", response_model=ProgressListResponse)
def game_progress_list(
    user: dict = Depends(require_user),
    conn: Connection = Depends(get_db),
):
    return {"items": list_user_progress(conn, user["id"])}


@app.get("/api/game/daily-challenge", response_model=DailyChallengeResponse)
def daily_challenge(
    locale: str = Query(default="ru"),
    user: dict = Depends(require_user),
    conn: Connection = Depends(get_db),
):
    return build_daily_challenge_response(conn, user["id"], locale)


@app.post("/api/game/daily-challenge", response_model=DailyChallengeSubmitResponse)
def submit_daily_challenge(
    payload: DailyChallengeSubmitIn,
    locale: str = Query(default="ru"),
    session: dict = Depends(require_csrf),
    user: dict = Depends(require_user),
    conn: Connection = Depends(get_db),
):
    _ = session
    try:
        result = submit_daily_challenge_answer(conn, user["id"], payload.answer)
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ежедневный вопрос пока недоступен.",
        ) from exc

    return {
        "challenge_date": result["challenge_date"],
        "is_correct": result["is_correct"],
        "correct_answers": translation.translate_texts(result["correct_answers"], locale),
        "explanation": translation.translate_text(result["explanation"], locale),
        "reward_coins": result["reward_coins"],
        "answered_at": result["answered_at"],
        "user": result["user"],
        "leaderboard": result["leaderboard"],
    }


@app.get("/api/shop", response_model=ShopResponse)
def shop_bootstrap(
    locale: str = Query(default="ru"),
    user: dict = Depends(require_user),
    conn: Connection = Depends(get_db),
):
    fresh_user = get_user_shop_state(conn, user["id"])
    return {
        "user": fresh_user,
        "items": translation.translate_shop_items(
            serialize_shop_items(fresh_user["inventory"], fresh_user["active_skin"]),
            locale,
        ),
        "message": None,
    }


@app.post("/api/shop/items/{item_id}", response_model=ShopResponse)
def shop_buy_or_equip(
    item_id: str,
    locale: str = Query(default="ru"),
    session: dict = Depends(require_csrf),
    user: dict = Depends(require_user),
    conn: Connection = Depends(get_db),
):
    _ = session
    try:
        result = buy_or_equip_item(conn, user["id"], item_id.strip().lower())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Такого предмета в магазине нет.",
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    message = (
        f"Куплено и надето: {result['item']['name']}."
        if result["purchased"]
        else f"Теперь активен предмет: {result['item']['name']}."
    )
    return {
        "user": result["user"],
        "items": translation.translate_shop_items(
            serialize_shop_items(result["user"]["inventory"], result["user"]["active_skin"]),
            locale,
        ),
        "message": translation.translate_message(message, locale),
    }


@app.post("/api/auth/redeem-promo", response_model=PromoRedeemResponse)
def redeem_promo(
    payload: PromoRedeemIn,
    locale: str = Query(default="ru"),
    session: dict = Depends(require_csrf),
    user: dict = Depends(require_user),
    conn: Connection = Depends(get_db),
):
    _ = session
    try:
        result = redeem_promo_code(conn, user["id"], payload.code)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    if result.get("message"):
        result["message"] = translation.translate_message(result["message"], locale)
    return result


@app.post("/api/game/reset", response_model=ProgressOut)
def reset_game(
    topic: str = Query(default=TOPIC_SLUG),
    session: dict = Depends(require_csrf),
    user: dict = Depends(require_user),
    conn: Connection = Depends(get_db),
):
    _ = session
    topic = ensure_topic_access(topic, user)
    return reset_progress(conn, user["id"], topic)


@app.post("/api/game/reset-all", response_model=ProgressListResponse)
def reset_all_game_progress(
    session: dict = Depends(require_csrf),
    user: dict = Depends(require_user),
    conn: Connection = Depends(get_db),
):
    _ = session
    return {"items": reset_all_progress(conn, user["id"])}


@app.post("/api/game/select-level", response_model=ProgressOut)
def select_level(
    payload: SelectLevelIn,
    session: dict = Depends(require_csrf),
    user: dict = Depends(require_user),
    conn: Connection = Depends(get_db),
):
    _ = session
    topic = ensure_topic_access(payload.topic, user)
    progress = ensure_progress_row(conn, user["id"], topic)
    current = serialize_progress(conn, progress, topic)

    if payload.level_index > current["unlocked_level_index"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Этот уровень пока еще закрыт.",
        )

    return select_level_progress(conn, user["id"], topic, payload.level_index)


@app.post("/api/game/reset-level", response_model=ProgressOut)
def reset_current_level(
    payload: TopicIn,
    session: dict = Depends(require_csrf),
    user: dict = Depends(require_user),
    conn: Connection = Depends(get_db),
):
    _ = session
    topic = ensure_topic_access(payload.topic, user)
    return reset_level_progress(conn, user["id"], topic)


@app.post("/api/game/submit-answer", response_model=AnswerResponse)
def submit_answer(
    payload: SubmitAnswerIn,
    locale: str = Query(default="ru"),
    session: dict = Depends(require_csrf),
    user: dict = Depends(require_user),
    conn: Connection = Depends(get_db),
):
    _ = session
    topic = ensure_topic_access(payload.topic, user)
    progress_row = ensure_progress_row(conn, user["id"], topic)
    current_question = get_question_by_index(conn, topic, progress_row["current_index"])

    if current_question is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Активного вопроса нет. Начни новый забег.",
        )

    if current_question["id"] != payload.question_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Прогресс устарел. Обнови данные и попробуй снова.",
        )

    correct_answers = get_correct_answers(
        conn,
        current_question["id"],
        current_question["type"],
    )
    is_correct = evaluate_answer(payload.answer, correct_answers)
    result = apply_answer_result(
        conn=conn,
        user_id=user["id"],
        topic=topic,
        question_id=current_question["id"],
        submitted_answer=payload.answer,
        is_correct=is_correct,
    )

    return {
        "is_correct": is_correct,
        "correct_answers": translation.translate_texts(correct_answers, locale),
        "explanation": translation.translate_text(current_question["explanation"], locale),
        "next_progress": result["next_progress"],
        "user": serialize_user_row(get_user_by_id(conn, user["id"])),
        "coins_awarded": result["coins_awarded"],
        "quiz_completed": result["quiz_completed"],
        "final_score": result["final_score"],
        "total_questions": result["next_progress"]["total_questions"],
    }


@app.get("/api/leaderboard", response_model=LeaderboardResponse)
def leaderboard(
    topic: str = Query(default=TOPIC_SLUG),
    metric: str = Query(default="best_score"),
    locale: str = Query(default="ru"),
    limit: int = Query(default=10, ge=1, le=50),
    conn: Connection = Depends(get_db),
):
    metric_meta = get_metric_meta(metric)
    return {
        "topic": topic,
        "metric": metric if metric in {"best_score", "completed_runs", "coins"} else "best_score",
        "metric_label": translation.translate_text(metric_meta["label"], locale),
        "scope": metric_meta["scope"],
        "entries": list_leaderboard(conn, topic, metric, limit),
    }


@app.get("/api/admin/questions")
def admin_list_questions(
    topic: str = Query(default=TOPIC_SLUG),
    locale: str = Query(default="ru"),
    admin: dict = Depends(require_admin),
    conn: Connection = Depends(get_db),
):
    _ = admin
    normalized_topic = topic.strip().lower()
    ensure_known_topic(normalized_topic)
    return translation.translate_questions(list_admin_questions(conn, normalized_topic), locale)


@app.get("/api/admin/promos", response_model=PromoCodeListResponse)
def admin_list_promos(
    locale: str = Query(default="ru"),
    admin: dict = Depends(require_admin),
    conn: Connection = Depends(get_db),
):
    _ = admin
    return {"items": translation.translate_promo_codes(list_promo_codes(conn), locale)}


@app.post("/api/admin/promos", response_model=PromoCodeOut, status_code=status.HTTP_201_CREATED)
def admin_create_promo(
    payload: PromoCodeIn,
    session: dict = Depends(require_csrf),
    admin: dict = Depends(require_admin),
    conn: Connection = Depends(get_db),
):
    _ = session
    _ = admin
    cleaned = sanitize_promo_payload(payload)
    existing_row = get_promo_code(conn, cleaned["code"])
    if existing_row is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Промокод с таким кодом уже существует.",
        )
    return upsert_promo_code(conn, cleaned)


@app.put("/api/admin/promos/{code}", response_model=PromoCodeOut)
def admin_update_promo(
    code: str,
    payload: PromoCodeIn,
    session: dict = Depends(require_csrf),
    admin: dict = Depends(require_admin),
    conn: Connection = Depends(get_db),
):
    _ = session
    _ = admin
    normalized_code = code.strip().upper()
    existing_row = get_promo_code(conn, normalized_code)
    if existing_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Промокод не найден.",
        )
    cleaned = sanitize_promo_payload(payload)
    cleaned["code"] = normalized_code
    return upsert_promo_code(conn, cleaned)


@app.delete("/api/admin/promos/{code}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_promo(
    code: str,
    session: dict = Depends(require_csrf),
    admin: dict = Depends(require_admin),
    conn: Connection = Depends(get_db),
):
    _ = session
    _ = admin
    existing_row = get_promo_code(conn, code)
    if existing_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Промокод не найден.",
        )
    delete_promo_code_record(conn, code)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/api/admin/questions", status_code=status.HTTP_201_CREATED)
def admin_create_question(
    payload: AdminQuestionIn,
    session: dict = Depends(require_csrf),
    admin: dict = Depends(require_admin),
    conn: Connection = Depends(get_db),
):
    _ = session
    _ = admin
    question = create_question(conn, sanitize_admin_payload(payload))
    return question


@app.put("/api/admin/questions/{question_id}")
def admin_update_question(
    question_id: int,
    payload: AdminQuestionIn,
    session: dict = Depends(require_csrf),
    admin: dict = Depends(require_admin),
    conn: Connection = Depends(get_db),
):
    _ = session
    _ = admin
    row = get_question_by_id(conn, question_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Вопрос не найден.",
        )
    return update_question(conn, question_id, sanitize_admin_payload(payload))


@app.delete("/api/admin/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_question(
    question_id: int,
    session: dict = Depends(require_csrf),
    admin: dict = Depends(require_admin),
    conn: Connection = Depends(get_db),
):
    _ = session
    _ = admin
    row = get_question_by_id(conn, question_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Вопрос не найден.",
        )
    delete_question(conn, question_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
