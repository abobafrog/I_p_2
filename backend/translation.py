from __future__ import annotations

import re
from typing import Any, Dict, List, Sequence

import httpx

from backend.config import (
    get_translation_api_base_url,
    get_translation_api_key,
    get_translation_timeout_seconds,
)


SUPPORTED_LOCALES = {"ru": "ru", "en": "en", "zh": "zh"}
PUBLIC_TRANSLATION_BASE_URLS = (
    "https://translate.argosopentech.com",
    "https://libretranslate.de",
)
_TRANSLATION_CACHE: dict[tuple[str, str], str] = {}


def normalize_locale(locale: str | None) -> str:
    if locale in SUPPORTED_LOCALES:
        return locale
    return "ru"


def looks_like_code(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False

    if "=>" in stripped or ":=" in stripped or "++" in stripped or "--" in stripped:
        return True

    if any(symbol in stripped for symbol in ("{", "}", "[", "]", ";", "`")):
        return True

    if ("(" in stripped or ")" in stripped) and " " not in stripped:
        return True

    if "=" in stripped and len(stripped.split()) <= 4 and not any(punct in stripped for punct in (".", "!", "?")):
        return True

    return False


def should_translate(text: str, locale: str) -> bool:
    if locale not in SUPPORTED_LOCALES or not text:
        return False

    stripped = text.strip()
    if not stripped or not any(ch.isalpha() for ch in stripped):
        return False

    if looks_like_code(stripped):
        return False

    return True


def _chunked(values: Sequence[str], chunk_size: int) -> Sequence[Sequence[str]]:
    for index in range(0, len(values), chunk_size):
        yield values[index : index + chunk_size]


def _candidate_translation_urls() -> List[str]:
    configured_base_url = get_translation_api_base_url()
    if configured_base_url:
        return [f"{configured_base_url.rstrip('/')}/translate"]

    candidates: List[str] = list(PUBLIC_TRANSLATION_BASE_URLS)

    if get_translation_api_key():
        candidates.append("https://libretranslate.com")

    urls: List[str] = []
    seen: set[str] = set()
    for base_url in candidates:
        endpoint = f"{base_url.rstrip('/')}/translate"
        if endpoint in seen:
            continue
        seen.add(endpoint)
        urls.append(endpoint)

    return urls


def _translate_batch_with_api(texts: Sequence[str], locale: str) -> List[str]:
    target_language = SUPPORTED_LOCALES[locale]
    payload: Dict[str, Any] = {
        "q": list(texts),
        "source": "auto",
        "target": target_language,
        "format": "text",
    }

    api_key = get_translation_api_key()
    if api_key:
        payload["api_key"] = api_key

    last_error: Exception | None = None
    for endpoint in _candidate_translation_urls():
        try:
            response = httpx.post(
                endpoint,
                json=payload,
                timeout=get_translation_timeout_seconds(),
            )
            response.raise_for_status()
            data = response.json()
            translated = data.get("translatedText")

            if isinstance(translated, str):
                if len(texts) != 1:
                    raise ValueError("Unexpected translation response shape.")
                return [translated]

            if isinstance(translated, list):
                if len(translated) != len(texts):
                    raise ValueError("Translation response length mismatch.")
                return [str(item) for item in translated]

            raise ValueError("Translation response missing translatedText.")
        except Exception as exc:  # pragma: no cover - external API fallback
            last_error = exc

    if last_error is not None:
        raise last_error

    return list(texts)


def translate_texts(texts: Sequence[str], locale: str | None) -> List[str]:
    normalized_locale = normalize_locale(locale)
    if not texts:
        return list(texts)

    result = list(texts)
    pending_positions: dict[str, List[int]] = {}

    for index, text in enumerate(result):
        if not isinstance(text, str) or not should_translate(text, normalized_locale):
            continue

        cache_key = (normalized_locale, text)
        cached = _TRANSLATION_CACHE.get(cache_key)
        if cached is not None:
            result[index] = cached
            continue

        pending_positions.setdefault(text, []).append(index)

    pending_texts = list(pending_positions)
    if not pending_texts:
        return result

    translated_pending: List[str] = []
    for chunk in _chunked(pending_texts, 25):
        chunk_translated: List[str]
        chunk_translated_successfully = True
        try:
            chunk_translated = _translate_batch_with_api(chunk, normalized_locale)
        except Exception:
            chunk_translated_successfully = False
            chunk_translated = list(chunk)

        translated_pending.extend(chunk_translated)

        if chunk_translated_successfully:
            for source_text, translated_text in zip(chunk, chunk_translated):
                _TRANSLATION_CACHE[(normalized_locale, source_text)] = translated_text

    for source_text, translated_text in zip(pending_texts, translated_pending):
        for index in pending_positions[source_text]:
            result[index] = translated_text

    return result


def translate_text(text: str, locale: str | None) -> str:
    return translate_texts([text], locale)[0]


def translate_questions(questions: Sequence[Dict[str, Any]], locale: str | None) -> List[Dict[str, Any]]:
    normalized_locale = normalize_locale(locale)
    translated_questions = [dict(question) for question in questions]
    if normalized_locale == "ru" or not translated_questions:
        return translated_questions

    sources: List[str] = []
    locations: List[tuple[int, str, int | None]] = []

    for question_index, question in enumerate(translated_questions):
        for field in ("prompt", "hint", "placeholder", "explanation"):
            value = question.get(field)
            if isinstance(value, str) and should_translate(value, normalized_locale):
                sources.append(value)
                locations.append((question_index, field, None))

        options = question.get("options")
        if isinstance(options, list):
            for option_index, option in enumerate(options):
                if isinstance(option, str) and should_translate(option, normalized_locale):
                    sources.append(option)
                    locations.append((question_index, "options", option_index))

    translated_sources = translate_texts(sources, normalized_locale)
    for (question_index, field, option_index), translated_value in zip(locations, translated_sources):
        if field == "options" and option_index is not None:
            translated_questions[question_index]["options"][option_index] = translated_value
        else:
            translated_questions[question_index][field] = translated_value

    return translated_questions


def translate_promo_codes(promos: Sequence[Dict[str, Any]], locale: str | None) -> List[Dict[str, Any]]:
    normalized_locale = normalize_locale(locale)
    translated_promos = [dict(promo) for promo in promos]
    if normalized_locale == "ru" or not translated_promos:
        return translated_promos

    sources: List[str] = []
    locations: List[int] = []

    for promo_index, promo in enumerate(translated_promos):
        description = promo.get("description")
        if isinstance(description, str) and should_translate(description, normalized_locale):
            sources.append(description)
            locations.append(promo_index)

    translated_sources = translate_texts(sources, normalized_locale)
    for promo_index, translated_value in zip(locations, translated_sources):
        translated_promos[promo_index]["description"] = translated_value

    return translated_promos


def translate_question(question: Dict[str, Any], locale: str | None) -> Dict[str, Any]:
    translated_question = translate_questions([question], locale)[0]
    return translated_question


def translate_questions_with_result(
    questions: Sequence[Dict[str, Any]],
    locale: str | None,
) -> List[Dict[str, Any]]:
    return translate_questions(questions, locale)


def translate_question_feedback(
    feedback: Dict[str, Any],
    locale: str | None,
) -> Dict[str, Any]:
    normalized_locale = normalize_locale(locale)
    translated_feedback = dict(feedback)
    if normalized_locale == "ru":
        return translated_feedback

    sources: List[str] = []
    locations: List[tuple[str, int | None]] = []

    explanation = translated_feedback.get("explanation")
    if isinstance(explanation, str) and should_translate(explanation, normalized_locale):
        sources.append(explanation)
        locations.append(("explanation", None))

    correct_answers = translated_feedback.get("correct_answers")
    if isinstance(correct_answers, list):
        for answer_index, answer in enumerate(correct_answers):
            if isinstance(answer, str) and should_translate(answer, normalized_locale):
                sources.append(answer)
                locations.append(("correct_answers", answer_index))

    translated_sources = translate_texts(sources, normalized_locale)
    for (field, answer_index), translated_value in zip(locations, translated_sources):
        if field == "correct_answers" and answer_index is not None:
            translated_feedback["correct_answers"][answer_index] = translated_value
        elif field == "explanation":
            translated_feedback["explanation"] = translated_value

    return translated_feedback


def translate_route_options(routes: Sequence[Dict[str, Any]], locale: str | None) -> List[Dict[str, Any]]:
    normalized_locale = normalize_locale(locale)
    translated_routes = [dict(route) for route in routes]
    if normalized_locale == "ru" or not translated_routes:
        return translated_routes

    labels: List[str] = []
    label_indices: List[int] = []

    for route_index, route in enumerate(translated_routes):
        label = route.get("difficulty_label")
        if isinstance(label, str) and should_translate(label, normalized_locale):
            labels.append(label)
            label_indices.append(route_index)

    translated_labels = translate_texts(labels, normalized_locale)
    for route_index, translated_value in zip(label_indices, translated_labels):
        translated_routes[route_index]["difficulty_label"] = translated_value

    return translated_routes


def translate_shop_items(items: Sequence[Dict[str, Any]], locale: str | None) -> List[Dict[str, Any]]:
    normalized_locale = normalize_locale(locale)
    translated_items = [dict(item) for item in items]
    if normalized_locale == "ru" or not translated_items:
        return translated_items

    sources: List[str] = []
    locations: List[tuple[int, str]] = []

    for item_index, item in enumerate(translated_items):
        for field in ("name", "description"):
            value = item.get(field)
            if isinstance(value, str) and should_translate(value, normalized_locale):
                sources.append(value)
                locations.append((item_index, field))

    translated_sources = translate_texts(sources, normalized_locale)
    for (item_index, field), translated_value in zip(locations, translated_sources):
        translated_items[item_index][field] = translated_value

    return translated_items


def translate_message(message: str | None, locale: str | None) -> str | None:
    if message is None:
        return None
    translated_message = translate_text(message, locale)
    return translated_message
