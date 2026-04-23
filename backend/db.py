from __future__ import annotations

import sqlite3
import json
import re
import secrets
from datetime import datetime, timezone
from itertools import permutations
from pathlib import Path
from sqlite3 import Connection
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.config import get_database_path
from backend.game_meta import LEADERBOARD_METRICS, get_shop_item
from backend.seed_data import (
    AVAILABLE_ROUTES,
    SEED_QUESTIONS,
    get_route_meta,
    get_seed_question,
    get_seed_question_by_order,
    get_seed_question_by_prompt,
)


BASE_DIR = Path(__file__).resolve().parent.parent
QUESTIONS_COLUMN_DEFS = {
    "language": "TEXT NOT NULL DEFAULT ''",
    "difficulty": "TEXT NOT NULL DEFAULT ''",
    "level_index": "INTEGER NOT NULL DEFAULT 0",
    "task_index": "INTEGER NOT NULL DEFAULT 0",
    "hint": "TEXT NOT NULL DEFAULT ''",
}
PROGRESS_COLUMN_DEFS = {
    "max_index": "INTEGER NOT NULL DEFAULT 0",
    "remaining_hearts": "INTEGER NOT NULL DEFAULT 3",
}
USERS_COLUMN_DEFS = {
    "display_name": "TEXT",
    "tag": "TEXT",
    "coins": "INTEGER NOT NULL DEFAULT 0",
    "inventory_json": "TEXT NOT NULL DEFAULT '[\"default\"]'",
    "active_skin": "TEXT NOT NULL DEFAULT 'default'",
    "redeemed_promos_json": "TEXT NOT NULL DEFAULT '[]'",
}
SESSIONS_COLUMN_DEFS = {
    "csrf_token": "TEXT NOT NULL DEFAULT ''",
}
TAG_DIGITS = "0123456789"
TAG_LENGTH = 4
ALL_USER_TAGS = ["".join(chars) for chars in permutations(TAG_DIGITS, TAG_LENGTH)]
PROMO_FROGBEST = "FROGBEST"
PROMO_UNLOCK_REWARD_COINS = 1000
PROMO_SWAMP200 = "SWAMP200"
PROMO_LOTUS500 = "LOTUS500"
DAILY_CHALLENGE_REWARD_COINS = 25
HEARTS_PER_LEVEL = 3
DEFAULT_PROMO_CODES = [
    {
        "code": PROMO_FROGBEST,
        "description": "Открывает все уровни и добавляет 1000 монет.",
        "reward_coins": PROMO_UNLOCK_REWARD_COINS,
        "unlock_all_levels": 1,
        "is_active": 1,
    },
    {
        "code": PROMO_SWAMP200,
        "description": "Небольшой бонус для кошелька: +200 монет.",
        "reward_coins": 200,
        "unlock_all_levels": 0,
        "is_active": 1,
    },
    {
        "code": PROMO_LOTUS500,
        "description": "Редкий бонус: +500 монет без разблокировки уровней.",
        "reward_coins": 500,
        "unlock_all_levels": 0,
        "is_active": 1,
    },
]
SMART_QUOTES_TRANSLATION = str.maketrans(
    {
        "‘": "'",
        "’": "'",
        "‚": "'",
        "`": "'",
        "´": "'",
        "“": '"',
        "”": '"',
        "„": '"',
    }
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_connection() -> Connection:
    db_path = get_database_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
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
                display_name TEXT,
                tag TEXT,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                is_admin INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token TEXT NOT NULL UNIQUE,
                csrf_token TEXT NOT NULL DEFAULT '',
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
                max_index INTEGER NOT NULL DEFAULT 0,
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

            CREATE TABLE IF NOT EXISTS promo_codes (
                code TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                reward_coins INTEGER NOT NULL DEFAULT 0,
                unlock_all_levels INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS promo_redemptions (
                user_id INTEGER NOT NULL,
                code TEXT NOT NULL,
                redeemed_at TEXT NOT NULL,
                PRIMARY KEY (user_id, code),
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                FOREIGN KEY (code) REFERENCES promo_codes (code) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS daily_challenge_attempts (
                challenge_date TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                question_id INTEGER NOT NULL,
                submitted_answer TEXT NOT NULL,
                is_correct INTEGER NOT NULL,
                answered_at TEXT NOT NULL,
                PRIMARY KEY (challenge_date, user_id),
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                FOREIGN KEY (question_id) REFERENCES questions (id) ON DELETE CASCADE
            );

            """
        )
        ensure_user_columns(conn)
        ensure_session_columns(conn)
        ensure_question_columns(conn)
        ensure_progress_columns(conn)
        ensure_user_identity_columns(conn)
        ensure_user_indexes(conn)
        ensure_promo_indexes(conn)
        conn.commit()
    finally:
        conn.close()


def ensure_user_columns(conn: Connection) -> None:
    existing_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()
    }

    for column_name, column_def in USERS_COLUMN_DEFS.items():
        if column_name in existing_columns:
            continue

        conn.execute(
            f"ALTER TABLE users ADD COLUMN {column_name} {column_def}"
        )


def ensure_session_columns(conn: Connection) -> None:
    existing_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()
    }

    for column_name, column_def in SESSIONS_COLUMN_DEFS.items():
        if column_name in existing_columns:
            continue

        conn.execute(
            f"ALTER TABLE sessions ADD COLUMN {column_name} {column_def}"
        )


def ensure_question_columns(conn: Connection) -> None:
    existing_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(questions)").fetchall()
    }

    for column_name, column_def in QUESTIONS_COLUMN_DEFS.items():
        if column_name in existing_columns:
            continue

        conn.execute(
            f"ALTER TABLE questions ADD COLUMN {column_name} {column_def}"
        )


def ensure_progress_columns(conn: Connection) -> None:
    existing_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(progress)").fetchall()
    }

    for column_name, column_def in PROGRESS_COLUMN_DEFS.items():
        if column_name in existing_columns:
            continue

        conn.execute(
            f"ALTER TABLE progress ADD COLUMN {column_name} {column_def}"
        )


def ensure_user_indexes(conn: Connection) -> None:
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_users_tag_unique
        ON users(tag)
        WHERE tag IS NOT NULL AND tag <> ''
        """
    )


def ensure_promo_indexes(conn: Connection) -> None:
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_promo_redemptions_code
        ON promo_redemptions(code)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_daily_challenge_attempts_date
        ON daily_challenge_attempts(challenge_date, answered_at)
        """
    )


def normalize_user_tag(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None

    normalized = str(value).strip()
    return normalized or None


def is_valid_user_tag(value: Optional[str]) -> bool:
    if value is None:
        return False

    return (
        len(value) == TAG_LENGTH
        and value.isdigit()
        and len(set(value)) == TAG_LENGTH
    )


def build_full_username(display_name: str, tag: Optional[str]) -> str:
    return f"{display_name}#{tag}" if tag else display_name


def split_username_and_tag(value: str) -> Tuple[str, Optional[str]]:
    raw_value = (value or "").strip()
    if "#" not in raw_value:
        return raw_value, None

    display_name, possible_tag = raw_value.rsplit("#", 1)
    normalized_display_name = display_name.strip()
    normalized_tag = normalize_user_tag(possible_tag)

    if normalized_display_name and is_valid_user_tag(normalized_tag):
        return normalized_display_name, normalized_tag

    return raw_value, None


def get_taken_user_tags(
    conn: Connection,
    excluded_user_id: Optional[int] = None,
) -> Set[str]:
    query = "SELECT tag FROM users WHERE tag IS NOT NULL AND tag <> ''"
    params: Tuple[object, ...] = ()

    if excluded_user_id is not None:
        query += " AND id != ?"
        params = (excluded_user_id,)

    rows = conn.execute(query, params).fetchall()
    return {
        row["tag"]
        for row in rows
        if row["tag"] and is_valid_user_tag(row["tag"])
    }


def generate_unique_user_tag(
    conn: Connection,
    excluded_user_id: Optional[int] = None,
    reserved_tags: Optional[Set[str]] = None,
) -> str:
    taken_tags = get_taken_user_tags(conn, excluded_user_id)
    if reserved_tags:
        taken_tags.update(reserved_tags)

    available_tags = [tag for tag in ALL_USER_TAGS if tag not in taken_tags]
    if not available_tags:
        raise ValueError("Свободных тэгов больше нет.")

    return secrets.choice(available_tags)


def ensure_user_identity_columns(conn: Connection) -> None:
    rows = conn.execute(
        """
        SELECT id, username, display_name, tag, is_admin
        FROM users
        ORDER BY id ASC
        """
    ).fetchall()

    reserved_tags: Set[str] = set()

    for row in rows:
        parsed_name, parsed_tag = split_username_and_tag(row["username"])
        current_display_name = (row["display_name"] or "").strip()
        next_display_name = current_display_name or parsed_name or row["username"].strip()
        current_tag = normalize_user_tag(row["tag"])
        next_tag = current_tag or parsed_tag

        if next_tag and (not is_valid_user_tag(next_tag) or next_tag in reserved_tags):
            next_tag = None

        if not row["is_admin"] and not next_tag:
            next_tag = generate_unique_user_tag(
                conn,
                excluded_user_id=row["id"],
                reserved_tags=reserved_tags,
            )

        if next_tag:
            reserved_tags.add(next_tag)

        if next_display_name != row["display_name"] or next_tag != current_tag:
            conn.execute(
                """
                UPDATE users
                SET display_name = ?, tag = ?
                WHERE id = ?
                """,
                (next_display_name, next_tag, row["id"]),
            )


def bootstrap_database(
    admin_username: str,
    admin_password: str,
    admin_password_hash: str,
    admin_password_salt: str,
) -> None:
    conn = get_connection()
    try:
        ensure_default_admin(
            conn,
            username=admin_username,
            password=admin_password,
            password_hash=admin_password_hash,
            password_salt=admin_password_salt,
        )
        cleanup_seed_route_duplicates(conn)
        ensure_seed_questions(conn)
        seed_default_promo_codes(conn)
        migrate_legacy_promo_redemptions(conn)
        sync_progress_best_scores(conn)
        conn.commit()
    finally:
        conn.close()


def sync_progress_best_scores(conn: Connection) -> None:
    conn.execute(
        """
        UPDATE progress
        SET best_score = CASE
            WHEN best_score < max_index THEN max_index
            ELSE best_score
        END
        WHERE best_score < max_index
        """
    )


def ensure_default_admin(
    conn: Connection,
    username: str,
    password: str,
    password_hash: str,
    password_salt: str,
) -> None:
    row = conn.execute(
        "SELECT id, password_hash, password_salt FROM users WHERE is_admin = 1 LIMIT 1"
    ).fetchone()
    if row is not None:
        from backend.auth import verify_password

        if not verify_password(password, row["password_salt"], row["password_hash"]):
            conn.execute(
                """
                UPDATE users
                SET password_hash = ?, password_salt = ?
                WHERE id = ?
                """,
                (password_hash, password_salt, row["id"]),
            )
        return

    conn.execute(
        """
        INSERT INTO users (
            username,
            display_name,
            tag,
            password_hash,
            password_salt,
            is_admin,
            created_at
        )
        VALUES (?, ?, NULL, ?, ?, 1, ?)
        """,
        (username, username, password_hash, password_salt, utc_now_iso()),
    )


def seed_default_promo_codes(conn: Connection) -> None:
    for promo in DEFAULT_PROMO_CODES:
        row = conn.execute(
            "SELECT code FROM promo_codes WHERE code = ?",
            (promo["code"],),
        ).fetchone()
        if row is not None:
            continue

        now = utc_now_iso()
        conn.execute(
            """
            INSERT INTO promo_codes (
                code,
                description,
                reward_coins,
                unlock_all_levels,
                is_active,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                promo["code"],
                promo["description"],
                promo["reward_coins"],
                promo["unlock_all_levels"],
                promo["is_active"],
                now,
                now,
            ),
        )


def migrate_legacy_promo_redemptions(conn: Connection) -> None:
    rows = conn.execute(
        """
        SELECT id, redeemed_promos_json
        FROM users
        WHERE redeemed_promos_json IS NOT NULL AND redeemed_promos_json <> ''
        """
    ).fetchall()

    for row in rows:
        for code in parse_redeemed_promos(row["redeemed_promos_json"]):
            promo_row = conn.execute(
                "SELECT code FROM promo_codes WHERE code = ?",
                (code,),
            ).fetchone()
            if promo_row is None:
                continue

            conn.execute(
                """
                INSERT OR IGNORE INTO promo_redemptions (user_id, code, redeemed_at)
                VALUES (?, ?, ?)
                """,
                (row["id"], code, utc_now_iso()),
            )


def cleanup_seed_route_duplicates(conn: Connection) -> None:
    route_topics = tuple(route["topic"] for route in AVAILABLE_ROUTES)
    if not route_topics:
        return

    placeholders = ", ".join("?" for _ in route_topics)
    duplicate_groups = conn.execute(
        f"""
        SELECT topic, order_index, MIN(id) AS keep_id, COUNT(*) AS count
        FROM questions
        WHERE topic IN ({placeholders})
        GROUP BY topic, order_index
        HAVING COUNT(*) > 1
        """,
        route_topics,
    ).fetchall()

    for group in duplicate_groups:
        duplicate_rows = conn.execute(
            """
            SELECT id
            FROM questions
            WHERE topic = ? AND order_index = ? AND id != ?
            """,
            (group["topic"], group["order_index"], group["keep_id"]),
        ).fetchall()

        for row in duplicate_rows:
            conn.execute("DELETE FROM questions WHERE id = ?", (row["id"],))


def ensure_seed_questions(conn: Connection) -> None:
    for question in SEED_QUESTIONS:
        existing_row = conn.execute(
            """
            SELECT id, hint, explanation, placeholder, language, difficulty,
                   order_index, level_index, task_index
            FROM questions
            WHERE topic = ? AND order_index = ?
            LIMIT 1
            """,
            (question["topic"], question["order_index"]),
        ).fetchone()

        if existing_row is None:
            create_question(conn, question)
            continue

        next_hint = existing_row["hint"] or question["hint"]
        next_explanation = existing_row["explanation"] or question["explanation"]
        next_placeholder = (
            existing_row["placeholder"]
            or question["placeholder"]
            or (question["hint"] if question["type"] == "input" else None)
        )
        next_language = existing_row["language"] or question["language"]
        next_difficulty = existing_row["difficulty"] or question["difficulty"]
        next_order_index = (
            existing_row["order_index"]
            if existing_row["order_index"] not in (None, 0)
            else question["order_index"]
        )

        should_update = any(
            [
                existing_row["hint"] != next_hint,
                existing_row["explanation"] != next_explanation,
                existing_row["placeholder"] != next_placeholder,
                existing_row["language"] != next_language,
                existing_row["difficulty"] != next_difficulty,
                existing_row["order_index"] != next_order_index,
                existing_row["level_index"] != question["level_index"],
                existing_row["task_index"] != question["task_index"],
            ]
        )

        if should_update:
            conn.execute(
                """
                UPDATE questions
                SET hint = ?,
                    explanation = ?,
                    placeholder = ?,
                    language = ?,
                    difficulty = ?,
                    level_index = ?,
                    task_index = ?,
                    order_index = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    next_hint,
                    next_explanation,
                    next_placeholder,
                    next_language,
                    next_difficulty,
                    question["level_index"],
                    question["task_index"],
                    next_order_index,
                    utc_now_iso(),
                    existing_row["id"],
                ),
            )


def get_user_by_username(conn: Connection, username: str):
    return conn.execute(
        "SELECT * FROM users WHERE lower(username) = lower(?)",
        (username,),
    ).fetchone()


def get_user_by_display_name_and_tag(conn: Connection, display_name: str, tag: str):
    return conn.execute(
        """
        SELECT *
        FROM users
        WHERE lower(COALESCE(NULLIF(display_name, ''), username)) = lower(?)
          AND tag = ?
        """,
        (display_name, tag),
    ).fetchone()


def get_user_by_id(conn: Connection, user_id: int):
    return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def parse_inventory(raw_value: Optional[str]) -> List[str]:
    if not raw_value:
        return ["default"]

    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        return ["default"]

    if not isinstance(parsed, list):
        return ["default"]

    items = [str(item).strip() for item in parsed if str(item).strip()]
    if "default" not in items:
        items.insert(0, "default")
    return items or ["default"]


def parse_redeemed_promos(raw_value: Optional[str]) -> List[str]:
    if not raw_value:
        return []

    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        return []

    if not isinstance(parsed, list):
        return []

    promos = []
    for item in parsed:
        normalized = str(item).strip().upper()
        if normalized and normalized not in promos:
            promos.append(normalized)
    return promos
def serialize_user_row(row) -> Dict:
    inventory = parse_inventory(row["inventory_json"])
    active_skin = row["active_skin"] if row["active_skin"] in inventory else "default"
    active_item = get_shop_item(active_skin) or get_shop_item("default") or {
        "name": "Обычная лягушка",
        "icon": "🐸",
    }
    display_name = (row["display_name"] or "").strip() or row["username"]
    tag = normalize_user_tag(row["tag"])

    return {
        "id": row["id"],
        "username": display_name,
        "tag": tag,
        "full_username": build_full_username(display_name, tag),
        "is_admin": bool(row["is_admin"]),
        "coins": row["coins"],
        "inventory": inventory,
        "active_skin": active_skin,
        "active_skin_label": active_item["name"],
        "active_skin_icon": active_item["icon"],
    }


def get_user_shop_state(conn: Connection, user_id: int) -> Dict:
    row = get_user_by_id(conn, user_id)
    if row is None:
        raise ValueError("User not found")
    return serialize_user_row(row)


def buy_or_equip_item(conn: Connection, user_id: int, item_id: str) -> Dict:
    item = get_shop_item(item_id)
    if item is None:
        raise ValueError("Item not found")

    row = get_user_by_id(conn, user_id)
    if row is None:
        raise ValueError("User not found")

    inventory = parse_inventory(row["inventory_json"])
    coins = row["coins"]
    purchased = False

    if item_id not in inventory:
        if item["price"] > coins:
            raise PermissionError("Недостаточно монет для покупки.")
        inventory.append(item_id)
        coins -= item["price"]
        purchased = True

    conn.execute(
        """
        UPDATE users
        SET coins = ?, inventory_json = ?, active_skin = ?
        WHERE id = ?
        """,
        (coins, json.dumps(inventory, ensure_ascii=False), item_id, user_id),
    )
    conn.commit()

    updated = get_user_by_id(conn, user_id)
    return {
        "user": serialize_user_row(updated),
        "purchased": purchased,
        "item": item,
    }


def create_user(
    conn: Connection,
    username: str,
    display_name: str,
    tag: Optional[str],
    password_hash: str,
    password_salt: str,
    is_admin: bool = False,
):
    cursor = conn.execute(
        """
        INSERT INTO users (
            username,
            display_name,
            tag,
            password_hash,
            password_salt,
            is_admin,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            username,
            display_name,
            tag,
            password_hash,
            password_salt,
            1 if is_admin else 0,
            utc_now_iso(),
        ),
    )
    conn.commit()
    return get_user_by_id(conn, cursor.lastrowid)


def create_user_with_generated_tag(
    conn: Connection,
    display_name: str,
    password_hash: str,
    password_salt: str,
    max_attempts: int = 5,
):
    for _ in range(max_attempts):
        try:
            conn.execute("BEGIN IMMEDIATE")
            tag = generate_unique_user_tag(conn)
            login_handle = build_full_username(display_name, tag)
            cursor = conn.execute(
                """
                INSERT INTO users (
                    username,
                    display_name,
                    tag,
                    password_hash,
                    password_salt,
                    is_admin,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, 0, ?)
                """,
                (
                    login_handle,
                    display_name,
                    tag,
                    password_hash,
                    password_salt,
                    utc_now_iso(),
                ),
            )
            conn.commit()
            return get_user_by_id(conn, cursor.lastrowid)
        except sqlite3.IntegrityError:
            conn.rollback()

    raise sqlite3.IntegrityError("Could not allocate a unique user tag after retries.")


def update_user_profile(
    conn: Connection,
    user_id: int,
    display_name: str,
    password_hash: str,
    password_salt: str,
):
    row = get_user_by_id(conn, user_id)
    if row is None:
        raise ValueError("User not found")

    login_handle = build_full_username(display_name, normalize_user_tag(row["tag"]))
    conn.execute(
        """
        UPDATE users
        SET username = ?,
            display_name = ?,
            password_hash = ?,
            password_salt = ?
        WHERE id = ?
        """,
        (login_handle, display_name, password_hash, password_salt, user_id),
    )
    conn.commit()
    return get_user_by_id(conn, user_id)


def list_user_progress(conn: Connection, user_id: int) -> List[Dict]:
    progress_items = []
    for route in list_route_options(conn, user_id):
        topic = route["topic"]
        row = ensure_progress_row(conn, user_id, topic)
        progress_items.append(serialize_progress(conn, row, topic))
    return progress_items


def serialize_promo_row(conn: Connection, row) -> Dict:
    redemptions_row = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM promo_redemptions
        WHERE code = ?
        """,
        (row["code"],),
    ).fetchone()

    return {
        "code": row["code"],
        "description": row["description"],
        "reward_coins": row["reward_coins"],
        "unlock_all_levels": bool(row["unlock_all_levels"]),
        "is_active": bool(row["is_active"]),
        "redemptions_count": int(redemptions_row["count"]),
    }


def list_promo_codes(conn: Connection) -> List[Dict]:
    rows = conn.execute(
        """
        SELECT *
        FROM promo_codes
        ORDER BY is_active DESC, code ASC
        """
    ).fetchall()
    return [serialize_promo_row(conn, row) for row in rows]


def get_promo_code(conn: Connection, code: str):
    return conn.execute(
        """
        SELECT *
        FROM promo_codes
        WHERE upper(code) = upper(?)
        """,
        (code,),
    ).fetchone()


def sync_legacy_redeemed_promos_json(conn: Connection, user_id: int, code: str) -> None:
    user_row = get_user_by_id(conn, user_id)
    if user_row is None:
        raise ValueError("User not found")

    redeemed_promos = parse_redeemed_promos(user_row["redeemed_promos_json"])
    if code not in redeemed_promos:
        redeemed_promos.append(code)
        conn.execute(
            """
            UPDATE users
            SET redeemed_promos_json = ?
            WHERE id = ?
            """,
            (json.dumps(redeemed_promos, ensure_ascii=False), user_id),
        )


def unlock_all_route_levels(conn: Connection, user_id: int) -> None:
    for route in list_route_options(conn, user_id):
        topic = route["topic"]
        row = ensure_progress_row(conn, user_id, topic)
        total_questions = get_question_count(conn, topic)
        if total_questions <= 0:
            continue

        conn.execute(
            """
            UPDATE progress
            SET max_index = CASE WHEN max_index < ? THEN ? ELSE max_index END,
                best_score = CASE WHEN best_score < ? THEN ? ELSE best_score END,
                updated_at = ?
            WHERE id = ?
            """,
            (
                total_questions,
                total_questions,
                total_questions,
                total_questions,
                utc_now_iso(),
                row["id"],
            ),
        )


def upsert_promo_code(conn: Connection, payload: Dict) -> Dict:
    normalized_code = payload["code"].strip().upper()
    now = utc_now_iso()
    existing_row = get_promo_code(conn, normalized_code)

    if existing_row is None:
        conn.execute(
            """
            INSERT INTO promo_codes (
                code,
                description,
                reward_coins,
                unlock_all_levels,
                is_active,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                normalized_code,
                payload["description"],
                payload["reward_coins"],
                1 if payload["unlock_all_levels"] else 0,
                1 if payload["is_active"] else 0,
                now,
                now,
            ),
        )
    else:
        conn.execute(
            """
            UPDATE promo_codes
            SET description = ?,
                reward_coins = ?,
                unlock_all_levels = ?,
                is_active = ?,
                updated_at = ?
            WHERE code = ?
            """,
            (
                payload["description"],
                payload["reward_coins"],
                1 if payload["unlock_all_levels"] else 0,
                1 if payload["is_active"] else 0,
                now,
                normalized_code,
            ),
        )

    conn.commit()
    row = get_promo_code(conn, normalized_code)
    return serialize_promo_row(conn, row)


def delete_promo_code_record(conn: Connection, code: str) -> None:
    conn.execute(
        "DELETE FROM promo_codes WHERE upper(code) = upper(?)",
        (code,),
    )
    conn.commit()


def redeem_promo_code(conn: Connection, user_id: int, code: str) -> Dict:
    normalized_code = (code or "").strip().upper()
    promo_row = get_promo_code(conn, normalized_code)
    if promo_row is None or not bool(promo_row["is_active"]):
        raise ValueError("Промокод не найден.")

    user_row = get_user_by_id(conn, user_id)
    if user_row is None:
        raise ValueError("User not found")

    redemption_row = conn.execute(
        """
        SELECT 1
        FROM promo_redemptions
        WHERE user_id = ? AND code = ?
        """,
        (user_id, normalized_code),
    ).fetchone()
    if redemption_row is not None:
        raise PermissionError("Этот промокод уже активирован.")

    conn.execute(
        """
        INSERT INTO promo_redemptions (user_id, code, redeemed_at)
        VALUES (?, ?, ?)
        """,
        (user_id, normalized_code, utc_now_iso()),
    )
    sync_legacy_redeemed_promos_json(conn, user_id, normalized_code)

    if promo_row["reward_coins"] > 0:
        conn.execute(
            """
            UPDATE users
            SET coins = coins + ?
            WHERE id = ?
            """,
            (promo_row["reward_coins"], user_id),
        )

    if bool(promo_row["unlock_all_levels"]):
        unlock_all_route_levels(conn, user_id)

    conn.commit()
    updated_user = get_user_by_id(conn, user_id)
    message_parts = []
    if promo_row["reward_coins"] > 0:
        message_parts.append(f"+{promo_row['reward_coins']} монет")
    if bool(promo_row["unlock_all_levels"]):
        message_parts.append("все уровни открыты")
    message_suffix = ", ".join(message_parts) if message_parts else "бонус применен"
    return {
        "user": serialize_user_row(updated_user),
        "progresses": list_user_progress(conn, user_id),
        "message": f"Промокод {normalized_code} активирован: {message_suffix}.",
    }


def get_daily_challenge_date() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def get_daily_challenge_row(conn: Connection, challenge_date: Optional[str] = None):
    target_date = challenge_date or get_daily_challenge_date()
    rows = conn.execute(
        """
        SELECT *
        FROM questions
        ORDER BY topic ASC, order_index ASC, id ASC
        """
    ).fetchall()
    if not rows:
        return None, target_date

    seed_value = sum(target_date.encode("utf-8"))
    index = seed_value % len(rows)
    return rows[index], target_date


def get_daily_challenge_attempt(conn: Connection, user_id: int, challenge_date: str):
    return conn.execute(
        """
        SELECT *
        FROM daily_challenge_attempts
        WHERE user_id = ? AND challenge_date = ?
        """,
        (user_id, challenge_date),
    ).fetchone()


def list_daily_challenge_leaderboard(conn: Connection, challenge_date: Optional[str] = None) -> List[Dict]:
    target_date = challenge_date or get_daily_challenge_date()
    rows = conn.execute(
        """
        SELECT
            users.username,
            users.display_name,
            users.tag,
            attempts.is_correct,
            attempts.answered_at
        FROM daily_challenge_attempts AS attempts
        JOIN users ON users.id = attempts.user_id
        WHERE attempts.challenge_date = ?
          AND attempts.is_correct = 1
          AND users.is_admin = 0
        ORDER BY attempts.answered_at ASC, users.username ASC
        LIMIT 25
        """,
        (target_date,),
    ).fetchall()

    items = []
    for index, row in enumerate(rows, start=1):
        display_name = (row["display_name"] or "").strip() or row["username"]
        items.append(
            {
                "rank": index,
                "username": display_name,
                "tag": normalize_user_tag(row["tag"]),
                "full_username": build_full_username(display_name, normalize_user_tag(row["tag"])),
                "is_correct": bool(row["is_correct"]),
                "answered_at": row["answered_at"],
            }
        )

    return items


def submit_daily_challenge_answer(conn: Connection, user_id: int, answer: str) -> Dict:
    question_row, challenge_date = get_daily_challenge_row(conn)
    if question_row is None:
        raise ValueError("Daily challenge question not found")

    existing_attempt = get_daily_challenge_attempt(conn, user_id, challenge_date)
    if existing_attempt is not None:
        raise PermissionError("Ежедневный вопрос уже отвечен.")

    correct_answers = get_correct_answers(conn, question_row["id"], question_row["type"])
    is_correct = evaluate_answer(answer, correct_answers)
    answered_at = utc_now_iso()

    conn.execute(
        """
        INSERT INTO daily_challenge_attempts (
            challenge_date,
            user_id,
            question_id,
            submitted_answer,
            is_correct,
            answered_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            challenge_date,
            user_id,
            question_row["id"],
            answer,
            1 if is_correct else 0,
            answered_at,
        ),
    )

    reward_coins = DAILY_CHALLENGE_REWARD_COINS if is_correct else 0
    if reward_coins > 0:
        conn.execute(
            """
            UPDATE users
            SET coins = coins + ?
            WHERE id = ?
            """,
            (reward_coins, user_id),
        )

    conn.commit()
    updated_user = get_user_by_id(conn, user_id)
    return {
        "challenge_date": challenge_date,
        "question": serialize_public_question(conn, question_row),
        "is_correct": is_correct,
        "correct_answers": correct_answers,
        "explanation": normalize_question_explanation(question_row["explanation"]),
        "reward_coins": reward_coins,
        "answered_at": answered_at,
        "user": serialize_user_row(updated_user),
        "leaderboard": list_daily_challenge_leaderboard(conn, challenge_date),
    }


def delete_expired_sessions(conn: Connection) -> None:
    conn.execute(
        "DELETE FROM sessions WHERE expires_at <= ?",
        (utc_now_iso(),),
    )
    conn.commit()


def create_session(
    conn: Connection,
    user_id: int,
    token: str,
    csrf_token: str,
    expires_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO sessions (user_id, token, csrf_token, created_at, expires_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, token, csrf_token, utc_now_iso(), expires_at),
    )
    conn.commit()


def delete_session(conn: Connection, token: str) -> None:
    conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()


def get_session_record(conn: Connection, token: str):
    return conn.execute(
        """
        SELECT
            sessions.token AS session_token,
            sessions.csrf_token AS session_csrf_token,
            sessions.expires_at AS session_expires_at,
            users.*
        FROM sessions
        JOIN users ON users.id = sessions.user_id
        WHERE sessions.token = ? AND sessions.expires_at > ?
        """,
        (token, utc_now_iso()),
    ).fetchone()


def get_session_user(conn: Connection, token: str):
    session = get_session_record(conn, token)
    return session


def normalize_answer(value: str) -> str:
    normalized = " ".join((value or "").strip().lower().split())
    return normalized.translate(SMART_QUOTES_TRANSLATION)


def normalize_code_answer(value: str) -> str:
    normalized = normalize_answer(value)
    return re.sub(r"\s*([,.\[\]\(\)\{\}:+\-*/%=<>])\s*", r"\1", normalized)


def get_topic_questions(conn: Connection, topic: str):
    return conn.execute(
        """
        SELECT *
        FROM questions
        WHERE topic = ?
        ORDER BY level_index ASC, task_index ASC, order_index ASC, id ASC
        """,
        (topic,),
    ).fetchall()


def get_question_by_index(conn: Connection, topic: str, index: int):
    return conn.execute(
        """
        SELECT *
        FROM questions
        WHERE topic = ?
        ORDER BY level_index ASC, task_index ASC, order_index ASC, id ASC
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


def derive_hint_text(row) -> str:
    if row["hint"]:
        return row["hint"]

    seed_question = (
        get_seed_question(row["topic"], row["level_index"], row["task_index"])
        or get_seed_question_by_order(row["topic"], row["order_index"])
        or get_seed_question_by_prompt(row["topic"], row["prompt"])
    )
    if seed_question is not None and seed_question["hint"]:
        return seed_question["hint"]

    explanation = row["explanation"] or ""
    prefix = "Подсказка из desktop-версии: "
    if explanation.startswith(prefix):
        return explanation[len(prefix):]
    return explanation


def normalize_question_explanation(value: Optional[str]) -> str:
    explanation = (value or "").strip()
    prefix = "Подсказка из desktop-версии: "
    if explanation.startswith(prefix):
        return explanation[len(prefix):]
    return explanation


def serialize_public_question(conn: Connection, row) -> Dict:
    hint_text = derive_hint_text(row)
    return {
        "id": row["id"],
        "topic": row["topic"],
        "language": row["language"],
        "difficulty": row["difficulty"],
        "level_index": row["level_index"],
        "task_index": row["task_index"],
        "type": row["type"],
        "prompt": row["prompt"],
        "options": get_question_options(conn, row["id"]) if row["type"] == "choice" else [],
        "placeholder": row["placeholder"] or (hint_text if row["type"] == "input" else None),
        "hint": hint_text,
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


def get_route_question_stats(conn: Connection, topic: str):
    return conn.execute(
        """
        SELECT
            MAX(level_index) AS max_level_index,
            MAX(task_index) AS max_task_index
        FROM questions
        WHERE topic = ?
        """,
        (topic,),
    ).fetchone()


def list_route_options(conn: Connection, user_id: int | None = None) -> List[Dict]:
    items: List[Dict] = []
    for route in AVAILABLE_ROUTES:
        topic = route["topic"]
        total_questions = get_question_count(conn, topic)
        route_shape = get_route_shape(conn, topic, total_questions)

        items.append(
            {
                "topic": topic,
                "language": route["language"],
                "difficulty": route["difficulty"],
                "difficulty_label": route["difficulty_label"],
                "levels_total": route_shape["levels_total"],
                "questions_total": total_questions,
                "tasks_per_level": route_shape["tasks_per_level"],
            }
        )
    return items


def can_user_access_topic(user_id: int, topic: str) -> bool:
    _ = user_id
    return get_route_meta(topic) is not None


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
            user_id,
            topic,
            current_index,
            current_score,
            max_index,
            remaining_hearts,
            best_score,
            completed_runs,
            updated_at
        )
        VALUES (?, ?, 0, 0, 0, ?, 0, 0, ?)
        """,
        (user_id, topic, HEARTS_PER_LEVEL, utc_now_iso()),
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
    if total_questions == 0 and (
        current_index != 0
        or current_score != 0
        or row["remaining_hearts"] != HEARTS_PER_LEVEL
    ):
        conn.execute(
            """
            UPDATE progress
            SET current_index = 0,
                current_score = 0,
                remaining_hearts = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (HEARTS_PER_LEVEL, utc_now_iso(), row["id"]),
        )
        conn.commit()
    elif total_questions > 0 and current_index > total_questions - 1:
        conn.execute(
            """
            UPDATE progress
            SET current_index = 0,
                current_score = 0,
                remaining_hearts = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (HEARTS_PER_LEVEL, utc_now_iso(), row["id"]),
        )
        conn.commit()

    return conn.execute("SELECT * FROM progress WHERE id = ?", (row["id"],)).fetchone()


def get_route_shape(conn: Connection, topic: str, total_questions: int) -> Dict:
    route_meta = get_route_meta(topic)
    default_levels_total = route_meta["levels_total"] if route_meta is not None else 5
    default_tasks_per_level = route_meta.get("tasks_per_level", 5) if route_meta is not None else 5
    question_stats = get_route_question_stats(conn, topic)
    max_level_index = question_stats["max_level_index"]
    max_task_index = question_stats["max_task_index"]

    if total_questions > 0 and max_level_index is not None:
        populated_levels_total = int(max_level_index) + 1
        levels_total = max(default_levels_total, populated_levels_total)
    else:
        levels_total = default_levels_total

    if total_questions > 0 and max_task_index is not None:
        tasks_per_level = max(1, int(max_task_index) + 1)
    else:
        tasks_per_level = default_tasks_per_level

    return {
        "levels_total": levels_total,
        "tasks_per_level": tasks_per_level,
    }


def serialize_progress(conn: Connection, row, topic: str) -> Dict:
    total_questions = get_question_count(conn, topic)
    route_shape = get_route_shape(conn, topic, total_questions)
    current_index = row["current_index"]
    max_index = row["max_index"]
    if total_questions == 0:
        current_index = 0
        max_index = 0
    elif current_index > total_questions - 1:
        current_index = 0
    if max_index > total_questions:
        max_index = total_questions

    next_question = (
        get_question_by_index(conn, topic, current_index)
        if total_questions > 0 and current_index < total_questions
        else None
    )
    current_level_index = (
        min(current_index // route_shape["tasks_per_level"], route_shape["levels_total"] - 1)
        if total_questions > 0 and route_shape["levels_total"] > 0
        else 0
    )
    current_task_index = (
        current_index % route_shape["tasks_per_level"]
        if total_questions > 0
        else 0
    )
    unlocked_level_index = (
        route_shape["levels_total"] - 1
        if total_questions > 0 and max_index >= total_questions
        else min(max_index // route_shape["tasks_per_level"], route_shape["levels_total"] - 1)
        if total_questions > 0 and route_shape["levels_total"] > 0
        else 0
    )
    remaining_hearts = row["remaining_hearts"]
    if remaining_hearts < 0 or remaining_hearts > HEARTS_PER_LEVEL:
        remaining_hearts = HEARTS_PER_LEVEL
    return {
        "topic": topic,
        "current_index": current_index,
        "current_score": row["current_score"],
        "opened_questions": min(max_index, total_questions),
        "best_score": row["best_score"],
        "completed_runs": row["completed_runs"],
        "remaining_hearts": remaining_hearts,
        "total_questions": total_questions,
        "levels_total": route_shape["levels_total"],
        "tasks_per_level": route_shape["tasks_per_level"],
        "current_level_index": current_level_index,
        "current_task_index": current_task_index,
        "unlocked_level_index": unlocked_level_index,
        "next_question_id": next_question["id"] if next_question is not None else None,
    }


def reset_progress(conn: Connection, user_id: int, topic: str) -> Dict:
    row = ensure_progress_row(conn, user_id, topic)
    conn.execute(
        """
        UPDATE progress
        SET current_index = 0,
            current_score = 0,
            max_index = 0,
            remaining_hearts = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (HEARTS_PER_LEVEL, utc_now_iso(), row["id"]),
    )
    conn.commit()
    fresh = conn.execute("SELECT * FROM progress WHERE id = ?", (row["id"],)).fetchone()
    return serialize_progress(conn, fresh, topic)


def reset_all_progress(conn: Connection, user_id: int) -> List[Dict]:
    route_topics = [route["topic"] for route in list_route_options(conn, user_id)]
    if route_topics:
        placeholders = ", ".join("?" for _ in route_topics)
        conn.execute(
            f"""
            DELETE FROM progress
            WHERE user_id = ? AND topic IN ({placeholders})
            """,
            (user_id, *route_topics),
        )
        conn.commit()

    return list_user_progress(conn, user_id)


def replace_topic_questions(
    conn: Connection,
    *,
    topic: str,
    user_id: int | None = None,
) -> None:
    conn.execute("DELETE FROM questions WHERE topic = ?", (topic,))
    if user_id is None:
        conn.execute("DELETE FROM progress WHERE topic = ?", (topic,))
        conn.execute("DELETE FROM quiz_results WHERE topic = ?", (topic,))
    else:
        conn.execute(
            "DELETE FROM progress WHERE user_id = ? AND topic = ?",
            (user_id, topic),
        )
        conn.execute(
            "DELETE FROM quiz_results WHERE user_id = ? AND topic = ?",
            (user_id, topic),
        )
    conn.commit()


def select_level_progress(conn: Connection, user_id: int, topic: str, level_index: int) -> Dict:
    row = ensure_progress_row(conn, user_id, topic)
    total_questions = get_question_count(conn, topic)
    route_shape = get_route_shape(conn, topic, total_questions)
    max_level_index = max(route_shape["levels_total"] - 1, 0)
    selected_level = max(0, min(level_index, max_level_index))
    selected_index = selected_level * route_shape["tasks_per_level"]

    conn.execute(
        """
        UPDATE progress
        SET current_index = ?,
            current_score = ?,
            remaining_hearts = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (selected_index, selected_index, HEARTS_PER_LEVEL, utc_now_iso(), row["id"]),
    )
    conn.commit()
    fresh = conn.execute("SELECT * FROM progress WHERE id = ?", (row["id"],)).fetchone()
    return serialize_progress(conn, fresh, topic)


def reset_level_progress(conn: Connection, user_id: int, topic: str) -> Dict:
    row = ensure_progress_row(conn, user_id, topic)
    total_questions = get_question_count(conn, topic)
    route_shape = get_route_shape(conn, topic, total_questions)
    current_index = row["current_index"]
    level_start_index = (
        (current_index // route_shape["tasks_per_level"]) * route_shape["tasks_per_level"]
        if route_shape["tasks_per_level"] > 0
        else 0
    )

    conn.execute(
        """
        UPDATE progress
        SET current_index = ?,
            current_score = ?,
            remaining_hearts = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (level_start_index, level_start_index, HEARTS_PER_LEVEL, utc_now_iso(), row["id"]),
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


def award_coins(conn: Connection, user_id: int, amount: int) -> None:
    if amount <= 0:
        return

    conn.execute(
        "UPDATE users SET coins = coins + ? WHERE id = ?",
        (amount, user_id),
    )


def evaluate_answer(answer: str, correct_answers: List[str]) -> bool:
    normalized_user_answer = normalize_answer(answer)
    normalized_code_answer = normalize_code_answer(answer)
    return any(
        normalize_answer(candidate) == normalized_user_answer
        or normalize_code_answer(candidate) == normalized_code_answer
        for candidate in correct_answers
    )


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
    route_shape = get_route_shape(conn, topic, total_questions)
    coins_awarded = 10 if is_correct else 0

    # All writes in this function stay within the same transaction and are committed once.
    insert_attempt(conn, user_id, question_id, submitted_answer, is_correct)

    if not is_correct:
        remaining_hearts = max(0, min(progress_row["remaining_hearts"], HEARTS_PER_LEVEL) - 1)
        conn.execute(
            """
            UPDATE progress
            SET remaining_hearts = ?, updated_at = ?
            WHERE id = ?
            """,
            (remaining_hearts, utc_now_iso(), progress_row["id"]),
        )
        conn.commit()
        updated_row = conn.execute(
            "SELECT * FROM progress WHERE id = ?",
            (progress_row["id"],),
        ).fetchone()
        return {
            "quiz_completed": False,
            "final_score": None,
            "coins_awarded": 0,
            "next_progress": serialize_progress(conn, updated_row, topic),
        }

    next_index = progress_row["current_index"] + 1
    next_score = progress_row["current_score"] + 1
    next_max_index = max(progress_row["max_index"], next_index)
    next_best_score = max(progress_row["best_score"], next_max_index)
    current_level_index = (
        progress_row["current_index"] // route_shape["tasks_per_level"]
        if route_shape["tasks_per_level"] > 0
        else 0
    )
    if coins_awarded > 0:
        award_coins(conn, user_id, coins_awarded)

    if next_index >= total_questions:
        conn.execute(
            """
            UPDATE progress
            SET current_index = 0,
                current_score = 0,
                max_index = ?,
                remaining_hearts = ?,
                best_score = ?,
                completed_runs = completed_runs + 1,
                updated_at = ?
            WHERE id = ?
            """,
            (
                total_questions,
                HEARTS_PER_LEVEL,
                next_best_score,
                utc_now_iso(),
                progress_row["id"],
            ),
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
            "coins_awarded": coins_awarded,
            "next_progress": serialize_progress(conn, updated_row, topic),
        }

    next_level_index = (
        next_index // route_shape["tasks_per_level"]
        if route_shape["tasks_per_level"] > 0
        else current_level_index
    )
    next_remaining_hearts = (
        HEARTS_PER_LEVEL
        if next_level_index != current_level_index
        else max(1, min(progress_row["remaining_hearts"], HEARTS_PER_LEVEL))
    )

    conn.execute(
        """
        UPDATE progress
        SET current_index = ?,
            current_score = ?,
            max_index = ?,
            best_score = ?,
            remaining_hearts = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            next_index,
            next_score,
            next_max_index,
            next_best_score,
            next_remaining_hearts,
            utc_now_iso(),
            progress_row["id"],
        ),
    )
    conn.commit()
    updated_row = conn.execute(
        "SELECT * FROM progress WHERE id = ?",
        (progress_row["id"],),
    ).fetchone()
    return {
        "quiz_completed": False,
        "final_score": None,
        "coins_awarded": coins_awarded,
        "next_progress": serialize_progress(conn, updated_row, topic),
    }


def list_leaderboard(
    conn: Connection,
    topic: str,
    metric: str = "best_score",
    limit: int = 10,
) -> List[Dict]:
    metric_key = metric if metric in LEADERBOARD_METRICS else "best_score"

    if metric_key == "coins":
        rows = conn.execute(
            """
            SELECT
                users.username,
                users.display_name,
                users.tag,
                users.coins,
                progress.best_score,
                progress.completed_runs,
                COALESCE(attempt_stats.topic_coins, 0) AS topic_coins,
                result_stats.last_played_at AS last_played_at
            FROM progress
            JOIN users ON users.id = progress.user_id
            LEFT JOIN (
                SELECT
                    question_attempts.user_id AS user_id,
                    questions.topic AS topic,
                    SUM(CASE WHEN question_attempts.is_correct = 1 THEN 10 ELSE 0 END) AS topic_coins
                FROM question_attempts
                JOIN questions ON questions.id = question_attempts.question_id
                GROUP BY question_attempts.user_id, questions.topic
            ) AS attempt_stats
                ON attempt_stats.user_id = progress.user_id
               AND attempt_stats.topic = progress.topic
            LEFT JOIN (
                SELECT
                    user_id,
                    topic,
                    MAX(created_at) AS last_played_at
                FROM quiz_results
                GROUP BY user_id, topic
            ) AS result_stats
                ON result_stats.user_id = progress.user_id
               AND result_stats.topic = progress.topic
            WHERE progress.topic = ? AND users.is_admin = 0
              AND (
                    COALESCE(attempt_stats.topic_coins, 0) > 0
                 OR progress.best_score > 0
                 OR progress.completed_runs > 0
              )
            ORDER BY topic_coins DESC, progress.completed_runs DESC, last_played_at DESC, users.username ASC
            LIMIT ?
            """,
            (topic, limit),
        ).fetchall()
    else:
        order_by = (
            "progress.completed_runs DESC, last_played_at DESC, progress.best_score DESC, users.username ASC"
            if metric_key == "completed_runs"
            else "progress.best_score DESC, progress.completed_runs DESC, last_played_at DESC, users.username ASC"
        )
        rows = conn.execute(
            f"""
            SELECT
                users.username,
                users.display_name,
                users.tag,
                users.coins,
                progress.best_score,
                progress.completed_runs,
                MAX(quiz_results.created_at) AS last_played_at
            FROM progress
            JOIN users ON users.id = progress.user_id
            LEFT JOIN quiz_results
                ON quiz_results.user_id = progress.user_id
               AND quiz_results.topic = progress.topic
            WHERE progress.topic = ? AND users.is_admin = 0
              AND (progress.best_score > 0 OR progress.completed_runs > 0)
            GROUP BY
                users.id,
                users.username,
                users.display_name,
                users.tag,
                users.coins,
                progress.best_score,
                progress.completed_runs
            ORDER BY {order_by}
            LIMIT ?
            """,
            (topic, limit),
        ).fetchall()

    entries = []
    for index, row in enumerate(rows, start=1):
        metric_value = (
            row["topic_coins"]
            if metric_key == "coins"
            else row["completed_runs"]
            if metric_key == "completed_runs"
            else row["best_score"]
        )
        entries.append(
            {
                "rank": index,
                "username": (row["display_name"] or "").strip() or row["username"],
                "tag": normalize_user_tag(row["tag"]),
                "full_username": build_full_username(
                    (row["display_name"] or "").strip() or row["username"],
                    normalize_user_tag(row["tag"]),
                ),
                "metric_value": metric_value,
                "best_score": row["best_score"],
                "completed_runs": row["completed_runs"],
                "coins": row["coins"],
                "last_played_at": row["last_played_at"],
            }
        )
    return entries


def create_question(conn: Connection, payload: Dict) -> Dict:
    now = utc_now_iso()
    cursor = conn.execute(
        """
        INSERT INTO questions (
            topic,
            language,
            difficulty,
            level_index,
            task_index,
            type,
            prompt,
            explanation,
            placeholder,
            hint,
            order_index,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload["topic"],
            payload.get("language", ""),
            payload.get("difficulty", ""),
            payload.get("level_index", 0),
            payload.get("task_index", 0),
            payload["type"],
            payload["prompt"],
            payload["explanation"],
            payload.get("placeholder"),
            payload.get("hint", ""),
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
        SET topic = ?,
            language = ?,
            difficulty = ?,
            level_index = ?,
            task_index = ?,
            type = ?,
            prompt = ?,
            explanation = ?,
            placeholder = ?,
            hint = ?,
            order_index = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            payload["topic"],
            payload.get("language", ""),
            payload.get("difficulty", ""),
            payload.get("level_index", 0),
            payload.get("task_index", 0),
            payload["type"],
            payload["prompt"],
            payload["explanation"],
            payload.get("placeholder"),
            payload.get("hint", ""),
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
