"""Exercise the local API: accounts, both languages, locks, lessons, word bank."""

import json
import sqlite3
import threading
import urllib.error
import urllib.request
from datetime import datetime
from urllib.parse import parse_qsl, urlencode

from lumen.build_db import DB_PATH
from lumen.server import make_server


def call(base, path, token=None, body=None, method=None):
    if "?" in path:
        route, query = path.split("?", 1)
        path = route + "?" + urlencode(parse_qsl(query, keep_blank_values=True), encoding="utf-8")
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        base + path,
        data=data,
        method=method or ("POST" if body is not None else "GET"),
        headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + token} if token else {})},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))


def reset_fixtures():
    conn = sqlite3.connect(DB_PATH)
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute("DELETE FROM sessions WHERE user_id IN (SELECT id FROM users WHERE username = 'solomiya')")
    conn.execute("DELETE FROM lesson_progress WHERE user_id IN (SELECT id FROM users WHERE username = 'solomiya')")
    conn.execute("DELETE FROM users WHERE username = 'solomiya'")
    conn.execute(
        """
        DELETE FROM lesson_runs WHERE user_id = (SELECT id FROM users WHERE username = 'ostap')
        """
    )
    conn.execute("DELETE FROM mistakes WHERE user_id = (SELECT id FROM users WHERE username = 'ostap')")
    conn.execute(
        "UPDATE users SET hearts = 5, hearts_at = ?, lang = 'uk' WHERE username = 'ostap'",
        (now,),
    )
    conn.execute("UPDATE users SET lang = 'ru' WHERE username = 'alex'")
    conn.commit()
    conn.close()


def main():
    reset_fixtures()
    server = make_server(8799)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = "http://127.0.0.1:8799"
    problems = []
    try:
        return _run(base, problems)
    finally:
        server.shutdown()


def _run(base, problems):

    def check(name, cond):
        print(("OK  " if cond else "FAIL") + " " + name)
        if not cond:
            problems.append(name)

    status, health = call(base, "/api/health")
    check("health", status == 200 and health.get("ok"))

    status, bad = call(base, "/api/login", body={"username": "alex", "password": "wrong"})
    check("bad password rejected", status == 401 and bad.get("error") == "bad_login")

    status, alex = call(base, "/api/login", body={"username": "alex", "password": "lumen2026"})
    status_o, ostap = call(base, "/api/login", body={"username": "ostap", "password": "lumen2026"})
    status_m, mira = call(base, "/api/login", body={"username": "mira", "password": "lumen2026"})
    check("seed logins", status == 200 and status_o == 200 and status_m == 200)
    check("ostap is Ukrainian", ostap["user"]["lang"] == "uk")
    check("alex is Russian", alex["user"]["lang"] == "ru")
    check("mira starts clean", mira["user"]["xp"] == 0 and mira["user"]["lang"] == "uk")

    hashes = sqlite3.connect(DB_PATH).execute("SELECT password_hash FROM users").fetchall()
    check("passwords are hashed", all(":" in row[0] and "lumen2026" not in row[0] for row in hashes))

    _, course = call(base, "/api/course", ostap["token"])
    levels = [level["id"] for level in course["levels"]]
    check("levels include A3 and B3", levels == ["A1", "A2", "A3", "B1", "B2", "B3", "C1"])
    first_unit = course["levels"][0]["units"][0]
    states = [lesson["state"] for lesson in first_unit["lessons"]]
    check("ostap progress unlocks the third lesson", states[:2] == ["done", "done"] and states[2] == "open")
    titles = [lesson["title"] for lesson in first_unit["lessons"]]
    check("path titles in Ukrainian", "Збірка" in titles and "Граматика" in titles)

    _, alex_course = call(base, "/api/course", alex["token"])
    alex_titles = [lesson["title"] for lesson in alex_course["levels"][0]["units"][0]["lessons"]]
    check("path titles in Russian", "Сборка" in alex_titles and "Грамматика" in alex_titles)

    status, locked = call(base, "/api/lesson/start", mira["token"], {"lesson_id": "a1-town-words"})
    check("later lesson is locked", status == 403 and locked.get("error") == "locked")

    status, started = call(base, "/api/lesson/start", ostap["token"], {"lesson_id": "a1-hello-words"})
    check("ukrainian lesson starts", status == 200 and started["exercise"])
    run_id = started["run_id"]
    row = sqlite3.connect(DB_PATH).execute("SELECT exercises_json FROM lesson_runs WHERE id = ?", (run_id,)).fetchone()
    exercises = json.loads(row[0])
    blob = json.dumps(exercises, ensure_ascii=False)
    check("lesson has no Russian-only letters in Ukrainian", not any(ch in blob for ch in "ыэъёЫЭЪЁ"))
    check("lesson contains Ukrainian letters", any(ch in blob for ch in "іїєґ"))

    public = started["exercise"]
    check("answer key stays on the server", "correct_id" not in public and "accept" not in public)

    secret = exercises[0]
    if secret["type"] in ("choice", "listen", "fill"):
        wrong = next(opt["id"] for opt in secret["options"] if opt["id"] != secret["correct_id"])
        status, marked = call(
            base,
            "/api/lesson/check",
            ostap["token"],
            {"run_id": run_id, "exercise_id": public["id"], "answer": {"option_id": wrong}},
        )
        check("wrong answer stays in the lesson", status == 200 and marked["correct"] is False and marked.get("next"))
        nxt = marked["next"]
        secret_next = exercises[1]
        right = secret_next["correct_id"]
        status, marked = call(
            base,
            "/api/lesson/check",
            ostap["token"],
            {"run_id": run_id, "exercise_id": nxt["id"], "answer": {"option_id": right}},
        )
        check("right answer continues", status == 200 and marked["correct"] is True and "hearts" not in marked)

    status, reg = call(
        base,
        "/api/register",
        body={"username": "solomiya", "display_name": "Соломія", "password": "lumen2026", "lang": "uk"},
    )
    check("register Ukrainian account", status == 200 and reg["user"]["lang"] == "uk")
    status, again = call(
        base,
        "/api/register",
        body={"username": "solomiya", "display_name": "Соломія", "password": "lumen2026", "lang": "ru"},
    )
    check("duplicate username blocked", status == 409)

    _, words = call(base, "/api/words?level=C1&page=1", alex["token"])
    check("C1 word bank", words["total"] > 500)
    _, translated = call(base, "/api/words?q=яблуко&translated=1", ostap["token"])
    check("Ukrainian search finds apple", any(item["headword"].lower() == "apple" for item in translated["items"]))
    _, grammar = call(base, "/api/grammar?level=A1", alex["token"])
    check("grammar catalogue", grammar["total"] > 20)

    _, board = call(base, "/api/leaderboard", alex["token"])
    names = [item["username"] for item in board["leaders"]]
    check("leaderboard has the accounts", {"alex", "ostap", "mira", "admin", "solomiya"} <= set(names))

    status, switched = call(base, "/api/settings", alex["token"], {"lang": "uk"})
    _, switched_course = call(base, "/api/course", alex["token"])
    uk_title = switched_course["levels"][0]["units"][0]["title"]
    call(base, "/api/settings", alex["token"], {"lang": "ru"})
    check("language switch keeps progress and changes copy", status == 200 and switched["user"]["lang"] == "uk" and "Вітання" in uk_title)
    reset_fixtures()

    print("PROBLEMS" if problems else "ALL CHECKS PASSED", len(problems))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
