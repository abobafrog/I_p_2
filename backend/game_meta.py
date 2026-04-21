from typing import Dict, List, Optional


SHOP_ITEMS = [
    {
        "id": "default",
        "name": "Обычная лягушка",
        "description": "Базовый образ без аксессуаров.",
        "price": 0,
        "icon": "🐸",
        "is_default": True,
    },
    {
        "id": "cylinder",
        "name": "Цилиндр",
        "description": "Тот самый цилиндр из оригинального магазина desktop-версии.",
        "price": 250,
        "icon": "🎩",
        "is_default": False,
    },
    {
        "id": "swamp_bow",
        "name": "Болотный бант",
        "description": "Легкий аксессуар для более вайбового профиля.",
        "price": 180,
        "icon": "🎀",
        "is_default": False,
    },
    {
        "id": "lotus_crown",
        "name": "Лотос-корона",
        "description": "Редкий болотный дроп для уверенных лягушек-кодеров.",
        "price": 420,
        "icon": "👑",
        "is_default": False,
    },
]

SHOP_ITEMS_BY_ID = {item["id"]: item for item in SHOP_ITEMS}

LEADERBOARD_METRICS = {
    "best_score": {
        "label": "Лучший счет",
        "scope": "route",
    },
    "completed_runs": {
        "label": "Завершенные забеги",
        "scope": "route",
    },
    "coins": {
        "label": "Монеты",
        "scope": "global",
    },
}


def get_shop_item(item_id: str) -> Optional[Dict]:
    return SHOP_ITEMS_BY_ID.get(item_id)


def get_metric_meta(metric: str) -> Dict:
    return LEADERBOARD_METRICS.get(metric, LEADERBOARD_METRICS["best_score"])


def serialize_shop_items(inventory: List[str], active_skin: str) -> List[Dict]:
    owned = set(inventory)
    return [
        {
            **item,
            "owned": item["id"] in owned,
            "active": item["id"] == active_skin,
        }
        for item in SHOP_ITEMS
    ]
