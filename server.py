"""Local server for the Lumen mobile app."""

import json
import os
import re
import secrets
import socket
import sqlite3
import ssl
import subprocess
import threading
import webbrowser
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from lumen.build_db import DB_PATH, rebuild, sync_course_words
from lumen.course_data import LEVELS, lesson_catalog, validate_course
from lumen.engine import (
    grade,
    kind_title,
    lesson_by_id,
    make_exercises,
    public_exercise,
    unit_by_id,
    unit_of_lesson,
)
from lumen.phone import qr_svg
from lumen.security import hash_password, verify_password

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
LOCK = threading.Lock()
HTTPS_PORT = None
USERNAME_RE = re.compile(r"^[a-z][a-z0-9_]{2,19}$")

SENTENCE_TYPES = {
    "AFF. DEC.": {"ru": "утверждение", "uk": "ствердження"},
    "NEG. DEC.": {"ru": "отрицание", "uk": "заперечення"},
    "AFF. INT.": {"ru": "вопрос", "uk": "питання"},
    "NEG. INT.": {"ru": "отрицательный вопрос", "uk": "заперечне питання"},
}


def connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def ensure_db():
    if not DB_PATH.exists():
        rebuild(DB_PATH)
    else:
        validate_course()
        sync_course_words(DB_PATH)


def today():
    return date.today().isoformat()


def stamp():
    return datetime.now().isoformat(timespec="seconds")


def visible_streak(user):
    last = user["last_active"]
    if not last:
        return 0
    current = date.today()
    yesterday = (current - timedelta(days=1)).isoformat()
    if last == current.isoformat() or last == yesterday:
        return user["streak"]
    return 0


def refresh_user(conn, user_id):
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        return None
    user = dict(row)
    current = today()
    if user["daily_date"] != current:
        conn.execute(
            "UPDATE users SET daily_xp = 0, daily_date = ? WHERE id = ?",
            (current, user_id),
        )
        conn.commit()
        user["daily_xp"] = 0
        user["daily_date"] = current
    return user


def public_user(conn, user):
    done = conn.execute(
        "SELECT COUNT(*), AVG(best_accuracy) FROM lesson_progress WHERE user_id = ? AND stars > 0",
        (user["id"],),
    ).fetchone()
    lessons_done = done[0] or 0
    accuracy = round((done[1] or 0) * 100)
    return {
        "id": user["id"],
        "username": user["username"],
        "display_name": user["display_name"],
        "lang": user["lang"],
        "is_admin": bool(user["is_admin"]),
        "xp": user["xp"],
        "streak": visible_streak(user),
        "best_streak": user["best_streak"],
        "gems": user["gems"],
        "daily_goal": user["daily_goal"],
        "daily_xp": user["daily_xp"],
        "sound_on": bool(user["sound_on"]),
        "lessons_done": lessons_done,
        "accuracy": accuracy,
        "created_at": user["created_at"],
    }


def touch_activity(conn, user):
    current = today()
    last = user["last_active"]
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    if last == current:
        streak = user["streak"]
    elif last == yesterday:
        streak = user["streak"] + 1
    else:
        streak = 1
    best = max(user["best_streak"], streak)
    conn.execute(
        "UPDATE users SET streak = ?, best_streak = ?, last_active = ? WHERE id = ?",
        (streak, best, current, user["id"]),
    )
    user["streak"] = streak
    user["best_streak"] = best
    user["last_active"] = current
    return streak


def course_for(conn, user):
    lang = user["lang"]
    progress = {
        row["lesson_id"]: dict(row)
        for row in conn.execute("SELECT * FROM lesson_progress WHERE user_id = ?", (user["id"],))
    }
    catalog = lesson_catalog()
    admin = bool(user["is_admin"])
    unlocked = True
    states = {}
    for lesson in catalog:
        done = progress.get(lesson["id"])
        if done and done["stars"] > 0:
            state = "done"
            stars = done["stars"]
        elif admin or unlocked:
            state = "open"
            stars = 0
            if not admin:
                unlocked = False
        else:
            state = "locked"
            stars = 0
        states[lesson["id"]] = (state, stars)
    levels = []
    for code, title in LEVELS:
        unit_ids = []
        for lesson in catalog:
            if lesson["level"] == code and lesson["unit_id"] not in unit_ids:
                unit_ids.append(lesson["unit_id"])
        units = []
        for unit_id in unit_ids:
            unit = unit_by_id(unit_id)
            lessons = []
            for lesson in catalog:
                if lesson["unit_id"] != unit_id:
                    continue
                state, stars = states[lesson["id"]]
                lessons.append(
                    {
                        "id": lesson["id"],
                        "title": lesson["title"][lang],
                        "kind": lesson["kind"],
                        "state": state,
                        "stars": stars,
                    }
                )
            units.append(
                {
                    "id": unit_id,
                    "title": unit["title"][lang],
                    "goal": unit["goal"][lang],
                    "color": unit["color"],
                    "lessons": lessons,
                }
            )
        levels.append({"id": code, "title": title[lang], "units": units})
    return {"levels": levels}


def next_lesson_id(lesson_id):
    ids = [lesson["id"] for lesson in lesson_catalog()]
    if lesson_id not in ids:
        return None
    index = ids.index(lesson_id)
    if index + 1 < len(ids):
        return ids[index + 1]
    return None


def lesson_state(conn, user, lesson_id):
    if user["is_admin"]:
        return "open"
    catalog = [lesson["id"] for lesson in lesson_catalog()]
    if lesson_id not in catalog:
        return "missing"
    progress = {
        row["lesson_id"]: row["stars"]
        for row in conn.execute(
            "SELECT lesson_id, stars FROM lesson_progress WHERE user_id = ? AND stars > 0",
            (user["id"],),
        )
    }
    for item in catalog:
        if item == lesson_id:
            return "done" if progress.get(item) else "open"
        if not progress.get(item):
            return "locked"
    return "locked"


class App(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def handle(self):
        try:
            super().handle()
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            return

    def log_message(self, fmt, *args):
        print("[%s] %s" % (self.log_date_time_string(), fmt % args))

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length > 1_000_000:
            return None
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return None

    def _send(self, code, payload, content_type="application/json; charset=utf-8"):
        if isinstance(payload, (dict, list)):
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        elif isinstance(payload, str):
            body = payload.encode("utf-8")
        else:
            body = payload
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _error(self, code, error):
        self._send(code, {"error": error})

    def _user(self, conn):
        header = self.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return None
        token = header[7:].strip()
        row = conn.execute(
            "SELECT users.* FROM sessions JOIN users ON users.id = sessions.user_id WHERE token = ?",
            (token,),
        ).fetchone()
        if not row:
            return None
        return refresh_user(conn, row["id"])

    def _phone_url(self):
        # iPhone Safari from the camera stays blank on the self-signed https port.
        return f"http://{lan_ip()}:8765/"

    def _session(self, conn, user_id):
        token = secrets.token_urlsafe(32)
        conn.execute(
            "INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)",
            (token, user_id, stamp()),
        )
        return token

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/join.svg":
            self._send(200, qr_svg(self._phone_url()), "image/svg+xml")
            return
        if parsed.path.startswith("/api/"):
            self._api_get(parsed)
            return
        self._static(parsed.path)

    def do_POST(self):
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/"):
            self._error(404, "not_found")
            return
        self._api_post(parsed)

    def _static(self, path):
        rel = path.lstrip("/") or "index.html"
        if ".." in rel.split("/"):
            self._error(404, "not_found")
            return
        file_path = (WEB / rel).resolve()
        try:
            file_path.relative_to(WEB.resolve())
        except ValueError:
            self._error(404, "not_found")
            return
        if file_path.is_dir():
            file_path = file_path / "index.html"
        if not file_path.is_file():
            self._error(404, "not_found")
            return
        kind = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
            ".svg": "image/svg+xml",
            ".png": "image/png",
            ".webmanifest": "application/manifest+json",
            ".json": "application/json; charset=utf-8",
        }.get(file_path.suffix, "application/octet-stream")
        self._send(200, file_path.read_bytes(), kind)

    def _api_get(self, parsed):
        with LOCK:
            conn = connect()
            try:
                path = parsed.path
                if path == "/api/health":
                    self._send(200, {"ok": True})
                    return
                if path == "/api/join":
                    self._send(200, {"url": self._phone_url()})
                    return
                user = self._user(conn)
                if not user:
                    self._error(401, "unauthorized")
                    return
                if path == "/api/me":
                    self._send(200, {"user": public_user(conn, user)})
                elif path == "/api/course":
                    self._send(200, course_for(conn, user))
                elif path == "/api/leaderboard":
                    self._leaderboard(conn, user)
                elif path == "/api/words":
                    self._words(conn, user, parse_qs(parsed.query))
                elif path == "/api/grammar":
                    self._grammar(conn, user, parse_qs(parsed.query))
                else:
                    self._error(404, "not_found")
            finally:
                conn.close()

    def _api_post(self, parsed):
        body = self._read_json()
        if body is None:
            self._error(400, "bad_json")
            return
        with LOCK:
            conn = connect()
            try:
                path = parsed.path
                if path == "/api/register":
                    self._register(conn, body)
                elif path == "/api/login":
                    self._login(conn, body)
                elif path == "/api/logout":
                    self._logout(conn)
                else:
                    user = self._user(conn)
                    if not user:
                        self._error(401, "unauthorized")
                        return
                    if path == "/api/settings":
                        self._settings(conn, user, body)
                    elif path == "/api/lesson/start":
                        self._start(conn, user, body, "lesson")
                    elif path == "/api/practice/start":
                        self._start_practice(conn, user)
                    elif path == "/api/lesson/check":
                        self._check(conn, user, body)
                    elif path == "/api/lesson/finish":
                        self._finish(conn, user, body)
                    else:
                        self._error(404, "not_found")
            finally:
                conn.close()

    def _register(self, conn, body):
        username = str(body.get("username") or "").strip().lower()
        display = str(body.get("display_name") or "").strip()
        password = str(body.get("password") or "")
        lang = body.get("lang") if body.get("lang") in ("ru", "uk") else None
        if not USERNAME_RE.match(username):
            self._error(400, "bad_username")
            return
        if not (1 <= len(display) <= 32):
            self._error(400, "bad_name")
            return
        if not (4 <= len(password) <= 64):
            self._error(400, "weak_password")
            return
        if not lang:
            self._error(400, "bad_lang")
            return
        exists = conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone()
        if exists:
            self._error(409, "taken")
            return
        current = today()
        conn.execute(
            """
            INSERT INTO users (
                username, display_name, password_hash, lang, hearts, hearts_at, gems,
                daily_goal, daily_xp, daily_date, created_at
            ) VALUES (?, ?, ?, ?, 5, ?, 5, 50, 0, ?, ?)
            """,
            (username, display, hash_password(password), lang, stamp(), current, stamp()),
        )
        user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        token = self._session(conn, user_id)
        conn.commit()
        user = refresh_user(conn, user_id)
        self._send(200, {"token": token, "user": public_user(conn, user)})

    def _login(self, conn, body):
        username = str(body.get("username") or "").strip().lower()
        password = str(body.get("password") or "")
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if not row or not verify_password(password, row["password_hash"]):
            self._error(401, "bad_login")
            return
        token = self._session(conn, row["id"])
        conn.commit()
        user = refresh_user(conn, row["id"])
        self._send(200, {"token": token, "user": public_user(conn, user)})

    def _logout(self, conn):
        header = self.headers.get("Authorization", "")
        if header.startswith("Bearer "):
            conn.execute("DELETE FROM sessions WHERE token = ?", (header[7:].strip(),))
            conn.commit()
        self._send(200, {"ok": True})

    def _settings(self, conn, user, body):
        lang = user["lang"]
        goal = user["daily_goal"]
        sound = user["sound_on"]
        if body.get("lang") in ("ru", "uk"):
            lang = body["lang"]
        if body.get("daily_goal") in (20, 50, 100):
            goal = body["daily_goal"]
        if "sound_on" in body:
            sound = 1 if body["sound_on"] else 0
        conn.execute(
            "UPDATE users SET lang = ?, daily_goal = ?, sound_on = ? WHERE id = ?",
            (lang, goal, sound, user["id"]),
        )
        conn.commit()
        fresh = refresh_user(conn, user["id"])
        self._send(200, {"user": public_user(conn, fresh)})

    def _start(self, conn, user, body, mode):
        lesson_id = str(body.get("lesson_id") or "")
        lesson = lesson_by_id(lesson_id)
        if not lesson:
            self._error(404, "not_found")
            return
        state = lesson_state(conn, user, lesson_id)
        if state == "locked":
            self._error(403, "locked")
            return
        existing = conn.execute(
            """
            SELECT * FROM lesson_runs
            WHERE user_id = ? AND lesson_id = ? AND mode = 'lesson' AND lang = ? AND finished = 0
            ORDER BY created_at DESC LIMIT 1
            """,
            (user["id"], lesson_id, user["lang"]),
        ).fetchone()
        if existing:
            created = datetime.fromisoformat(existing["created_at"])
            if datetime.now() - created < timedelta(hours=6):
                self._send(200, self._run_payload(user, existing))
                return
        import random

        unit = unit_of_lesson(lesson_id)
        exercises = make_exercises(unit, lesson["kind"], user["lang"], random.Random())
        run_id = secrets.token_hex(16)
        conn.execute(
            """
            INSERT INTO lesson_runs (id, user_id, lesson_id, mode, lang, exercises_json, created_at)
            VALUES (?, ?, ?, 'lesson', ?, ?, ?)
            """,
            (run_id, user["id"], lesson_id, user["lang"], json.dumps(exercises, ensure_ascii=False), stamp()),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM lesson_runs WHERE id = ?", (run_id,)).fetchone()
        self._send(200, self._run_payload(user, row))

    def _start_practice(self, conn, user):
        import random

        rows = conn.execute(
            """
            SELECT payload FROM mistakes
            WHERE user_id = ? AND lang = ?
            ORDER BY wrong_count DESC, exercise_key
            LIMIT 8
            """,
            (user["id"], user["lang"]),
        ).fetchall()
        exercises = []
        seen = set()
        for row in rows:
            exercise = json.loads(row["payload"])
            if exercise.get("key") in seen:
                continue
            seen.add(exercise.get("key"))
            exercise["id"] = secrets.token_hex(5)
            exercises.append(exercise)
        if len(exercises) < 6:
            unit = self._practice_unit(conn, user)
            extra = make_exercises(unit, "words", user["lang"], random.Random())
            for exercise in extra:
                if exercise["key"] in seen:
                    continue
                seen.add(exercise["key"])
                exercises.append(exercise)
                if len(exercises) >= 8:
                    break
        exercises = exercises[:8]
        run_id = secrets.token_hex(16)
        conn.execute(
            """
            INSERT INTO lesson_runs (id, user_id, lesson_id, mode, lang, exercises_json, created_at)
            VALUES (?, ?, 'practice', 'practice', ?, ?, ?)
            """,
            (run_id, user["id"], user["lang"], json.dumps(exercises, ensure_ascii=False), stamp()),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM lesson_runs WHERE id = ?", (run_id,)).fetchone()
        self._send(200, self._run_payload(user, row))

    def _practice_unit(self, conn, user):
        row = conn.execute(
            """
            SELECT lesson_id FROM lesson_progress
            WHERE user_id = ? AND stars > 0
            ORDER BY lesson_id DESC LIMIT 1
            """,
            (user["id"],),
        ).fetchone()
        if row:
            unit = unit_of_lesson(row["lesson_id"])
            if unit:
                return unit
        return unit_by_id("a1-hello")

    def _run_payload(self, user, row):
        exercises = json.loads(row["exercises_json"])
        index = row["answered"]
        lesson = lesson_by_id(row["lesson_id"]) if row["mode"] == "lesson" else None
        unit = unit_of_lesson(row["lesson_id"]) if lesson else None
        lang = user["lang"]
        title = kind_title(lesson["kind"], lang) if lesson else ("Практика" if lang == "ru" else "Практика")
        if lang == "uk" and not lesson:
            title = "Практика"
        tip = ""
        tip_title = ""
        if lesson and lesson["kind"] == "grammar" and unit:
            tip = unit["grammar_tip"][lang]
            tip_title = unit["grammar_title"][lang]
        exercise = public_exercise(exercises[index]) if index < len(exercises) else None
        return {
            "run_id": row["id"],
            "mode": row["mode"],
            "lesson_id": row["lesson_id"],
            "title": title,
            "unit_title": unit["title"][lang] if unit else title,
            "tip": tip,
            "tip_title": tip_title,
            "index": index + 1 if exercise else len(exercises),
            "total": len(exercises),
            "correct": row["correct"],
            "exercise": exercise,
        }

    def _check(self, conn, user, body):
        run = conn.execute(
            "SELECT * FROM lesson_runs WHERE id = ? AND user_id = ?",
            (str(body.get("run_id") or ""), user["id"]),
        ).fetchone()
        if not run or run["finished"]:
            self._error(404, "not_found")
            return
        exercises = json.loads(run["exercises_json"])
        index = run["answered"]
        if index >= len(exercises):
            self._error(400, "finished")
            return
        exercise = exercises[index]
        if body.get("exercise_id") and body.get("exercise_id") != exercise["id"]:
            self._error(409, "stale")
            return
        ok = grade(exercise, body.get("answer") or {})
        correct = run["correct"] + (1 if ok else 0)
        answered = index + 1
        if ok:
            conn.execute(
                """
                UPDATE mistakes SET wrong_count = wrong_count - 1
                WHERE user_id = ? AND exercise_key = ? AND lang = ?
                """,
                (user["id"], exercise["key"], run["lang"]),
            )
            conn.execute(
                "DELETE FROM mistakes WHERE user_id = ? AND exercise_key = ? AND lang = ? AND wrong_count <= 0",
                (user["id"], exercise["key"], run["lang"]),
            )
        elif run["mode"] == "lesson":
            conn.execute(
                """
                INSERT INTO mistakes (user_id, exercise_key, lang, payload, wrong_count)
                VALUES (?, ?, ?, ?, 1)
                ON CONFLICT(user_id, exercise_key, lang) DO UPDATE SET
                    wrong_count = wrong_count + 1,
                    payload = excluded.payload
                """,
                (user["id"], exercise["key"], run["lang"], json.dumps(exercise, ensure_ascii=False)),
            )
        conn.execute(
            "UPDATE lesson_runs SET answered = ?, correct = ? WHERE id = ?",
            (answered, correct, run["id"]),
        )
        conn.commit()
        has_next = answered < len(exercises)
        fresh = refresh_user(conn, user["id"])
        self._send(
            200,
            {
                "correct": ok,
                "reveal": exercise.get("reveal") or "",
                "explain": exercise.get("explain") or "",
                "gems": fresh["gems"],
                "progress": {"index": answered, "total": len(exercises), "correct": correct},
                "next": public_exercise(exercises[answered]) if has_next else None,
            },
        )

    def _finish(self, conn, user, body):
        run = conn.execute(
            "SELECT * FROM lesson_runs WHERE id = ? AND user_id = ?",
            (str(body.get("run_id") or ""), user["id"]),
        ).fetchone()
        if not run:
            self._error(404, "not_found")
            return
        if run["finished"] and run["result_json"]:
            self._send(200, json.loads(run["result_json"]))
            return
        total = len(json.loads(run["exercises_json"]))
        correct = run["correct"]
        answered = run["answered"]
        ratio = (correct / total) if total else 0
        mode = run["mode"]
        if mode == "practice":
            passed = answered == total and total > 0
            stars = 3 if correct == total and passed else (2 if ratio >= 0.85 else 1 if passed else 0)
            xp_gain = correct * 4
            gems_gain = 0
        else:
            passed = answered == total and ratio >= 0.70
            if not passed:
                stars = 0
                xp_gain = 0
                gems_gain = 0
            else:
                stars = 3 if correct == total else (2 if ratio >= 0.85 else 1)
                previous = conn.execute(
                    "SELECT times_done FROM lesson_progress WHERE user_id = ? AND lesson_id = ?",
                    (user["id"], run["lesson_id"]),
                ).fetchone()
                times = previous["times_done"] if previous else 0
                xp_gain = correct * (10 if times == 0 else 3) + (20 if correct == total and times == 0 else 0)
                gems_gain = (6 if times == 0 else 0) + (4 if correct == total and times == 0 else 0)
                prev_row = conn.execute(
                    "SELECT stars, best_accuracy, xp_awarded FROM lesson_progress WHERE user_id = ? AND lesson_id = ?",
                    (user["id"], run["lesson_id"]),
                ).fetchone()
                if prev_row:
                    best_stars = max(stars, prev_row["stars"])
                    best_accuracy = max(ratio, prev_row["best_accuracy"])
                    conn.execute(
                        """
                        UPDATE lesson_progress
                        SET stars = ?, best_accuracy = ?, times_done = times_done + 1, xp_awarded = xp_awarded + ?
                        WHERE user_id = ? AND lesson_id = ?
                        """,
                        (best_stars, best_accuracy, xp_gain, user["id"], run["lesson_id"]),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO lesson_progress (user_id, lesson_id, stars, best_accuracy, times_done, xp_awarded)
                        VALUES (?, ?, ?, ?, 1, ?)
                        """,
                        (user["id"], run["lesson_id"], stars, ratio, xp_gain),
                    )
        streak = touch_activity(conn, user)
        conn.execute(
            "UPDATE users SET xp = xp + ?, gems = gems + ?, daily_xp = daily_xp + ?, daily_date = ? WHERE id = ?",
            (xp_gain, gems_gain, xp_gain, today(), user["id"]),
        )
        result = {
            "passed": passed,
            "stars": stars,
            "accuracy": round(ratio * 100),
            "correct": correct,
            "total": total,
            "xp_gain": xp_gain,
            "gems_gain": gems_gain,
            "streak": streak,
            "mode": mode,
            "next_lesson_id": next_lesson_id(run["lesson_id"]) if mode == "lesson" and passed else None,
        }
        conn.execute(
            "UPDATE lesson_runs SET finished = 1, result_json = ? WHERE id = ?",
            (json.dumps(result, ensure_ascii=False), run["id"]),
        )
        conn.commit()
        fresh = refresh_user(conn, user["id"])
        result["user"] = public_user(conn, fresh)
        conn.execute(
            "UPDATE lesson_runs SET result_json = ? WHERE id = ?",
            (json.dumps(result, ensure_ascii=False), run["id"]),
        )
        conn.commit()
        self._send(200, result)

    def _leaderboard(self, conn, user):
        rows = conn.execute(
            "SELECT id, username, display_name, xp, streak, last_active, best_streak, lang, is_admin FROM users ORDER BY xp DESC, username"
        ).fetchall()
        board = []
        for row in rows:
            item = dict(row)
            board.append(
                {
                    "username": item["username"],
                    "display_name": item["display_name"],
                    "xp": item["xp"],
                    "streak": visible_streak(item),
                    "lang": item["lang"],
                    "is_admin": bool(item["is_admin"]),
                    "you": item["id"] == user["id"],
                }
            )
        self._send(200, {"leaders": board})

    def _words(self, conn, user, query):
        level = (query.get("level") or [""])[0].upper()
        text = (query.get("q") or [""])[0].strip().casefold()
        translated = (query.get("translated") or ["0"])[0] == "1"
        try:
            page = max(1, int((query.get("page") or ["1"])[0]))
        except ValueError:
            page = 1
        where = ["1=1"]
        params = []
        if level in {"A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2"}:
            where.append("level = ?")
            params.append(level)
        if translated:
            where.append("(COALESCE(ru, '') != '' OR COALESCE(uk, '') != '')")
        if text:
            where.append("(head_l LIKE ? OR COALESCE(ru_l, '') LIKE ? OR COALESCE(uk_l, '') LIKE ?)")
            like = f"%{text}%"
            params.extend([like, like, like])
        clause = " AND ".join(where)
        total = conn.execute(f"SELECT COUNT(*) FROM words WHERE {clause}", params).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT headword, pos, level, source, ru, uk FROM words
            WHERE {clause}
            ORDER BY head_l, pos
            LIMIT 40 OFFSET ?
            """,
            [*params, (page - 1) * 40],
        ).fetchall()
        counts = conn.execute(
            """
            SELECT level,
                   COUNT(*) AS total,
                   SUM(CASE WHEN COALESCE(ru, '') != '' OR COALESCE(uk, '') != '' THEN 1 ELSE 0 END) AS translated
            FROM words
            GROUP BY level
            """
        ).fetchall()
        self._send(
            200,
            {
                "page": page,
                "pages": max(1, (total + 39) // 40),
                "total": total,
                "items": [dict(row) for row in rows],
                "counts": {row["level"]: {"total": row["total"], "translated": row["translated"]} for row in counts},
            },
        )

    def _grammar(self, conn, user, query):
        level = (query.get("level") or ["A1"])[0].upper()
        if level not in {"A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2"}:
            level = "A1"
        text = (query.get("q") or [""])[0].strip()
        try:
            page = max(1, int((query.get("page") or ["1"])[0]))
        except ValueError:
            page = 1
        where = ["level = ?"]
        params = [level]
        if text:
            where.append("item LIKE ?")
            params.append(f"%{text}%")
        clause = " AND ".join(where)
        total = conn.execute(f"SELECT COUNT(*) FROM grammar WHERE {clause}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT item, sentence_type, level FROM grammar WHERE {clause} ORDER BY item LIMIT 50 OFFSET ?",
            [*params, (page - 1) * 50],
        ).fetchall()
        lang = user["lang"]
        items = []
        for row in rows:
            label = SENTENCE_TYPES.get(row["sentence_type"], {}).get(lang, "")
            items.append({"item": row["item"], "level": row["level"], "sentence_type": label})
        self._send(200, {"page": page, "pages": max(1, (total + 49) // 50), "total": total, "items": items, "level": level})


class DualStackServer(ThreadingHTTPServer):
    address_family = socket.AF_INET6
    allow_reuse_address = True

    def server_bind(self):
        self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        super().server_bind()


def make_server(port=8765):
    ensure_db()
    try:
        return DualStackServer(("::", port), App)
    except OSError:
        return ThreadingHTTPServer(("0.0.0.0", port), App)


def allow_phone(port):
    if os.name != "nt":
        return
    try:
        subprocess.run(
            [
                "netsh", "advfirewall", "firewall", "add", "rule",
                f"name=Lumen {port}", "dir=in", "action=allow",
                "protocol=TCP", f"localport={port}", "profile=any",
            ],
            check=False,
            capture_output=True,
            timeout=8,
        )
    except (OSError, subprocess.TimeoutExpired):
        return


def lan_ip():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except OSError:
        return "127.0.0.1"


def ensure_https_cert(ip):
    cert_path = ROOT / "data" / "lumen.crt"
    key_path = ROOT / "data" / "lumen.key"
    stamp_path = ROOT / "data" / "lumen.ip"
    if cert_path.is_file() and key_path.is_file() and stamp_path.is_file() and stamp_path.read_text(encoding="utf-8").strip() == ip:
        return cert_path, key_path
    try:
        import datetime
        import ipaddress

        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
    except ImportError:
        return None, None
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Lumen")])
    names = [x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
    try:
        names.append(x509.IPAddress(ipaddress.ip_address(ip)))
    except ValueError:
        pass
    now = datetime.datetime.utcnow()
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=3650))
        .add_extension(x509.SubjectAlternativeName(names), critical=False)
        .sign(key, hashes.SHA256())
    )
    cert_path.parent.mkdir(parents=True, exist_ok=True)
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption())
    )
    stamp_path.write_text(ip, encoding="utf-8")
    return cert_path, key_path


def start_https(ip):
    global HTTPS_PORT
    cert, key = ensure_https_cert(ip)
    if not cert:
        return None
    port = 8443
    try:
        server = make_server(port)
    except OSError:
        return None
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    server.socket = ctx_wrap(server, context)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    HTTPS_PORT = port
    allow_phone(port)
    return port


def ctx_wrap(server, context):
    return context.wrap_socket(server.socket, server_side=True)


def main():
    port = 8765
    server = None
    for candidate in range(port, port + 6):
        try:
            server = make_server(candidate)
            port = candidate
            break
        except OSError:
            continue
    if server is None:
        raise SystemExit("No free port between 8765 and 8770")
    ip = lan_ip()
    allow_phone(port)
    https_port = start_https(ip)
    print("Lumen is running", flush=True)
    print(f"  on this computer: http://127.0.0.1:{port}/", flush=True)
    print(f"  on your phone:    http://{ip}:{port}/", flush=True)
    print("  iPhone: same Wi-Fi, not mobile data. The address must include :8765.", flush=True)
    print("Demo accounts, password lumen2026: alex, ostap, mira, admin", flush=True)
    threading.Timer(0.6, lambda: webbrowser.open(f"http://127.0.0.1:{port}/")).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped")


if __name__ == "__main__":
    main()
