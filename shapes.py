"""Small constructors for course units."""


def W(en, ru, uk, ex_en, ex_ru, ex_uk):
    return {
        "en": en,
        "ru": ru,
        "uk": uk,
        "ex_en": ex_en,
        "ex_ru": ex_ru,
        "ex_uk": ex_uk,
    }


def S(en, ru, uk):
    return {"en": en, "ru": ru, "uk": uk}


def B(prompt, answer, options, ru, uk):
    return {
        "prompt": prompt,
        "answer": answer,
        "options": options,
        "explain": {"ru": ru, "uk": uk},
    }


def U(
    id,
    level,
    title_ru,
    title_uk,
    goal_ru,
    goal_uk,
    tip_title_ru,
    tip_title_uk,
    tip_ru,
    tip_uk,
    color,
    words,
    sentences,
    blanks,
):
    return {
        "id": id,
        "level": level,
        "title": {"ru": title_ru, "uk": title_uk},
        "goal": {"ru": goal_ru, "uk": goal_uk},
        "grammar_title": {"ru": tip_title_ru, "uk": tip_title_uk},
        "grammar_tip": {"ru": tip_ru, "uk": tip_uk},
        "color": color,
        "words": words,
        "sentences": sentences,
        "blanks": blanks,
    }
