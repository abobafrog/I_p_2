import os
from typing import Dict

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials
from sqlite3 import Connection, IntegrityError

from backend.auth import (
    bearer_scheme,
    create_session_token,
    hash_password,
    require_admin,
    require_user,
    verify_password,
)
from backend.db import (
    apply_answer_result,
    bootstrap_database,
    create_question,
    create_session,
    create_user,
    delete_question,
    delete_session,
    delete_expired_sessions,
    evaluate_answer,
    get_correct_answers,
    get_db,
    get_question_by_id,
    get_question_by_index,
    get_user_by_id,
    get_user_by_username,
    init_db,
    list_admin_questions,
    list_leaderboard,
    list_public_questions,
    reset_progress,
    serialize_progress,
    update_question,
    ensure_progress_row,
)
from backend.schemas import (
    AdminQuestionIn,
    AnswerResponse,
    AuthResponse,
    BootstrapResponse,
    CredentialsIn,
    LeaderboardResponse,
    ProgressOut,
    SubmitAnswerIn,
    UserOut,
)


TOPIC_SLUG = "python"
DEFAULT_ADMIN_USERNAME = os.getenv("FROGGY_ADMIN_USERNAME", "frog_admin")
DEFAULT_ADMIN_PASSWORD = os.getenv("FROGGY_ADMIN_PASSWORD", "admin12345")

app = FastAPI(
    title="Froggy Coder API",
    version="0.1.0",
    description="Backend API for the Froggy Coder portfolio project.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_origin_regex=r"https://.*\.onrender\.com",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event() -> None:
    init_db()
    admin_salt, admin_hash = hash_password(DEFAULT_ADMIN_PASSWORD)
    bootstrap_database(
        admin_username=DEFAULT_ADMIN_USERNAME,
        admin_password_hash=admin_hash,
        admin_password_salt=admin_salt,
    )


def serialize_user(row) -> Dict:
    return {
        "id": row["id"],
        "username": row["username"],
        "is_admin": bool(row["is_admin"]),
    }


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

    return {
        "topic": topic,
        "type": question_type,
        "prompt": prompt,
        "explanation": explanation,
        "placeholder": placeholder,
        "order_index": payload.order_index,
        "options": options,
        "correct_answers": correct_answers,
    }


@app.get("/api/health")
def healthcheck() -> Dict:
    return {"status": "ok", "topic": TOPIC_SLUG}


@app.post("/api/auth/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: CredentialsIn, conn: Connection = Depends(get_db)):
    cleaned = sanitize_credentials(payload)
    existing = get_user_by_username(conn, cleaned["username"])
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Такой пользователь уже существует.",
        )

    password_salt, password_hash = hash_password(cleaned["password"])

    try:
        user = create_user(
            conn,
            username=cleaned["username"],
            password_hash=password_hash,
            password_salt=password_salt,
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Не удалось создать пользователя.",
        ) from exc

    token, expires_at = create_session_token()
    create_session(conn, user["id"], token, expires_at)
    return {"token": token, "user": serialize_user(user)}


@app.post("/api/auth/login", response_model=AuthResponse)
def login(payload: CredentialsIn, conn: Connection = Depends(get_db)):
    cleaned = sanitize_credentials(payload)
    user = get_user_by_username(conn, cleaned["username"])
    if user is None or not verify_password(
        cleaned["password"],
        user["password_salt"],
        user["password_hash"],
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль.",
        )

    delete_expired_sessions(conn)
    token, expires_at = create_session_token()
    create_session(conn, user["id"], token, expires_at)
    return {"token": token, "user": serialize_user(user)}


@app.get("/api/auth/me", response_model=UserOut)
def me(user: dict = Depends(require_user)):
    return user


@app.post("/api/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    conn: Connection = Depends(get_db),
    user: dict = Depends(require_user),
):
    _ = user
    if credentials is not None and credentials.credentials:
        delete_session(conn, credentials.credentials)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/api/game/bootstrap", response_model=BootstrapResponse)
def game_bootstrap(
    topic: str = Query(default=TOPIC_SLUG),
    user: dict = Depends(require_user),
    conn: Connection = Depends(get_db),
):
    progress_row = ensure_progress_row(conn, user["id"], topic)
    questions = list_public_questions(conn, topic)
    progress = serialize_progress(conn, progress_row, topic)
    return {
        "user": user,
        "questions": questions,
        "progress": progress,
    }


@app.post("/api/game/reset", response_model=ProgressOut)
def reset_game(
    topic: str = Query(default=TOPIC_SLUG),
    user: dict = Depends(require_user),
    conn: Connection = Depends(get_db),
):
    return reset_progress(conn, user["id"], topic)


@app.post("/api/game/submit-answer", response_model=AnswerResponse)
def submit_answer(
    payload: SubmitAnswerIn,
    user: dict = Depends(require_user),
    conn: Connection = Depends(get_db),
):
    topic = payload.topic.strip().lower()
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
        "quiz_completed": result["quiz_completed"],
        "final_score": result["final_score"],
        "total_questions": result["next_progress"]["total_questions"],
    }


@app.get("/api/leaderboard", response_model=LeaderboardResponse)
def leaderboard(
    topic: str = Query(default=TOPIC_SLUG),
    limit: int = Query(default=10, ge=1, le=50),
    conn: Connection = Depends(get_db),
):
    return {
        "topic": topic,
        "entries": list_leaderboard(conn, topic, limit),
    }


@app.get("/api/admin/questions")
def admin_list_questions(
    topic: str = Query(default=TOPIC_SLUG),
    admin: dict = Depends(require_admin),
    conn: Connection = Depends(get_db),
):
    _ = admin
    return list_admin_questions(conn, topic)


@app.post("/api/admin/questions", status_code=status.HTTP_201_CREATED)
def admin_create_question(
    payload: AdminQuestionIn,
    admin: dict = Depends(require_admin),
    conn: Connection = Depends(get_db),
):
    _ = admin
    question = create_question(conn, sanitize_admin_payload(payload))
    return question


@app.put("/api/admin/questions/{question_id}")
def admin_update_question(
    question_id: int,
    payload: AdminQuestionIn,
    admin: dict = Depends(require_admin),
    conn: Connection = Depends(get_db),
):
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
    admin: dict = Depends(require_admin),
    conn: Connection = Depends(get_db),
):
    _ = admin
    row = get_question_by_id(conn, question_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Вопрос не найден.",
        )
    delete_question(conn, question_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
