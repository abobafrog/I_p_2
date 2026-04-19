import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from sqlite3 import Connection
from typing import Dict, List, Optional

from backend.seed_data import SEED_QUESTIONS


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BASE_DIR / "data" / "froggy_coder.db"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_database_path() -> Path:
    override = os.getenv("FROGGY_DB_PATH")
    if override:
        return Path(override)
    return DEFAULT_DB_PATH


def get_connection() -> Connection:
    db_path = get_database_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db():
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    conn = get_connection()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                is_admin INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                type TEXT NOT NULL,
                prompt TEXT NOT NULL,
                explanation TEXT NOT NULL,
                placeholder TEXT,
                order_index INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS question_options (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id INTEGER NOT NULL,
                option_text TEXT NOT NULL,
                is_correct INTEGER NOT NULL DEFAULT 0,
                order_index INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (question_id) REFERENCES questions (id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS question_answers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id INTEGER NOT NULL,
                answer_text TEXT NOT NULL,
                order_index INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (question_id) REFERENCES questions (id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                topic TEXT NOT NULL,
                current_index INTEGER NOT NULL DEFAULT 0,
                current_score INTEGER NOT NULL DEFAULT 0,
                best_score INTEGER NOT NULL DEFAULT 0,
                completed_runs INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL,
                UNIQUE(user_id, topic),
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS question_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                question_id INTEGER NOT NULL,
                submitted_answer TEXT NOT NULL,
                is_correct INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                FOREIGN KEY (question_id) REFERENCES questions (id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS quiz_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                topic TEXT NOT NULL,
                score INTEGER NOT NULL,
                total_questions INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def bootstrap_database(
    admin_username: str,
    admin_password_hash: str,
    admin_password_salt: str,
) -> None:
    conn = get_connection()
    try:
        ensure_default_admin(
            conn,
            username=admin_username,
            password_hash=admin_password_hash,
            password_salt=admin_password_salt,
        )
        ensure_seed_questions(conn)
        conn.commit()
    finally:
        conn.close()


def ensure_default_admin(
    conn: Connection,
    username: str,
    password_hash: str,
    password_salt: str,
) -> None:
    row = conn.execute(
        "SELECT id FROM users WHERE is_admin = 1 LIMIT 1"
    ).fetchone()
    if row is not None:
        return

    conn.execute(
        """
        INSERT INTO users (username, password_hash, password_salt, is_admin, created_at)
        VALUES (?, ?, ?, 1, ?)
        """,
        (username, password_hash, password_salt, utc_now_iso()),
    )


def ensure_seed_questions(conn: Connection) -> None:
    row = conn.execute("SELECT COUNT(*) AS count FROM questions").fetchone()
    if row["count"] > 0:
        return

    for question in SEED_QUESTIONS:
        create_question(conn, question)


def get_user_by_username(conn: Connection, username: str):
    return conn.execute(
        "SELECT * FROM users WHERE lower(username) = lower(?)",
        (username,),
    ).fetchone()


def get_user_by_id(conn: Connection, user_id: int):
    return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def create_user(
    conn: Connection,
    username: str,
    password_hash: str,
    password_salt: str,
    is_admin: bool = False,
):
    cursor = conn.execute(
        """
        INSERT INTO users (username, password_hash, password_salt, is_admin, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (username, password_hash, password_salt, 1 if is_admin else 0, utc_now_iso()),
    )
    conn.commit()
    return get_user_by_id(conn, cursor.lastrowid)


def delete_expired_sessions(conn: Connection) -> None:
    conn.execute(
        "DELETE FROM sessions WHERE expires_at <= ?",
        (utc_now_iso(),),
    )
    conn.commit()


def create_session(conn: Connection, user_id: int, token: str, expires_at: str) -> None:
    conn.execute(
        """
        INSERT INTO sessions (user_id, token, created_at, expires_at)
        VALUES (?, ?, ?, ?)
        """,
        (user_id, token, utc_now_iso(), expires_at),
    )
    conn.commit()


def delete_session(conn: Connection, token: str) -> None:
    conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()


def get_session_user(conn: Connection, token: str):
    return conn.execute(
        """
        SELECT users.*
        FROM sessions
        JOIN users ON users.id = sessions.user_id
        WHERE sessions.token = ? AND sessions.expires_at > ?
        """,
        (token, utc_now_iso()),
    ).fetchone()


def normalize_answer(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def get_topic_questions(conn: Connection, topic: str):
    return conn.execute(
        """
        SELECT *
        FROM questions
        WHERE topic = ?
        ORDER BY order_index ASC, id ASC
        """,
        (topic,),
    ).fetchall()


def get_question_by_index(conn: Connection, topic: str, index: int):
    return conn.execute(
        """
        SELECT *
        FROM questions
        WHERE topic = ?
        ORDER BY order_index ASC, id ASC
        LIMIT 1 OFFSET ?
        """,
        (topic, index),
    ).fetchone()


def get_question_by_id(conn: Connection, question_id: int):
    return conn.execute(
        "SELECT * FROM questions WHERE id = ?",
        (question_id,),
    ).fetchone()


def get_question_options(conn: Connection, question_id: int) -> List[str]:
    rows = conn.execute(
        """
        SELECT option_text
        FROM question_options
        WHERE question_id = ?
        ORDER BY order_index ASC, id ASC
        """,
        (question_id,),
    ).fetchall()
    return [row["option_text"] for row in rows]


def get_correct_answers(conn: Connection, question_id: int, question_type: str) -> List[str]:
    if question_type == "choice":
        rows = conn.execute(
            """
            SELECT option_text
            FROM question_options
            WHERE question_id = ? AND is_correct = 1
            ORDER BY order_index ASC, id ASC
            """,
            (question_id,),
        ).fetchall()
        return [row["option_text"] for row in rows]

    rows = conn.execute(
        """
        SELECT answer_text
        FROM question_answers
        WHERE question_id = ?
        ORDER BY order_index ASC, id ASC
        """,
        (question_id,),
    ).fetchall()
    return [row["answer_text"] for row in rows]


def serialize_public_question(conn: Connection, row) -> Dict:
    return {
        "id": row["id"],
        "topic": row["topic"],
        "type": row["type"],
        "prompt": row["prompt"],
        "options": get_question_options(conn, row["id"]) if row["type"] == "choice" else [],
        "placeholder": row["placeholder"],
        "order_index": row["order_index"],
    }


def serialize_admin_question(conn: Connection, row) -> Dict:
    payload = serialize_public_question(conn, row)
    payload["explanation"] = row["explanation"]
    payload["correct_answers"] = get_correct_answers(conn, row["id"], row["type"])
    return payload


def list_public_questions(conn: Connection, topic: str) -> List[Dict]:
    return [serialize_public_question(conn, row) for row in get_topic_questions(conn, topic)]


def list_admin_questions(conn: Connection, topic: str) -> List[Dict]:
    return [serialize_admin_question(conn, row) for row in get_topic_questions(conn, topic)]


def get_question_count(conn: Connection, topic: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS count FROM questions WHERE topic = ?",
        (topic,),
    ).fetchone()
    return int(row["count"])


def ensure_progress_row(conn: Connection, user_id: int, topic: str):
    row = conn.execute(
        "SELECT * FROM progress WHERE user_id = ? AND topic = ?",
        (user_id, topic),
    ).fetchone()
    if row is not None:
        return clamp_progress_row(conn, row, topic)

    conn.execute(
        """
        INSERT INTO progress (
            user_id, topic, current_index, current_score, best_score, completed_runs, updated_at
        )
        VALUES (?, ?, 0, 0, 0, 0, ?)
        """,
        (user_id, topic, utc_now_iso()),
    )
    conn.commit()
    return conn.execute(
        "SELECT * FROM progress WHERE user_id = ? AND topic = ?",
        (user_id, topic),
    ).fetchone()


def clamp_progress_row(conn: Connection, row, topic: str):
    total_questions = get_question_count(conn, topic)
    current_index = row["current_index"]
    current_score = row["current_score"]
    if total_questions == 0 and (current_index != 0 or current_score != 0):
        conn.execute(
            """
            UPDATE progress
            SET current_index = 0, current_score = 0, updated_at = ?
            WHERE id = ?
            """,
            (utc_now_iso(), row["id"]),
        )
        conn.commit()
    elif total_questions > 0 and current_index > total_questions - 1:
        conn.execute(
            """
            UPDATE progress
            SET current_index = 0, current_score = 0, updated_at = ?
            WHERE id = ?
            """,
            (utc_now_iso(), row["id"]),
        )
        conn.commit()

    return conn.execute("SELECT * FROM progress WHERE id = ?", (row["id"],)).fetchone()


def serialize_progress(conn: Connection, row, topic: str) -> Dict:
    total_questions = get_question_count(conn, topic)
    current_index = row["current_index"]
    if total_questions == 0:
        current_index = 0
    elif current_index > total_questions - 1:
        current_index = 0

    next_question = (
        get_question_by_index(conn, topic, current_index)
        if total_questions > 0 and current_index < total_questions
        else None
    )
    return {
        "topic": topic,
        "current_index": current_index,
        "current_score": row["current_score"],
        "best_score": row["best_score"],
        "completed_runs": row["completed_runs"],
        "total_questions": total_questions,
        "next_question_id": next_question["id"] if next_question is not None else None,
    }


def reset_progress(conn: Connection, user_id: int, topic: str) -> Dict:
    row = ensure_progress_row(conn, user_id, topic)
    conn.execute(
        """
        UPDATE progress
        SET current_index = 0, current_score = 0, updated_at = ?
        WHERE id = ?
        """,
        (utc_now_iso(), row["id"]),
    )
    conn.commit()
    fresh = conn.execute("SELECT * FROM progress WHERE id = ?", (row["id"],)).fetchone()
    return serialize_progress(conn, fresh, topic)


def insert_attempt(
    conn: Connection,
    user_id: int,
    question_id: int,
    submitted_answer: str,
    is_correct: bool,
) -> None:
    conn.execute(
        """
        INSERT INTO question_attempts (user_id, question_id, submitted_answer, is_correct, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, question_id, submitted_answer, 1 if is_correct else 0, utc_now_iso()),
    )


def evaluate_answer(answer: str, correct_answers: List[str]) -> bool:
    normalized_user_answer = normalize_answer(answer)
    return any(normalize_answer(candidate) == normalized_user_answer for candidate in correct_answers)


def apply_answer_result(
    conn: Connection,
    user_id: int,
    topic: str,
    question_id: int,
    submitted_answer: str,
    is_correct: bool,
) -> Dict:
    progress_row = ensure_progress_row(conn, user_id, topic)
    total_questions = get_question_count(conn, topic)

    next_index = progress_row["current_index"] + 1
    next_score = progress_row["current_score"] + (1 if is_correct else 0)

    insert_attempt(conn, user_id, question_id, submitted_answer, is_correct)

    if next_index >= total_questions:
        best_score = max(progress_row["best_score"], next_score)
        conn.execute(
            """
            UPDATE progress
            SET current_index = 0,
                current_score = 0,
                best_score = ?,
                completed_runs = completed_runs + 1,
                updated_at = ?
            WHERE id = ?
            """,
            (best_score, utc_now_iso(), progress_row["id"]),
        )
        conn.execute(
            """
            INSERT INTO quiz_results (user_id, topic, score, total_questions, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, topic, next_score, total_questions, utc_now_iso()),
        )
        conn.commit()
        updated_row = conn.execute(
            "SELECT * FROM progress WHERE id = ?",
            (progress_row["id"],),
        ).fetchone()
        return {
            "quiz_completed": True,
            "final_score": next_score,
            "next_progress": serialize_progress(conn, updated_row, topic),
        }

    conn.execute(
        """
        UPDATE progress
        SET current_index = ?, current_score = ?, updated_at = ?
        WHERE id = ?
        """,
        (next_index, next_score, utc_now_iso(), progress_row["id"]),
    )
    conn.commit()
    updated_row = conn.execute(
        "SELECT * FROM progress WHERE id = ?",
        (progress_row["id"],),
    ).fetchone()
    return {
        "quiz_completed": False,
        "final_score": None,
        "next_progress": serialize_progress(conn, updated_row, topic),
    }


def list_leaderboard(conn: Connection, topic: str, limit: int = 10) -> List[Dict]:
    rows = conn.execute(
        """
        SELECT
            users.username,
            progress.best_score,
            progress.completed_runs,
            MAX(quiz_results.created_at) AS last_played_at
        FROM progress
        JOIN users ON users.id = progress.user_id
        LEFT JOIN quiz_results
            ON quiz_results.user_id = progress.user_id
           AND quiz_results.topic = progress.topic
        WHERE progress.topic = ? AND progress.completed_runs > 0
        GROUP BY users.username, progress.best_score, progress.completed_runs
        ORDER BY progress.best_score DESC, progress.completed_runs DESC, last_played_at DESC
        LIMIT ?
        """,
        (topic, limit),
    ).fetchall()

    entries = []
    for index, row in enumerate(rows, start=1):
        entries.append(
            {
                "rank": index,
                "username": row["username"],
                "best_score": row["best_score"],
                "completed_runs": row["completed_runs"],
                "last_played_at": row["last_played_at"],
            }
        )
    return entries


def create_question(conn: Connection, payload: Dict) -> Dict:
    now = utc_now_iso()
    cursor = conn.execute(
        """
        INSERT INTO questions (topic, type, prompt, explanation, placeholder, order_index, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload["topic"],
            payload["type"],
            payload["prompt"],
            payload["explanation"],
            payload.get("placeholder"),
            payload.get("order_index", 0),
            now,
            now,
        ),
    )
    question_id = cursor.lastrowid

    if payload["type"] == "choice":
        for index, option in enumerate(payload.get("options", [])):
            conn.execute(
                """
                INSERT INTO question_options (question_id, option_text, is_correct, order_index)
                VALUES (?, ?, ?, ?)
                """,
                (
                    question_id,
                    option,
                    1 if option in payload.get("correct_answers", []) else 0,
                    index,
                ),
            )
    else:
        for index, answer in enumerate(payload.get("correct_answers", [])):
            conn.execute(
                """
                INSERT INTO question_answers (question_id, answer_text, order_index)
                VALUES (?, ?, ?)
                """,
                (question_id, answer, index),
            )

    conn.commit()
    row = get_question_by_id(conn, question_id)
    return serialize_admin_question(conn, row)


def update_question(conn: Connection, question_id: int, payload: Dict) -> Dict:
    conn.execute(
        """
        UPDATE questions
        SET topic = ?, type = ?, prompt = ?, explanation = ?, placeholder = ?, order_index = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            payload["topic"],
            payload["type"],
            payload["prompt"],
            payload["explanation"],
            payload.get("placeholder"),
            payload.get("order_index", 0),
            utc_now_iso(),
            question_id,
        ),
    )
    conn.execute("DELETE FROM question_options WHERE question_id = ?", (question_id,))
    conn.execute("DELETE FROM question_answers WHERE question_id = ?", (question_id,))

    if payload["type"] == "choice":
        for index, option in enumerate(payload.get("options", [])):
            conn.execute(
                """
                INSERT INTO question_options (question_id, option_text, is_correct, order_index)
                VALUES (?, ?, ?, ?)
                """,
                (
                    question_id,
                    option,
                    1 if option in payload.get("correct_answers", []) else 0,
                    index,
                ),
            )
    else:
        for index, answer in enumerate(payload.get("correct_answers", [])):
            conn.execute(
                """
                INSERT INTO question_answers (question_id, answer_text, order_index)
                VALUES (?, ?, ?)
                """,
                (question_id, answer, index),
            )

    conn.commit()
    row = get_question_by_id(conn, question_id)
    return serialize_admin_question(conn, row)


def delete_question(conn: Connection, question_id: int) -> None:
    conn.execute("DELETE FROM questions WHERE id = ?", (question_id,))
    conn.commit()
