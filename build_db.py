"""Create lumen.db: accounts, CEFR word lists, grammar catalogue."""

import csv
import re
import sqlite3
from datetime import date, datetime
from pathlib import Path

from lumen.course_data import UNITS, validate_course
from lumen.course_data import RU_ONLY, UK_ONLY
from lumen.glossary import extra_glosses
from lumen.security import hash_password

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "lumen.db"
SOURCES = ROOT / "_sources"
DEMO_PASSWORD = "lumen2026"

SCHEMA = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    lang TEXT NOT NULL DEFAULT 'ru',
    is_admin INTEGER NOT NULL DEFAULT 0,
    xp INTEGER NOT NULL DEFAULT 0,
    streak INTEGER NOT NULL DEFAULT 0,
    best_streak INTEGER NOT NULL DEFAULT 0,
    last_active TEXT,
    hearts INTEGER NOT NULL DEFAULT 5,
    hearts_at TEXT NOT NULL,
    gems INTEGER NOT NULL DEFAULT 0,
    daily_goal INTEGER NOT NULL DEFAULT 50,
    daily_xp INTEGER NOT NULL DEFAULT 0,
    daily_date TEXT,
    sound_on INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
CREATE TABLE sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
);
CREATE TABLE lesson_progress (
    user_id INTEGER NOT NULL REFERENCES users(id),
    lesson_id TEXT NOT NULL,
    stars INTEGER NOT NULL,
    best_accuracy REAL NOT NULL,
    times_done INTEGER NOT NULL,
    xp_awarded INTEGER NOT NULL,
    PRIMARY KEY (user_id, lesson_id)
);
CREATE TABLE mistakes (
    user_id INTEGER NOT NULL REFERENCES users(id),
    exercise_key TEXT NOT NULL,
    lang TEXT NOT NULL,
    payload TEXT NOT NULL,
    wrong_count INTEGER NOT NULL,
    PRIMARY KEY (user_id, exercise_key, lang)
);
CREATE TABLE lesson_runs (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    lesson_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    lang TEXT NOT NULL,
    exercises_json TEXT NOT NULL,
    answered INTEGER NOT NULL DEFAULT 0,
    correct INTEGER NOT NULL DEFAULT 0,
    finished INTEGER NOT NULL DEFAULT 0,
    result_json TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE words (
    id INTEGER PRIMARY KEY,
    headword TEXT NOT NULL,
    head_l TEXT NOT NULL,
    pos TEXT,
    level TEXT NOT NULL,
    source TEXT NOT NULL,
    ru TEXT,
    uk TEXT,
    ru_l TEXT,
    uk_l TEXT
);
CREATE INDEX idx_words_level ON words(level);
CREATE INDEX idx_words_head ON words(head_l);
CREATE TABLE grammar (
    id TEXT PRIMARY KEY,
    level TEXT NOT NULL,
    item TEXT NOT NULL,
    sentence_type TEXT
);
CREATE INDEX idx_grammar_level ON grammar(level);
CREATE TABLE meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def now():
    return datetime.now().isoformat(timespec="seconds")


def first_level(text):
    match = re.search(r"A1|A2|B1|B2|C1|C2", (text or "").upper())
    return match.group(0) if match else ""


def clean_head(head):
    head = (head or "").strip()
    if "/" in head:
        head = head.split("/")[0].strip()
    return head


def course_gloss():
    gloss = {}
    conflicts = []
    for unit in UNITS:
        for word in unit["words"]:
            key = word["en"].casefold()
            pair = (word["ru"], word["uk"])
            if key in gloss and gloss[key] != pair:
                conflicts.append((word["en"], gloss[key], pair))
            else:
                gloss[key] = pair
    for key, pair in extra_glosses().items():
        ru, uk = pair
        if any(ch in ru for ch in UK_ONLY):
            raise SystemExit(f"Glossary RU has Ukrainian letters: {key} {ru}")
        if any(ch in uk for ch in RU_ONLY):
            raise SystemExit(f"Glossary UK has Russian letters: {key} {uk}")
        gloss.setdefault(key, pair)
    return gloss, conflicts


def read_words(gloss):
    rows = []
    seen = set()

    def add(head, pos, level, source):
        head = clean_head(head)
        if not head or len(head) > 60 or level not in {"A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2"}:
            return
        key = (level, head.casefold(), (pos or "").casefold())
        if key in seen:
            return
        seen.add(key)
        pair = gloss.get(head.casefold())
        ru, uk = pair if pair else (None, None)
        rows.append(
            (
                head,
                head.casefold(),
                (pos or "").strip(),
                level,
                source,
                ru,
                uk,
                ru.casefold() if ru else None,
                uk.casefold() if uk else None,
            )
        )

    with (SOURCES / "cefrj.csv").open(encoding="utf-8-sig", newline="") as handle:
        for record in csv.DictReader(handle):
            add(record.get("headword", ""), record.get("pos", ""), record.get("CEFR", ""), "cefrj")
    with (SOURCES / "octanove-c1c2.csv").open(encoding="utf-8-sig", newline="") as handle:
        for record in csv.DictReader(handle):
            add(record.get("headword", ""), record.get("pos", ""), record.get("CEFR", ""), "octanove")
    known = {row[1] for row in rows}
    for unit in UNITS:
        for word in unit["words"]:
            if word["en"].casefold() not in known:
                add(word["en"], "phrase", unit["level"], "course")
                known.add(word["en"].casefold())
    return rows


def sync_course_words(path=DB_PATH):
    """Add lesson headwords that are not in the dictionary yet. Keeps existing accounts."""
    if not path.exists():
        return 0
    conn = sqlite3.connect(path)
    try:
        existing = {(row[0], row[1]) for row in conn.execute("SELECT head_l, level FROM words")}
        rows = []
        for unit in UNITS:
            for word in unit["words"]:
                key = word["en"].casefold()
                if (key, unit["level"]) in existing:
                    continue
                existing.add((key, unit["level"]))
                rows.append(
                    (
                        word["en"],
                        key,
                        "phrase",
                        unit["level"],
                        "course",
                        word["ru"],
                        word["uk"],
                        word["ru"].casefold(),
                        word["uk"].casefold(),
                    )
                )
        if rows:
            conn.executemany(
                "INSERT INTO words (headword, head_l, pos, level, source, ru, uk, ru_l, uk_l) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
            conn.commit()
        return len(rows)
    finally:
        conn.close()


def read_grammar():
    rows = []
    path = SOURCES / "cefrj-grammar.csv"
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for record in csv.DictReader(handle):
            level = first_level(record.get("CEFR-J Level") or "") or first_level(record.get("Core Inventory") or "")
            item = (record.get("Grammatical Item") or "").strip()
            if not level or not item or level not in {"A1", "A2", "B1", "B2", "C1", "C2"}:
                continue
            rows.append((record.get("ID") or item, level, item, (record.get("Sentence Type") or "").strip()))
    return rows


def seed_users(conn):
    today = date.today().isoformat()
    stamp = now()
    people = [
        ("alex", "Алекс", "ru", 0, 640, 4, 6, today, 28, 40, 50),
        ("ostap", "Остап", "uk", 0, 200, 2, 2, today, 12, 20, 50),
        ("mira", "Міра", "uk", 0, 0, 0, 0, None, 5, 0, 30),
        ("admin", "Адмін", "ru", 1, 2400, 12, 20, today, 80, 80, 100),
    ]
    for username, display, lang, admin, xp, streak, best, active, gems, daily, goal in people:
        conn.execute(
            """
            INSERT INTO users (
                username, display_name, password_hash, lang, is_admin, xp, streak, best_streak,
                last_active, hearts, hearts_at, gems, daily_goal, daily_xp, daily_date, sound_on, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 5, ?, ?, ?, ?, ?, 1, ?)
            """,
            (username, display, hash_password(DEMO_PASSWORD), lang, admin, xp, streak, best, active, stamp, gems, goal, daily, today, stamp),
        )
    ids = {row[0]: row[1] for row in conn.execute("SELECT username, id FROM users")}
    alex_done = [
        ("a1-hello-words", 3, 1),
        ("a1-hello-phrases", 3, 1),
        ("a1-hello-build", 3, 1),
        ("a1-hello-grammar", 3, 1),
        ("a1-hello-check", 3, 1),
        ("a1-numbers-words", 2, 0.86),
        ("a1-numbers-phrases", 2, 0.86),
    ]
    for lesson_id, stars, accuracy in alex_done:
        conn.execute(
            "INSERT INTO lesson_progress (user_id, lesson_id, stars, best_accuracy, times_done, xp_awarded) VALUES (?, ?, ?, ?, 1, ?)",
            (ids["alex"], lesson_id, stars, accuracy, 100 if stars == 3 else 70),
        )
    for lesson_id in ("a1-hello-words", "a1-hello-phrases"):
        conn.execute(
            "INSERT INTO lesson_progress (user_id, lesson_id, stars, best_accuracy, times_done, xp_awarded) VALUES (?, ?, 3, 1, 1, 100)",
            (ids["ostap"], lesson_id),
        )


def rebuild(path=DB_PATH):
    validate_course()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    gloss, conflicts = course_gloss()
    words = read_words(gloss)
    grammar = read_grammar()
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA)
        conn.executemany(
            "INSERT INTO words (headword, head_l, pos, level, source, ru, uk, ru_l, uk_l) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            words,
        )
        conn.executemany(
            "INSERT OR REPLACE INTO grammar (id, level, item, sentence_type) VALUES (?, ?, ?, ?)",
            grammar,
        )
        seed_users(conn)
        conn.execute("INSERT INTO meta (key, value) VALUES ('built_at', ?)", (now(),))
        conn.execute("INSERT INTO meta (key, value) VALUES ('content', 'A1-C1 ru/uk')")
        conn.commit()
    finally:
        conn.close()
    translated = sum(1 for row in words if row[5] or row[6])
    print(f"Database: {path}")
    print(f"Words: {len(words)}, with a translation: {translated}")
    print(f"Grammar items: {len(grammar)}")
    print(f"Glossary conflicts left on the first lesson wording: {len(conflicts)}")
    return path


if __name__ == "__main__":
    rebuild()
