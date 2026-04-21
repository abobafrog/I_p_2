from contextlib import asynccontextmanager
from typing import Dict

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlite3 import Connection, IntegrityError

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
    apply_answer_result,
    build_full_username,
    buy_or_equip_item,
    bootstrap_database,
    can_user_access_topic,
    create_question,
    create_session,
    create_user,
    delete_question,
    delete_session,
    evaluate_answer,
    generate_unique_user_tag,
    get_correct_answers,
    get_db,
    get_user_by_display_name_and_tag,
    get_question_by_id,
    get_question_by_index,
    get_user_shop_state,
    get_user_by_id,
    get_user_by_username,
    is_valid_user_tag,
    init_db,
    list_admin_questions,
    list_leaderboard,
    list_public_questions,
    list_route_options,
    list_user_progress,
    redeem_promo_code,
    reset_level_progress,
    reset_all_progress,
    reset_progress,
    select_level_progress,
    serialize_user_row,
    serialize_progress,
    update_question,
    update_user_profile,
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
    LeaderboardResponse,
    ProfileUpdateIn,
    ProgressListResponse,
    PromoRedeemIn,
    PromoRedeemResponse,
    ProgressOut,
    RouteListResponse,
    SessionOut,
    SelectLevelIn,
    ShopResponse,
    TopicIn,
    SubmitAnswerIn,
    UserOut,
)


TOPIC_SLUG = AVAILABLE_ROUTES[0]["topic"] if AVAILABLE_ROUTES else "python-easy"
DEFAULT_ADMIN_USERNAME = get_admin_username()
DEFAULT_ADMIN_PASSWORD = get_admin_password()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    admin_salt, admin_hash = hash_password(DEFAULT_ADMIN_PASSWORD)
    bootstrap_database(
        admin_username=DEFAULT_ADMIN_USERNAME,
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


@app.get("/api/game/routes", response_model=RouteListResponse)
def game_routes(
    user: dict = Depends(require_user),
    conn: Connection = Depends(get_db),
):
    return {"items": list_route_options(conn, user["id"])}


@app.post("/api/auth/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: CredentialsIn,
    response: Response,
    conn: Connection = Depends(get_db),
):
    cleaned = sanitize_registration_credentials(payload)
    tag = generate_unique_user_tag(conn)
    login_handle = build_full_username(cleaned["username"], tag)

    password_salt, password_hash = hash_password(cleaned["password"])

    try:
        user = create_user(
            conn,
            username=login_handle,
            display_name=cleaned["username"],
            tag=tag,
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
    set_session_cookies(response, session_token, csrf_token)
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
    set_session_cookies(response, session_token, csrf_token)
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
    user: dict = Depends(require_user),
    conn: Connection = Depends(get_db),
):
    topic = ensure_topic_access(topic, user)
    progress_row = ensure_progress_row(conn, user["id"], topic)
    questions = list_public_questions(conn, topic)
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


@app.get("/api/shop", response_model=ShopResponse)
def shop_bootstrap(
    user: dict = Depends(require_user),
    conn: Connection = Depends(get_db),
):
    fresh_user = get_user_shop_state(conn, user["id"])
    return {
        "user": fresh_user,
        "items": serialize_shop_items(fresh_user["inventory"], fresh_user["active_skin"]),
        "message": None,
    }


@app.post("/api/shop/items/{item_id}", response_model=ShopResponse)
def shop_buy_or_equip(
    item_id: str,
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
        "items": serialize_shop_items(result["user"]["inventory"], result["user"]["active_skin"]),
        "message": message,
    }


@app.post("/api/auth/redeem-promo", response_model=PromoRedeemResponse)
def redeem_promo(
    payload: PromoRedeemIn,
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
        "correct_answers": correct_answers,
        "explanation": current_question["explanation"],
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
    limit: int = Query(default=10, ge=1, le=50),
    conn: Connection = Depends(get_db),
):
    metric_meta = get_metric_meta(metric)
    return {
        "topic": topic,
        "metric": metric if metric in {"best_score", "completed_runs", "coins"} else "best_score",
        "metric_label": metric_meta["label"],
        "scope": metric_meta["scope"],
        "entries": list_leaderboard(conn, topic, metric, limit),
    }


@app.get("/api/admin/questions")
def admin_list_questions(
    topic: str = Query(default=TOPIC_SLUG),
    admin: dict = Depends(require_admin),
    conn: Connection = Depends(get_db),
):
    _ = admin
    normalized_topic = topic.strip().lower()
    ensure_known_topic(normalized_topic)
    return list_admin_questions(conn, normalized_topic)


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
