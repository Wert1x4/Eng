"""Course catalogue A1–C1, with A3 and B3 between the standard steps."""

import re

from lumen.course_a1 import UNITS as A1
from lumen.course_a2 import UNITS as A2
from lumen.course_a3 import UNITS as A3
from lumen.course_b1 import UNITS as B1
from lumen.course_b2 import UNITS as B2
from lumen.course_b3 import UNITS as B3
from lumen.course_c1 import UNITS as C1

UNITS = A1 + A2 + A3 + B1 + B2 + B3 + C1

LEVELS = [
    ("A1", {"ru": "Начало", "uk": "Початок"}),
    ("A2", {"ru": "Быт", "uk": "Побут"}),
    ("A3", {"ru": "Дальше", "uk": "Далі"}),
    ("B1", {"ru": "Уверенность", "uk": "Впевненість"}),
    ("B2", {"ru": "Оттенки", "uk": "Відтінки"}),
    ("B3", {"ru": "Сложнее", "uk": "Складніше"}),
    ("C1", {"ru": "Точность", "uk": "Точність"}),
]

LESSON_KINDS = [
    ("words", {"ru": "Слова", "uk": "Слова"}),
    ("phrases", {"ru": "Фразы", "uk": "Фрази"}),
    ("build", {"ru": "Сборка", "uk": "Збірка"}),
    ("grammar", {"ru": "Грамматика", "uk": "Граматика"}),
    ("check", {"ru": "Проверка", "uk": "Перевірка"}),
]

RU_ONLY = set("ыэъёЫЭЪЁ")
UK_ONLY = set("іїєґІЇЄҐ")


def lesson_catalog():
    items = []
    for unit in UNITS:
        for kind, title in LESSON_KINDS:
            items.append(
                {
                    "id": f"{unit['id']}-{kind}",
                    "unit_id": unit["id"],
                    "level": unit["level"],
                    "kind": kind,
                    "title": title,
                    "unit_title": unit["title"],
                    "goal": unit["goal"],
                    "color": unit["color"],
                }
            )
    return items


def unit_by_id(unit_id):
    for unit in UNITS:
        if unit["id"] == unit_id:
            return unit
    return None


def lesson_by_id(lesson_id):
    for lesson in lesson_catalog():
        if lesson["id"] == lesson_id:
            return lesson
    return None


def _is_lang_key(key, lang):
    return key == lang or key.endswith("_" + lang)


def _walk_strings(node, lang, ctx, errors):
    if isinstance(node, dict):
        for key, value in node.items():
            if _is_lang_key(key, lang) and isinstance(value, str):
                _check_text(value, lang, ctx, errors)
            else:
                _walk_strings(value, lang, ctx, errors)
    elif isinstance(node, list):
        for item in node:
            _walk_strings(item, lang, ctx, errors)


def _check_text(text, lang, ctx, errors):
    if not text.strip():
        errors.append(f"{ctx}: empty {lang}")
    banned = UK_ONLY if lang == "ru" else RU_ONLY
    bad = sorted({ch for ch in text if ch in banned})
    if bad:
        errors.append(f"{ctx}: {lang} has {''.join(bad)} in «{text[:80]}»")


def validate_course():
    errors = []
    ids = [unit["id"] for unit in UNITS]
    if len(ids) != len(set(ids)):
        errors.append("duplicate unit id")
    by_level = {}
    for unit in UNITS:
        by_level.setdefault(unit["level"], 0)
        by_level[unit["level"]] += 1
        ctx = unit["id"]
        for lang in ("ru", "uk"):
            _walk_strings(unit, lang, ctx, errors)
        uk_blob = " ".join(
            [unit["title"]["uk"], unit["goal"]["uk"], unit["grammar_tip"]["uk"]]
            + [w["uk"] + w["ex_uk"] for w in unit["words"]]
            + [s["uk"] for s in unit["sentences"]]
            + [b["explain"]["uk"] for b in unit["blanks"]]
        )
        if not any(ch in uk_blob for ch in "іїєґ"):
            errors.append(f"{ctx}: Ukrainian block has no і/ї/є/ґ — it may be copied Russian")
        if len(unit["words"]) < 6:
            errors.append(f"{ctx}: need 6 words")
        if len(unit["sentences"]) < 4:
            errors.append(f"{ctx}: need 4 sentences")
        if len(unit["blanks"]) < 4:
            errors.append(f"{ctx}: need 4 blanks")
        for bucket, label in ((unit["words"], "word"), (unit["sentences"], "sentence")):
            for lang in ("en", "ru", "uk"):
                seen = {}
                for item in bucket:
                    key = re.sub(r"\s+", " ", item[lang].strip().lower())
                    if key in seen:
                        errors.append(f"{ctx}: duplicate {label} {lang} «{item[lang]}»")
                    seen[key] = item.get("en", "")
        for blank in unit["blanks"]:
            if "___" not in blank["prompt"]:
                errors.append(f"{ctx}: blank without ___: {blank['prompt']}")
            if blank["answer"] not in blank["options"]:
                errors.append(f"{ctx}: answer not in options: {blank['prompt']}")
            if len(set(blank["options"])) != len(blank["options"]):
                errors.append(f"{ctx}: duplicate blank options: {blank['prompt']}")
            if len(blank["options"]) != 4:
                errors.append(f"{ctx}: blank needs 4 options: {blank['prompt']}")
    for level, _title in LEVELS:
        if by_level.get(level) != 8:
            errors.append(f"{level} has {by_level.get(level, 0)} units, expected 8")
    if errors:
        raise SystemExit("Course check failed:\n- " + "\n- ".join(errors))
    return True
