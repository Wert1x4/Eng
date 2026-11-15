"""Build a lesson in the learner's language and grade answers."""

import re
import uuid

from lumen.course_data import LESSON_KINDS, LEVELS, UNITS, lesson_by_id, unit_by_id

_CYR = re.compile(r"[А-Яа-яЁёІіЇїЄєҐґ]")
_CONTRACTIONS = (
    ("i am", "i'm"),
    ("you are", "you're"),
    ("he is", "he's"),
    ("she is", "she's"),
    ("it is", "it's"),
    ("we are", "we're"),
    ("they are", "they're"),
    ("do not", "don't"),
    ("does not", "doesn't"),
    ("did not", "didn't"),
    ("cannot", "can't"),
    ("can not", "can't"),
    ("is not", "isn't"),
    ("are not", "aren't"),
    ("i will", "i'll"),
    ("she will", "she'll"),
    ("we will", "we'll"),
    ("they will", "they'll"),
    ("i have", "i've"),
    ("that is", "that's"),
    ("what is", "what's"),
    ("let us", "let's"),
    ("will not", "won't"),
    ("i would", "i'd"),
    ("she would", "she'd"),
    ("there is", "there's"),
)


def norm(text):
    text = (text or "").strip().lower().replace("ё", "е")
    text = text.replace("’", "'").replace("ʼ", "'").replace("`", "'")
    text = re.sub(r"[^\w\s'-]", "", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def tokens(sentence):
    text = (sentence or "").replace("—", " ").replace("–", " ")
    text = re.sub(r"[^\w\s'-]", " ", text, flags=re.UNICODE)
    return [part for part in text.split() if part]


def variants(sentence):
    base = norm(sentence)
    found = {base}
    for full, short in _CONTRACTIONS:
        if full in base:
            found.add(base.replace(full, short))
        if short in base:
            found.add(base.replace(short, full))
    return found


def _pools():
    pools = {"en": [], "ru": [], "uk": []}
    for unit in UNITS:
        for word in unit["words"]:
            pools["en"].append(word["en"])
            pools["ru"].append(word["ru"])
            pools["uk"].append(word["uk"])
        for sentence in unit["sentences"]:
            pools["en"].append(sentence["en"])
            pools["ru"].append(sentence["ru"])
            pools["uk"].append(sentence["uk"])
    return pools


POOLS = None


def all_pools():
    global POOLS
    if POOLS is None:
        POOLS = _pools()
    return POOLS


def _choice(prompt, reveal, correct, preferred, extra, rng, explain="", speak=None, type_name=None):
    texts = [correct]
    bags = [list(preferred), list(extra)]
    for bag in bags:
        rng.shuffle(bag)
    for item in bags[0] + bags[1]:
        if not item or norm(item) == norm(correct) or item in texts:
            continue
        texts.append(item)
        if len(texts) == 4:
            break
    if len(texts) < 4:
        raise ValueError(f"Not enough options for «{correct}»")
    rng.shuffle(texts)
    options = [{"id": "abcd"[i], "text": texts[i]} for i in range(4)]
    correct_id = next(item["id"] for item in options if item["text"] == correct)
    kind = type_name or ("listen" if speak else "choice")
    if kind == "listen":
        direction = "listen"
    elif kind == "fill":
        direction = "fill"
    elif _CYR.search(prompt or ""):
        direction = "to_en"
    else:
        direction = "to_native"
    exercise = {
        "id": uuid.uuid4().hex[:10],
        "type": kind,
        "dir": direction,
        "prompt": prompt,
        "options": options,
        "correct_id": correct_id,
        "reveal": reveal,
        "explain": explain or "",
        "key": f"{kind}|{norm(prompt)}|{norm(reveal)}",
    }
    if speak:
        exercise["speak"] = speak
    return exercise


def _build(prompt, english, rng):
    answer = tokens(english)
    if not (3 <= len(answer) <= 8):
        return None
    bank = list(answer)
    for _ in range(5):
        rng.shuffle(bank)
        if bank != answer:
            break
    return {
        "id": uuid.uuid4().hex[:10],
        "type": "build",
        "dir": "build",
        "prompt": prompt,
        "tokens": bank,
        "answer_tokens": answer,
        "reveal": " ".join(answer),
        "explain": "",
        "key": f"build|{norm(prompt)}|{norm(english)}",
    }


def _type(prompt, english):
    return {
        "id": uuid.uuid4().hex[:10],
        "type": "type",
        "dir": "type",
        "prompt": prompt,
        "accept": sorted(variants(english)),
        "reveal": english.rstrip(".!?"),
        "explain": "",
        "key": f"type|{norm(prompt)}|{norm(english)}",
    }


def _match(words, lang, rng):
    pool = list(words)
    rng.shuffle(pool)
    chosen = []
    seen_en, seen_native = set(), set()
    for word in pool:
        if norm(word["en"]) in seen_en or norm(word[lang]) in seen_native:
            continue
        chosen.append(word)
        seen_en.add(norm(word["en"]))
        seen_native.add(norm(word[lang]))
        if len(chosen) == 4:
            break
    if len(chosen) < 4:
        return None
    left = [{"id": f"l{i}", "text": chosen[i]["en"]} for i in range(4)]
    right = [{"id": f"r{i}", "text": chosen[i][lang]} for i in range(4)]
    pairs = {f"l{i}": f"r{i}" for i in range(4)}
    rng.shuffle(right)
    reveal = " · ".join(f"{word['en']} — {word[lang]}" for word in chosen)
    return {
        "id": uuid.uuid4().hex[:10],
        "type": "match",
        "dir": "match",
        "prompt": "",
        "left": left,
        "right": right,
        "pairs": pairs,
        "reveal": reveal,
        "explain": "",
        "key": "match|" + "|".join(norm(word["en"]) for word in chosen),
    }


def _short_lines(unit, lang):
    lines = []
    seen = set()
    for sentence in list(unit["sentences"]) + [
        {"en": word["ex_en"], lang: word[f"ex_{lang}"]} for word in unit["words"]
    ]:
        english = sentence["en"]
        if norm(english) in seen:
            continue
        if 3 <= len(tokens(english)) <= 7:
            seen.add(norm(english))
            lines.append(sentence)
    return lines


def make_exercises(unit, kind, lang, rng):
    pools = all_pools()
    unit_en = [word["en"] for word in unit["words"]]
    unit_native = [word[lang] for word in unit["words"]] + [sentence[lang] for sentence in unit["sentences"]]
    exercises = []

    def word_choice(word, to_english):
        if to_english:
            return _choice(word[lang], word["en"], word["en"], unit_en, pools["en"], rng)
        return _choice(word["en"], word[lang], word[lang], [w[lang] for w in unit["words"]], pools[lang], rng)

    def sentence_choice(sentence, to_english):
        natives = [item[lang] for item in unit["sentences"]]
        if to_english:
            return _choice(sentence[lang], sentence["en"], sentence["en"], [s["en"] for s in unit["sentences"]], pools["en"], rng)
        return _choice(sentence["en"], sentence[lang], sentence[lang], natives, pools[lang], rng)

    if kind == "words":
        for word in unit["words"][:4]:
            exercises.append(word_choice(word, True))
        for word in unit["words"][4:7]:
            exercises.append(word_choice(word, False))
        matched = _match(unit["words"], lang, rng)
        exercises.append(matched or word_choice(unit["words"][0], False))
    elif kind == "phrases":
        sentences = unit["sentences"]
        for sentence in sentences[:3]:
            exercises.append(sentence_choice(sentence, False))
        for sentence in sentences[:2]:
            exercises.append(sentence_choice(sentence, True))
        for sentence in sentences[2:4]:
            exercises.append(
                _choice(
                    "",
                    sentence[lang],
                    sentence[lang],
                    [item[lang] for item in sentences],
                    pools[lang],
                    rng,
                    speak=sentence["en"].rstrip(".!?"),
                )
            )
    elif kind == "build":
        for sentence in _short_lines(unit, lang)[:6]:
            built = _build(sentence[lang], sentence["en"], rng)
            if built:
                exercises.append(built)
    elif kind == "grammar":
        for blank in unit["blanks"]:
            exercises.append(
                _choice(
                    blank["prompt"],
                    blank["answer"],
                    blank["answer"],
                    blank["options"],
                    [],
                    rng,
                    explain=blank["explain"][lang],
                    type_name="fill",
                )
            )
        for word in unit["words"][:2]:
            exercises.append(word_choice(word, False))
    elif kind == "check":
        lines = _short_lines(unit, lang)
        for sentence in unit["sentences"][:2]:
            exercises.append(_type(sentence[lang], sentence["en"]))
        for word in unit["words"][:2]:
            exercises.append(word_choice(word, True))
        for sentence in lines[:2]:
            built = _build(sentence[lang], sentence["en"], rng)
            if built:
                exercises.append(built)
        if unit["sentences"]:
            sentence = unit["sentences"][-1]
            exercises.append(
                _choice(
                    "",
                    sentence[lang],
                    sentence[lang],
                    [item[lang] for item in unit["sentences"]],
                    pools[lang],
                    rng,
                    speak=sentence["en"].rstrip(".!?"),
                )
            )
        if unit["blanks"]:
            blank = unit["blanks"][0]
            exercises.append(
                _choice(
                    blank["prompt"],
                    blank["answer"],
                    blank["answer"],
                    blank["options"],
                    [],
                    rng,
                    explain=blank["explain"][lang],
                    type_name="fill",
                )
            )
    else:
        raise ValueError(kind)
    if len(exercises) < 4:
        raise ValueError(f"{unit['id']} {kind} {lang} produced {len(exercises)}")
    return exercises


def public_exercise(exercise):
    hidden = {"correct_id", "accept", "pairs", "answer_tokens", "reveal", "explain", "key"}
    return {key: value for key, value in exercise.items() if key not in hidden}


def grade(exercise, answer):
    answer = answer or {}
    kind = exercise["type"]
    if kind in ("choice", "listen", "fill"):
        ok = answer.get("option_id") == exercise["correct_id"]
    elif kind == "build":
        got = [norm(part) for part in (answer.get("tokens") or [])]
        ok = got == [norm(part) for part in exercise["answer_tokens"]]
    elif kind == "type":
        ok = norm(answer.get("text") or "") in set(exercise["accept"])
    elif kind == "match":
        raw = answer.get("pairs") or {}
        got = {str(key): str(value) for key, value in raw.items()} if isinstance(raw, dict) else {}
        ok = got == exercise["pairs"]
    else:
        ok = False
    return ok


def level_title(level, lang):
    for code, title in LEVELS:
        if code == level:
            return title[lang]
    return level


def kind_title(kind, lang):
    for code, title in LESSON_KINDS:
        if code == kind:
            return title[lang]
    return kind


def lesson_meta(lesson_id):
    lesson = lesson_by_id(lesson_id)
    if not lesson:
        return None
    return lesson


def unit_of_lesson(lesson_id):
    lesson = lesson_by_id(lesson_id)
    if not lesson:
        return None
    return unit_by_id(lesson["unit_id"])
