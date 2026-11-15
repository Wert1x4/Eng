"""Write web/pack.json: lessons, dictionary and demo accounts for the offline app."""

import hashlib
import json
import random
import sqlite3
from pathlib import Path

from lumen.build_db import DB_PATH
from lumen.course_data import LESSON_KINDS, LEVELS, UNITS, lesson_catalog, unit_by_id
from lumen.engine import make_exercises

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "web" / "pack.json"


def seed_for(lesson_id, lang):
    digest = hashlib.sha256(f"{lesson_id}:{lang}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def password_hash(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def build():
    lessons = {}
    order = []
    meta = {}
    for lesson in lesson_catalog():
        order.append(lesson["id"])
        meta[lesson["id"]] = {
            "unit_id": lesson["unit_id"],
            "level": lesson["level"],
            "kind": lesson["kind"],
            "title": lesson["title"],
            "color": lesson["color"],
        }
        unit = unit_by_id(lesson["unit_id"])
        lessons[lesson["id"]] = {}
        for lang in ("ru", "uk"):
            rng = random.Random(seed_for(lesson["id"], lang))
            lessons[lesson["id"]][lang] = make_exercises(unit, lesson["kind"], lang, rng)
    units = {}
    for unit in UNITS:
        units[unit["id"]] = {
            "level": unit["level"],
            "title": unit["title"],
            "goal": unit["goal"],
            "color": unit["color"],
            "grammar_tip": unit["grammar_tip"],
            "grammar_title": unit["grammar_title"],
        }
    words = []
    grammar = []
    accounts = []
    progress = {}
    if DB_PATH.exists():
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            for row in conn.execute("SELECT headword, pos, level, ru, uk FROM words ORDER BY head_l, pos"):
                words.append(
                    {
                        "headword": row["headword"],
                        "pos": row["pos"] or "",
                        "level": row["level"],
                        "ru": row["ru"] or "",
                        "uk": row["uk"] or "",
                    }
                )
            for row in conn.execute("SELECT item, level, sentence_type FROM grammar ORDER BY item"):
                grammar.append(
                    {"item": row["item"], "level": row["level"], "sentence_type": row["sentence_type"] or ""}
                )
            for row in conn.execute(
                "SELECT id, username, display_name, lang, is_admin, xp, streak, best_streak, gems, daily_goal FROM users"
            ):
                accounts.append(
                    {
                        "id": row["id"],
                        "username": row["username"],
                        "display_name": row["display_name"],
                        "password": password_hash("lumen2026"),
                        "lang": row["lang"],
                        "is_admin": bool(row["is_admin"]),
                        "xp": row["xp"],
                        "streak": row["streak"],
                        "best_streak": row["best_streak"],
                        "gems": row["gems"],
                        "daily_goal": row["daily_goal"],
                        "sound_on": True,
                    }
                )
                done = {}
                for item in conn.execute(
                    "SELECT lesson_id, stars, best_accuracy, times_done, xp_awarded FROM lesson_progress WHERE user_id = ?",
                    (row["id"],),
                ):
                    done[item["lesson_id"]] = {
                        "stars": item["stars"],
                        "best_accuracy": item["best_accuracy"],
                        "times_done": item["times_done"],
                        "xp_awarded": item["xp_awarded"],
                    }
                progress[str(row["id"])] = done
        finally:
            conn.close()
    pack = {
        "levels": [{"id": code, "title": title} for code, title in LEVELS],
        "kinds": {code: title for code, title in LESSON_KINDS},
        "order": order,
        "meta": meta,
        "units": units,
        "lessons": lessons,
        "words": words,
        "grammar": grammar,
        "accounts": accounts,
        "progress": progress,
    }
    PACK.write_text(json.dumps(pack, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {PACK} ({PACK.stat().st_size} bytes, {len(order)} lessons, {len(words)} words)")


if __name__ == "__main__":
    build()
