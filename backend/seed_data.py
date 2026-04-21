from __future__ import annotations

import ast
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List


BASE_DIR = Path(__file__).resolve().parent.parent
GAME_FILE = BASE_DIR / "game.py"

LANGUAGE_ORDER = ("Python", "JavaScript")
SEEDED_DIFFICULTY_ORDER = ("Easy", "Medium", "Hard")
DIFFICULTY_ORDER = SEEDED_DIFFICULTY_ORDER
DEFAULT_LEVELS_TOTAL = 5

LANGUAGE_SLUGS = {
    "Python": "python",
    "JavaScript": "javascript",
}

DIFFICULTY_SLUGS = {
    "Easy": "easy",
    "Medium": "medium",
    "Hard": "hard",
}

DIFFICULTY_LABELS = {
    "Easy": "Легкая",
    "Medium": "Средняя",
    "Hard": "Сложная",
}


def build_topic_slug(language: str, difficulty: str) -> str:
    return f"{LANGUAGE_SLUGS[language]}-{DIFFICULTY_SLUGS[difficulty]}"


@lru_cache(maxsize=1)
def _load_get_tasks():
    source = GAME_FILE.read_text(encoding="utf-8")
    tree = ast.parse(source)

    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "get_tasks":
            func_source = ast.get_source_segment(source, node)
            if not func_source:
                break

            namespace: Dict[str, Any] = {}
            exec(func_source, namespace)
            return namespace["get_tasks"]

    raise RuntimeError("Не удалось загрузить get_tasks() из game.py")


@lru_cache(maxsize=1)
def get_game_routes() -> List[Dict[str, Any]]:
    get_tasks = _load_get_tasks()
    routes: List[Dict[str, Any]] = []

    for language in LANGUAGE_ORDER:
        for difficulty in SEEDED_DIFFICULTY_ORDER:
            levels = get_tasks(language, difficulty)
            total_questions = sum(len(level) for level in levels)
            routes.append(
                {
                    "topic": build_topic_slug(language, difficulty),
                    "language": language,
                    "difficulty": difficulty,
                    "difficulty_label": DIFFICULTY_LABELS[difficulty],
                    "levels_total": len(levels),
                    "questions_total": total_questions,
                    "tasks_per_level": 5,
                }
            )

    return routes


@lru_cache(maxsize=1)
def get_seed_questions() -> List[Dict[str, Any]]:
    get_tasks = _load_get_tasks()
    questions: List[Dict[str, Any]] = []

    for language in LANGUAGE_ORDER:
        for difficulty in SEEDED_DIFFICULTY_ORDER:
            topic = build_topic_slug(language, difficulty)
            levels = get_tasks(language, difficulty)

            for level_index, level_questions in enumerate(levels):
                for task_index, task in enumerate(level_questions):
                    answers = task["ans"]
                    if not isinstance(answers, list):
                        answers = [answers]

                    questions.append(
                        {
                            "topic": topic,
                            "language": language,
                            "difficulty": difficulty,
                            "level_index": level_index,
                            "task_index": task_index,
                            "type": task["type"],
                            "prompt": task["q"],
                            "options": task.get("options", []),
                            "correct_answers": answers,
                            "explanation": (
                                f"Подсказка из desktop-версии: {task['hint']}"
                            ),
                            "hint": task["hint"],
                            "placeholder": (
                                task["hint"] if task["type"] == "input" else None
                            ),
                            "order_index": level_index * 100 + task_index,
                        }
                    )

    return questions


AVAILABLE_ROUTES = get_game_routes()
ROUTES_BY_TOPIC = {route["topic"]: route for route in AVAILABLE_ROUTES}
SEED_QUESTIONS = get_seed_questions()
SEED_QUESTIONS_BY_KEY = {
    (question["topic"], question["level_index"], question["task_index"]): question
    for question in SEED_QUESTIONS
}
SEED_QUESTIONS_BY_ORDER = {
    (question["topic"], question["order_index"]): question
    for question in SEED_QUESTIONS
}
SEED_QUESTIONS_BY_PROMPT = {
    (question["topic"], question["prompt"]): question
    for question in SEED_QUESTIONS
}


def get_route_meta(topic: str) -> Dict[str, Any] | None:
    return ROUTES_BY_TOPIC.get(topic)


def get_seed_question(topic: str, level_index: int, task_index: int) -> Dict[str, Any] | None:
    return SEED_QUESTIONS_BY_KEY.get((topic, level_index, task_index))


def get_seed_question_by_order(topic: str, order_index: int) -> Dict[str, Any] | None:
    return SEED_QUESTIONS_BY_ORDER.get((topic, order_index))


def get_seed_question_by_prompt(topic: str, prompt: str) -> Dict[str, Any] | None:
    return SEED_QUESTIONS_BY_PROMPT.get((topic, prompt))
