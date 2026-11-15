const state = {
  token: localStorage.getItem("lumen_token") || "",
  phoneUrl: "",
  phoneLoading: false,
  lang: localStorage.getItem("lumen_lang") || "ru",
  user: null,
  screen: "loading",
  course: null,
  level: "A1",
  lesson: null,
  phase: "answer",
  feedback: null,
  pendingNext: null,
  result: null,
  words: null,
  grammar: null,
  wordTab: "words",
  wordLevel: "A1",
  wordQuery: "",
  wordPage: 1,
  wordTranslated: false,
  leaders: null,
  authMode: "login",
  draft: { username: "", password: "", display_name: "" },
  modal: null,
  toast: "",
  error: "",
  busy: false,
  selected: null,
  bank: [],
  built: [],
  typed: "",
  pairs: {},
  pick: null,
  armed: "",
  revealSpeak: false,
  focus: "",
};

const app = document.getElementById("app");
let audioCtx;

function lang() {
  return state.user?.lang || state.lang || "ru";
}
function t(key) {
  const pack = I18N[lang()] || I18N.ru;
  return pack[key] ?? I18N.ru[key] ?? key;
}
function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[ch]));
}
function sameText(a, b) {
  return String(a || "").trim().toLowerCase().replaceAll("ё", "е") === String(b || "").trim().toLowerCase().replaceAll("ё", "е");
}
function plural(n, one, few, many) {
  const n10 = n % 10;
  const n100 = n % 100;
  if (n10 === 1 && n100 !== 11) return one;
  if (n10 >= 2 && n10 <= 4 && (n100 < 12 || n100 > 14)) return few;
  return many;
}
function posLabel(pos) {
  return (POS[lang()] && POS[lang()][pos]) || pos || "";
}

async function api(path, options = {}) {
  if (!String(path).startsWith("/api/join") && window.lumenDevice) {
    return lumenDevice.handle(path, options);
  }
  let response;
  try {
    response = await fetch(path, {
      method: options.method || "GET",
      headers: {
        "Content-Type": "application/json",
        ...(state.token ? { Authorization: "Bearer " + state.token } : {}),
      },
      body: options.body ? JSON.stringify(options.body) : undefined,
    });
  } catch (error) {
    const err = new Error("offline");
    err.code = "offline";
    throw err;
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const err = new Error(data.error || "server");
    err.code = data.error || "server";
    throw err;
  }
  return data;
}

function tone(freq, length) {
  if (state.user && !state.user.sound_on) return;
  try {
    audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = "sine";
    osc.frequency.value = freq;
    gain.gain.value = 0.045;
    osc.connect(gain);
    gain.connect(audioCtx.destination);
    osc.start();
    gain.gain.exponentialRampToValueAtTime(0.0001, audioCtx.currentTime + length);
    osc.stop(audioCtx.currentTime + length);
  } catch (error) {
    /* sound is optional */
  }
}
function speak(text) {
  if (!text || !window.speechSynthesis) return false;
  const utter = new SpeechSynthesisUtterance(text);
  utter.lang = "en-US";
  utter.rate = 0.92;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(utter);
  return true;
}
function mascot(mood) {
  const smile = mood === "bad" ? "M26 42c3-3 9-3 12 0" : "M26 38c3 3 9 3 12 0";
  return `<svg class="mascot" viewBox="0 0 64 64" aria-hidden="true">
    <circle cx="32" cy="30" r="16" fill="#f6d56b"/>
    <circle cx="26" cy="28" r="2" fill="#17241c"/>
    <circle cx="38" cy="28" r="2" fill="#17241c"/>
    <path d="${smile}" fill="none" stroke="#17241c" stroke-width="2" stroke-linecap="round"/>
  </svg>`;
}
const UNIT_ICONS = {
  "a1-hello": "chat", "a1-numbers": "hash", "a1-people": "users", "a1-food": "apple",
  "a1-day": "sun", "a1-home": "home", "a1-town": "city", "a1-now": "clock",
  "a2-yesterday": "back", "a2-stories": "book", "a2-shop": "bag", "a2-trip": "map",
  "a2-health": "plus", "a2-work": "case", "a2-compare": "scales", "a2-plans": "calendar",
  "a3-routine": "clock", "a3-while": "back", "a3-amount": "drops", "a3-invite": "chat",
  "a3-reason": "link", "a3-best": "star", "a3-just": "check", "a3-could": "hand",
  "b1-experience": "star", "b1-study": "book", "b1-opinion": "chat", "b1-nature": "leaf",
  "b1-people": "users", "b1-story": "film", "b1-city": "city", "b1-if": "split",
  "b2-lately": "clock", "b2-usedto": "back", "b2-passive": "repeat", "b2-guess": "search",
  "b2-report": "quote", "b2-linkers": "link", "b2-wish": "spark", "b2-if2": "split",
  "b3-if3": "split", "b3-regret": "back", "b3-despite": "shield", "b3-whose": "search",
  "b3-bythen": "calendar", "b3-done": "case", "b3-such": "spark", "b3-asked": "quote",
  "c1-hedge": "shield", "c1-eval": "scales", "c1-contrast": "split", "c1-research": "search",
  "c1-society": "users", "c1-nominal": "layers", "c1-tone": "chat", "c1-master": "star",
};

function icon(name, size = 22) {
  const paths = {
    learn: "M8 18h8M8 12h8M6 6h12v16H6z",
    words: "M6 5h10a3 3 0 013 3v14H9a3 3 0 00-3 3V5zM6 22a3 3 0 013-3h10",
    practice: "M12 4v4M8 6l2 2M16 6l-2 2M6 14a6 6 0 1012 0",
    profile: "M12 12a3.5 3.5 0 100-7 3.5 3.5 0 000 7zM5 20c1.2-3 3.4-4.5 7-4.5S17.8 17 19 20",
    phrases: "M5 6h10a3 3 0 013 3v5a3 3 0 01-3 3H9l-4 3v-3H5a2 2 0 01-2-2V8a2 2 0 012-2z",
    build: "M4 9l8-4 8 4-8 4-8-4zM4 13l8 4 8-4",
    grammar: "M5 19l3-8 3 8M6 16h4M14 5h5v14h-5",
    check: "M5 12l4 4 10-10",
    lock: "M8 11V8a4 4 0 018 0v3M6 11h12v9H6z",
    chat: "M5 6h14v9H9l-4 3z",
    hash: "M9 4v16M15 4v16M4 9h16M4 15h16",
    users: "M8 12a3 3 0 100-6 3 3 0 000 6zM16 11a2.5 2.5 0 100-5 2.5 2.5 0 000 5zM3 19c.6-2.4 2.4-3.5 5-3.5s4.4 1.1 5 3.5M14 15.5c1.8 0 3.2.7 3.8 2.5",
    apple: "M12 8c-2 0-4 2-4 5 0 4 2 7 4 7s4-3 4-7c0-3-2-5-4-5zM12 8c1-2 2-3 4-3",
    sun: "M12 8a4 4 0 100 8 4 4 0 000-8zM12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M19 5l-1.5 1.5M6.5 17.5L5 19",
    home: "M4 11l8-7 8 7v9H4zM10 20v-6h4v6",
    city: "M4 20V9l5-3v14M9 20V6l6 3v11M15 20v-8l5 2v6",
    clock: "M12 7v5l3 2M12 4a8 8 0 100 16 8 8 0 000-16z",
    back: "M9 8H5v4M5 8a8 8 0 11-1 4",
    book: "M6 5h10a3 3 0 013 3v14H9a3 3 0 00-3 3V5zM6 22a3 3 0 013-3h10",
    bag: "M6 8h12l-1 12H7L6 8zM9 8V6a3 3 0 016 0v2",
    map: "M4 6l5-2 6 2 5-2v14l-5 2-6-2-5 2zM9 4v14M15 6v14",
    plus: "M12 6v12M6 12h12",
    case: "M4 8h16v11H4zM9 8V6h6v2",
    scales: "M12 4v16M5 20h14M6 8h12M6 8l-3 6h6l-3-6zM18 8l-3 6h6l-3-6z",
    calendar: "M5 5h14v15H5zM5 9h14M8 3v4M16 3v4",
    drops: "M12 4s5 6 5 9a5 5 0 11-10 0c0-3 5-9 5-9z",
    hand: "M8 11V6M12 11V4M16 11V7M8 11l-2 2v3a4 4 0 004 4h4a4 4 0 004-4v-5",
    star: "M12 3l2.2 5.2L20 9l-4 3.6L17.2 18 12 15.2 6.8 18 8 12.6 4 9l5.8-.8z",
    leaf: "M5 19C5 11 12 4 20 4 20 12 13 19 5 19zM8 16c2-2 5-5 8-8",
    film: "M5 6h14v12H5zM9 6v12M15 6v12M5 10h4M15 10h4M5 14h4M15 14h4",
    split: "M7 6v12M7 12h6l4-4M13 12l4 4",
    repeat: "M7 7h9a4 4 0 010 8H8M7 7l3-3M7 7l3 3",
    search: "M11 6a5 5 0 100 10 5 5 0 000-10zM15 15l4 4",
    quote: "M7 16c-2 0-3-1.5-3-3 2 0 3-1 3-3H5c0-2 1-3 3-3v3c0 3-1 6-1 6zm9 0c-2 0-3-1.5-3-3 2 0 3-1 3-3h-2c0-2 1-3 3-3v3c0 3-1 6-1 6z",
    link: "M9 12a3 3 0 013-3h3M15 12a3 3 0 01-3 3H9",
    spark: "M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2 2M16 16l2 2M18 6l-2 2M8 16l-2 2",
    shield: "M12 3l7 3v6c0 4-3 7-7 9-4-2-7-5-7-9V6z",
    layers: "M12 4l8 4-8 4-8-4 8-4zM4 12l8 4 8-4M4 16l8 4 8-4",
    flame: "M12 3s5 5 5 9a5 5 0 11-10 0c0-2 1-3 2-4 0 2 1 3 3 3 0-3 0-6 0-8z",
    gem: "M12 21l7-9-3-6H8L5 12z",
    target: "M12 4a8 8 0 100 16 8 8 0 000-16zM12 8a4 4 0 100 8 4 4 0 000-8z",
  };
  const draw = paths[name] || paths.book;
  return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="${draw}"></path></svg>`;
}

function render() {
  document.documentElement.lang = lang();
  document.title = "Lumen";
  document.body.classList.toggle("in-lesson", state.screen === "lesson");
  const focused = document.activeElement && document.activeElement.id;
  const caret = focused && document.activeElement.selectionStart;
  const views = {
    loading: loadingView,
    offline: offlineView,
    auth: authView,
    goal: goalView,
    path: pathView,
    lesson: lessonView,
    result: resultView,
    words: wordsView,
    practice: practiceView,
    profile: profileView,
  };
  app.innerHTML = (views[state.screen] || loadingView)();
  const screen = app.querySelector(".screen");
  const bar = screen && screen.querySelector(":scope > .nav");
  if (bar) {
    screen.classList.add("has-nav");
    const scroller = document.createElement("div");
    scroller.className = "scroller";
    while (screen.firstChild && screen.firstChild !== bar) scroller.appendChild(screen.firstChild);
    screen.insertBefore(scroller, bar);
  }
  paintPhone();
  if (state.focus && document.getElementById(state.focus)) {
    const el = document.getElementById(state.focus);
    el.focus();
    if (caret != null && el.setSelectionRange) el.setSelectionRange(caret, caret);
  } else if (focused && document.getElementById(focused)) {
    const el = document.getElementById(focused);
    el.focus();
    if (caret != null && el.setSelectionRange) el.setSelectionRange(caret, caret);
  }
  state.focus = "";
  const exercise = state.lesson && state.lesson.exercise;
  if (state.screen === "lesson" && exercise && exercise.type === "listen" && state.phase === "answer" && state.armedSpeak !== exercise.id) {
    state.armedSpeak = exercise.id;
    setTimeout(() => speak(exercise.speak), 200);
  }
}

function loadingView() {
  return `<div class="center-screen">${esc(t("loading"))}</div>`;
}
function offlineView() {
  const message = location.protocol === "file:" || isLocalHost() ? t("server") : t("offlineHost");
  return `<div class="center-screen"><p>${esc(message)}</p><button class="primary" data-action="boot">${esc(t("retry"))}</button></div>`;
}
function langSwitch() {
  return `<div class="lang-switch" role="group" aria-label="${esc(t("langName"))}">
    <button type="button" data-action="set-lang" data-lang="ru" class="${lang() === "ru" ? "on" : ""}">${esc(t("ru"))}</button>
    <button type="button" data-action="set-lang" data-lang="uk" class="${lang() === "uk" ? "on" : ""}">${esc(t("uk"))}</button>
  </div>`;
}
function authView() {
  const reg = state.authMode === "register";
  const demos = [
    ["alex", t("alex")],
    ["ostap", t("ostap")],
    ["mira", t("mira")],
    ["admin", t("adminUser")],
  ];
  return `<div class="screen auth-screen">
    <div class="brand"><img src="icon.svg" alt=""><div><h1>Lumen</h1><p>${esc(t("tagline"))}</p></div></div>
    ${langSwitch()}
    <form id="authForm" class="card">
      <label for="username">${esc(t("username"))}</label>
      <input id="username" name="username" autocomplete="username" value="${esc(state.draft.username)}">
      ${reg ? `<label for="display_name">${esc(t("displayName"))}</label><input id="display_name" value="${esc(state.draft.display_name)}">` : ""}
      <label for="password">${esc(t("password"))}</label>
      <input id="password" type="password" autocomplete="${reg ? "new-password" : "current-password"}" value="${esc(state.draft.password)}">
      <p class="err">${esc(state.error)}</p>
      <button class="primary" type="submit">${esc(reg ? t("register") : t("login"))}</button>
      <button class="linkish" type="button" data-action="auth-mode">${esc(reg ? t("haveAccount") : t("noAccount"))}</button>
    </form>
    <div class="card">
      <strong>${esc(t("demoTitle"))}</strong>
      <p class="hint">${esc(t("demoNote"))}</p>
      ${demos.map(([id, label]) => `<button class="demo" type="button" data-action="demo" data-user="${id}"><i>${esc(id[0].toUpperCase())}</i><b>${esc(id)}</b><span>${esc(label)}</span></button>`).join("")}
    </div>
    ${homeHint()}
  </div>`;
}
function goalView() {
  return `<div class="screen goal-screen">
    <div class="brand"><img src="icon.svg" alt=""><div><h1>Lumen</h1><p>${esc(t("goalLead"))}</p></div></div>
    ${[20, 50, 100].map((goal) => `<button class="goal-card" data-action="goal" data-goal="${goal}">${esc(t("goal" + goal))}</button>`).join("")}
  </div>`;
}
function ring() {
  const goal = state.user.daily_goal || 50;
  const value = Math.min(goal, state.user.daily_xp || 0);
  const length = 94;
  const dash = ((value / goal) * length).toFixed(1);
  return `<svg class="ring" viewBox="0 0 36 36" aria-hidden="true">
    <circle class="bg" cx="18" cy="18" r="15"></circle>
    <circle class="fg" cx="18" cy="18" r="15" stroke-dasharray="${dash} ${length}"></circle>
  </svg>`;
}
function shellTop() {
  const user = state.user;
  return `<header class="top">
      <div><p class="hello">${esc(t("welcome"))}, ${esc(user.display_name)}</p></div>
      <div class="pills">
        <span class="pill fire">${icon("flame", 16)} ${user.streak} ${esc(t("streak"))}</span>
        <span class="pill gem">${icon("gem", 16)} ${user.gems}</span>
      </div>
    </header>
    <div class="card daily">${ring()}<div><strong>${user.daily_xp} / ${user.daily_goal} XP</strong><span>${esc(t("daily"))}</span></div></div>
    ${state.toast ? `<div class="toast">${esc(state.toast)}</div>` : ""}`;
}
function nav(active) {
  const items = ["learn", "words", "practice", "profile"];
  return `<nav class="nav">${items.map((item) => `<button type="button" data-action="tab" data-tab="${item}" class="${item === active ? "on" : ""}">${icon(item)}${esc(t(item))}</button>`).join("")}</nav>`;
}
function pathView() {
  const level = (state.course?.levels || []).find((item) => item.id === state.level) || state.course?.levels?.[0];
  if (!level) return loadingView();
  const offsets = ["flex-start", "center", "flex-end", "center"];
  let index = 0;
  let pulsed = false;
  const units = level.units.map((unit) => {
    const lessons = unit.lessons.map((lesson) => {
      const align = offsets[index % offsets.length];
      index += 1;
      const stars = lesson.stars ? "★".repeat(lesson.stars) + "☆".repeat(3 - lesson.stars) : "";
      const mark = lesson.state === "locked" ? icon("lock", 26) : icon(lesson.kind, 28);
      const pulse = lesson.state === "open" && !pulsed;
      if (pulse) pulsed = true;
      return `<div class="node-row" style="justify-content:${align}">
        <div class="node-wrap">
          <button class="node ${lesson.state} ${pulse ? "pulse" : ""}" style="${lesson.state === "open" ? `background-color:${unit.color}` : ""}" data-action="open-lesson" data-id="${esc(lesson.id)}" data-state="${lesson.state}">${mark}${lesson.state === "done" ? `<span class="tick">✓</span>` : ""}</button>
          <div class="node-label">${esc(lesson.title)}</div>
          <div class="stars">${stars}</div>
        </div>
      </div>`;
    }).join("");
    return `<section class="unit">
      <div class="unit-banner" style="background-color:${unit.color}"><span class="unit-icon">${icon(UNIT_ICONS[unit.id] || "book", 22)}</span><div><h2>${esc(unit.title)}</h2><p>${esc(unit.goal)}</p></div></div>
      <div class="path">${lessons}</div>
    </section>`;
  }).join("");
  const chips = state.course.levels.map((item) => `<button class="chip ${item.id === level.id ? "on" : ""}" data-action="level" data-level="${item.id}">${item.id}</button>`).join("");
  return `<div class="screen">${shellTop()}
    <div class="levels">${chips}</div>
    <h2 style="margin:8px 0">${esc(level.id)} · ${esc(level.title)}</h2>${units}
    ${nav("learn")}</div>`;
}

function arm(exercise) {
  if (!exercise || state.armed === exercise.id) return;
  state.armed = exercise.id;
  state.selected = null;
  state.bank = (exercise.tokens || []).slice();
  state.built = [];
  state.typed = "";
  state.pairs = {};
  state.pick = null;
  state.revealSpeak = false;
  state.phase = "answer";
  state.feedback = null;
}
function lessonView() {
  const lesson = state.lesson;
  const exercise = lesson.exercise;
  arm(exercise);
  const bars = Array.from({ length: lesson.total }, (_, i) => `<i class="${i < lesson.index - (state.phase === "answer" ? 1 : 0) ? "on" : ""}"></i>`).join("");
  const prompt = exercise.prompt ? `<h2 class="prompt">${esc(exercise.prompt)}</h2>` : "";
  let body = "";
  const instruction = {
    to_en: t("toEn"),
    to_native: t("toNative"),
    listen: t("listen"),
    build: t("build"),
    type: t("type"),
    match: t("match"),
    fill: t("fill"),
  }[exercise.dir] || "";
  if (exercise.type === "choice" || exercise.type === "listen" || exercise.type === "fill") {
    body = `<div class="options">${exercise.options.map((option) => {
      let cls = state.selected === option.id ? "picked" : "";
      if (state.phase === "feedback") {
        if (sameText(option.text, state.feedback.reveal)) cls = "good";
        else if (state.selected === option.id) cls = "bad";
      }
      return `<button type="button" class="option ${cls}" data-action="pick" data-id="${esc(option.id)}">${esc(option.text)}</button>`;
    }).join("")}</div>`;
  } else if (exercise.type === "build") {
    body = `<div class="built">${state.built.map((word, i) => `<button type="button" class="chip" data-action="unbuild" data-i="${i}">${esc(word)}</button>`).join("")}</div>
      <div class="bank">${state.bank.map((word, i) => `<button type="button" class="chip" data-action="build" data-i="${i}">${esc(word)}</button>`).join("")}</div>`;
  } else if (exercise.type === "type") {
    body = `<input id="typeAnswer" type="text" autocomplete="off" placeholder="${esc(t("typePh"))}" value="${esc(state.typed)}">`;
  } else if (exercise.type === "match") {
    const pairedRight = new Set(Object.values(state.pairs));
    const col = (side, items) => items.map((item) => {
      const on = side === "left" ? state.pairs[item.id] : pairedRight.has(item.id);
      const picked = state.pick && state.pick.side === side && state.pick.id === item.id;
      return `<button type="button" class="option ${on ? "paired" : ""} ${picked ? "picked" : ""}" data-action="match" data-side="${side}" data-id="${esc(item.id)}">${esc(item.text)}</button>`;
    }).join("");
    body = `<div class="match"><div class="stack">${col("left", exercise.left)}</div><div class="stack">${col("right", exercise.right)}</div></div>`;
  }
  let listenExtra = "";
  if (exercise.type === "listen") {
    const canSpeak = "speechSynthesis" in window;
    listenExtra = `<button class="ghost" type="button" data-action="replay">${esc(t("replay"))}</button>
      ${canSpeak ? `<button class="ghost" type="button" data-action="reveal-speech">${esc(state.revealSpeak ? t("heard") : t("noHear"))}</button>` : `<p class="hint">${esc(t("noSpeech"))}</p>`}
      ${(state.revealSpeak || !canSpeak) ? `<p class="prompt">${esc(exercise.speak)}</p>` : ""}`;
  }
  const line = state.feedback
    ? (state.feedback.correct ? t("mascotOk") : t("mascotNo"))[lesson.index % 4]
    : instruction;
  const sheet = state.feedback ? `<div class="sheet ${state.feedback.correct ? "good" : "bad"}">
      ${esc(state.feedback.correct ? t("correct") : t("wrong"))}
      ${state.feedback.reveal ? `<small>${esc(state.feedback.reveal)}</small>` : ""}
      ${state.feedback.explain ? `<small>${esc(state.feedback.explain)}</small>` : ""}
    </div>` : "";
  const ready = answerReady();
  const buttonLabel = state.phase === "feedback" ? t("next") : t("check");
  return `<div class="lesson">
    <div class="lesson-top">
      <button class="icon-btn" type="button" data-action="ask-close" aria-label="${esc(t("leave"))}">×</button>
      <div class="bars">${bars}</div>
    </div>
    <div class="lesson-body">
      <p class="sub">${esc(lesson.unit_title)} · ${esc(lesson.title)}</p>
      ${lesson.tip ? `<div class="tip"><b>${esc(lesson.tip_title || t("tip"))}</b>${esc(lesson.tip)}</div>` : ""}
      <div class="mascot-row">${mascot(state.feedback && !state.feedback.correct ? "bad" : "ok")}<div class="bubble">${esc(line)}</div></div>
      ${prompt}${listenExtra}${body}
    </div>
    <div class="dock">${sheet}<button id="checkBtn" class="primary" type="button" data-action="advance" ${state.phase === "answer" && !ready ? "disabled" : ""}>${esc(buttonLabel)}</button></div>
    ${state.modal ? modalView() : ""}
  </div>`;
}
function answerReady() {
  const exercise = state.lesson?.exercise;
  if (!exercise || state.phase !== "answer") return true;
  if (exercise.type === "choice" || exercise.type === "listen" || exercise.type === "fill") return !!state.selected;
  if (exercise.type === "build") return state.built.length === (exercise.tokens || []).length && state.built.length > 0;
  if (exercise.type === "type") return state.typed.trim().length > 0;
  if (exercise.type === "match") return Object.keys(state.pairs).length === (exercise.left || []).length;
  return false;
}
function resultView() {
  const result = state.result;
  const stars = "★".repeat(result.stars) + "☆".repeat(3 - result.stars);
  const title = result.passed ? t("passed") : t("failed");
  const note = result.passed ? (result.stars === 3 ? t("perfect") : t("again")) : t("failedNote");
  return `<div class="screen result">
    ${mascot(result.passed ? "ok" : "bad")}
    <div class="big-stars">${stars}</div>
    <h2>${esc(title)}</h2>
    <p class="hint" style="text-align:center">${esc(note)}</p>
    <div class="scoreline">
      <div><b>${result.accuracy}%</b><span>${esc(t("accuracy"))}</span></div>
      <div><b>+${result.xp_gain}</b><span>${esc(t("xpGain"))}</span></div>
      <div><b>+${result.gems_gain}</b><span>${esc(t("gemsGain"))}</span></div>
    </div>
    ${result.next_lesson_id ? `<button class="primary" data-action="open-lesson" data-id="${esc(result.next_lesson_id)}" data-state="open">${esc(t("nextLesson"))}</button>` : ""}
    <button class="ghost" data-action="retry-lesson" style="margin-top:8px">${esc(t("retry"))}</button>
    <button class="linkish" data-action="tab" data-tab="learn">${esc(t("toPath"))}</button>
  </div>`;
}
function wordsView() {
  const levels = ["A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2"];
  const chips = levels.map((level) => `<button class="chip ${state.wordLevel === level ? "on" : ""}" data-action="word-level" data-level="${level}">${level}</button>`).join("");
  const data = state.wordTab === "grammar" ? state.grammar : state.words;
  let list = `<p class="hint">${esc(t("loading"))}</p>`;
  if (data) {
    if (!data.items.length) list = `<p class="hint">${esc(t("noResults"))}</p>`;
    else if (state.wordTab === "grammar") {
      list = data.items.map((item) => `<div class="word"><b>${esc(item.item)}</b><div class="alt">${esc(item.sentence_type || item.level)}</div></div>`).join("");
    } else {
      const other = lang() === "ru" ? "uk" : "ru";
      const otherName = lang() === "ru" ? "UK" : "RU";
      list = data.items.map((item) => {
        const main = item[lang()];
        const alt = item[other];
        const shown = main || alt || t("noTr");
        const altLine = main && alt ? `${otherName} · ${alt}` : "";
        return `<div class="word"><b>${esc(item.headword)}</b> <span class="pos">${esc(posLabel(item.pos))} · ${esc(item.level)}</span><div class="tr">${esc(shown)}</div>${altLine ? `<div class="alt">${esc(altLine)}</div>` : ""}</div>`;
      }).join("");
    }
  }
  const pages = data ? `<div class="pager">
      <button class="ghost" data-action="page" data-dir="-1" ${data.page <= 1 ? "disabled" : ""}>${esc(t("back"))}</button>
      <button class="ghost" data-action="page" data-dir="1" ${data.page >= data.pages ? "disabled" : ""}>${esc(t("forward"))}</button>
    </div><p class="hint">${esc(t("page"))} ${data.page} ${esc(t("of"))} ${data.pages} · ${data.total}</p>` : "";
  return `<div class="screen">${shellTop()}
    <div class="seg">
      <button class="${state.wordTab === "words" ? "on" : ""}" data-action="word-tab" data-tab="words">${esc(t("wordsTab"))}</button>
      <button class="${state.wordTab === "grammar" ? "on" : ""}" data-action="word-tab" data-tab="grammar">${esc(t("grammar"))}</button>
    </div>
    <div class="levels">${chips}</div>
    ${state.wordLevel === "C2" ? `<p class="hint">${esc(t("c2note"))}</p>` : ""}
    <div class="search-row">
      <input id="wordSearch" type="search" placeholder="${esc(t("search"))}" value="${esc(state.wordQuery)}">
    </div>
    ${state.wordTab === "words" ? `<button class="chip ${state.wordTranslated ? "on" : ""}" data-action="translated" style="margin-top:8px">${esc(state.wordTranslated ? t("withTr") : t("allWords"))}</button>` : ""}
    ${list}${pages}
    <p class="hint">${esc(t("sourceNote"))}</p>
    ${nav("words")}</div>`;
}
function practiceView() {
  return `<div class="screen">${shellTop()}
    <div class="card"><h2 style="margin-top:0">${esc(t("practice"))}</h2><p>${esc(t("practiceLead"))}</p><p class="hint">${esc(t("practiceEmpty"))}</p>
    <button class="primary" data-action="start-practice">${esc(t("startPractice"))}</button></div>
    ${nav("practice")}</div>`;
}
function profileView() {
  const user = state.user;
  const leaders = (state.leaders || []).map((item, index) => `<div class="leader ${item.you ? "you" : ""}"><div><b>${index + 1}. ${esc(item.display_name)}</b><div class="alt">${esc(item.username)} · ${item.lang === "uk" ? "UK" : "RU"}${item.is_admin ? " · " + esc(t("admin")) : ""}${item.you ? " · " + esc(t("you")) : ""}</div></div><b>${item.xp} XP</b></div>`).join("");
  return `<div class="screen">${shellTop()}
    <div class="stats">
      <div class="stat"><b>${user.lessons_done}</b><span>${esc(t("lessonsDone"))}</span></div>
      <div class="stat"><b>${user.accuracy}%</b><span>${esc(t("accuracy"))}</span></div>
      <div class="stat"><b>${user.best_streak}</b><span>${esc(t("bestStreak"))}</span></div>
      <div class="stat"><b>${user.xp}</b><span>${esc(t("xp"))}</span></div>
    </div>
    <div class="card"><strong>${esc(t("langName"))}</strong>${langSwitch()}
      <button class="ghost" style="margin-top:8px" data-action="sound">${esc(user.sound_on ? t("soundOn") : t("soundOff"))}</button>
    </div>
    <div class="card"><strong>${esc(t("leaders"))}</strong>${leaders || `<p class="hint">${esc(t("loading"))}</p>`}</div>
    ${homeHint()}
    <div class="card"><p class="hint">${esc(t("sourceNote"))}</p></div>
    <button class="danger" data-action="logout">${esc(t("logout"))}</button>
    ${nav("profile")}</div>`;
}
function modalView() {
  return `<div class="modal"><div class="card"><h2>${esc(t("closeTitle"))}</h2><p>${esc(t("closeText"))}</p>
    <button class="primary" data-action="stay">${esc(t("stay"))}</button>
    <button class="ghost" style="margin-top:8px" data-action="abandon">${esc(t("leave"))}</button></div></div>`;
}

function homeHint() {
  const narrow = window.matchMedia("(max-width: 900px)").matches;
  const standalone = window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone;
  if (!narrow || standalone) return "";
  return `<div class="card home-card"><strong>${esc(t("homeTitle"))}</strong><p class="hint">${esc(t("homeLead"))}</p></div>`;
}
function isLocalHost() {
  const host = location.hostname;
  return host === "localhost" || host === "127.0.0.1" || /^10\./.test(host) || /^192\.168\./.test(host) || /^172\.(1[6-9]|2\d|3[0-1])\./.test(host);
}
function paintPhone() {
  const dock = document.getElementById("phoneDock");
  if (!dock || location.protocol === "file:") return;
  const local = isLocalHost();
  dock.querySelector("[data-phone='kicker']").textContent = t("phoneKicker");
  dock.querySelector("[data-phone='title']").textContent = t(local ? "phoneTitle" : "hostTitle");
  dock.querySelector("[data-phone='lead']").textContent = t(local ? "phoneLead" : "hostLead");
  dock.querySelector("[data-phone='note']").textContent = t(local ? "phoneNote" : "hostNote");
  dock.querySelector("[data-phone='steps']").innerHTML = (local ? ["phoneStep1", "phoneStep2", "phoneStep3"] : ["hostStep1", "hostStep2", "hostStep3"])
    .map((key) => `<li>${esc(t(key))}</li>`)
    .join("");
  if (!local) {
    state.phoneUrl = location.origin + "/";
    showPhone(dock, false);
    return;
  }
  if (state.phoneUrl) {
    showPhone(dock, true);
    return;
  }
  if (state.phoneLoading) return;
  state.phoneLoading = true;
  api("/api/join").then((data) => {
    state.phoneUrl = data.url;
    state.phoneLoading = false;
    showPhone(dock, true);
  }).catch(() => {
    state.phoneLoading = false;
  });
}
function showPhone(dock, withQr) {
  const image = document.getElementById("phoneQr");
  const frame = image && image.closest(".qr-frame");
  const link = document.getElementById("phoneUrl");
  if (frame) frame.hidden = !withQr;
  if (withQr) {
    image.src = "/join.svg";
    image.alt = state.phoneUrl;
  }
  link.href = state.phoneUrl;
  link.textContent = state.phoneUrl.replace(/^https?:\/\//, "");
  dock.hidden = false;
}

function showError(error) {
  const code = error.code || "server";
  const authCodes = {
    bad_login: "badLogin",
    taken: "taken",
    weak_password: "weakPassword",
    bad_name: "badName",
    bad_username: "badUsername",
    offline: "server",
  };
  if (authCodes[code]) state.error = t(authCodes[code]);
  if (code === "offline") state.screen = "offline";
  const toasts = { locked: "locked", no_gems: "noGems" };
  if (toasts[code]) state.toast = t(toasts[code]);
}

async function boot() {
  if ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "localhost" || location.hostname === "127.0.0.1")) {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  }
  if (location.protocol === "file:") {
    state.screen = "offline";
    render();
    return;
  }
  const requested = new URLSearchParams(location.search).get("lang");
  if (!state.token && (requested === "ru" || requested === "uk")) {
    state.lang = requested;
    localStorage.setItem("lumen_lang", requested);
  }
  state.screen = "loading";
  state.error = "";
  render();
  if (!state.token) {
    state.screen = "auth";
    render();
    return;
  }
  try {
    const me = await api("/api/me");
    state.user = me.user;
    state.lang = me.user.lang;
    await loadCourse();
    state.screen = "path";
  } catch (error) {
    state.token = "";
    localStorage.removeItem("lumen_token");
    state.screen = error.code === "offline" ? "offline" : "auth";
    if (error.code !== "unauthorized" && error.code !== "offline") showError(error);
  }
  render();
}
async function loadCourse() {
  state.course = await api("/api/course");
  state.level = focusLevel(state.course);
}
function focusLevel(course) {
  for (const level of course.levels) {
    for (const unit of level.units) {
      if (unit.lessons.some((lesson) => lesson.state === "open")) return level.id;
    }
  }
  return "C1";
}
function saveDraft() {
  const username = document.getElementById("username");
  if (!username) return;
  state.draft.username = username.value;
  state.draft.password = document.getElementById("password")?.value || "";
  state.draft.display_name = document.getElementById("display_name")?.value || "";
}

async function submitAuth() {
  saveDraft();
  state.busy = true;
  state.error = "";
  const body = {
    username: state.draft.username,
    password: state.draft.password,
    display_name: state.draft.display_name || state.draft.username,
    lang: state.lang,
  };
  try {
    const data = await api(state.authMode === "register" ? "/api/register" : "/api/login", { method: "POST", body });
    state.token = data.token;
    localStorage.setItem("lumen_token", data.token);
    state.user = data.user;
    state.lang = data.user.lang;
    if (state.authMode === "register") {
      state.screen = "goal";
    } else {
      await loadCourse();
      state.screen = "path";
    }
  } catch (error) {
    showError(error);
  }
  state.busy = false;
  render();
}

async function openLesson(id) {
  state.busy = true;
  state.toast = "";
  try {
    const data = await api("/api/lesson/start", { method: "POST", body: { lesson_id: id } });
    state.lesson = data;
    state.resultLesson = id;
    if (!data.exercise) {
      await finishLesson();
      return;
    }
    state.phase = "answer";
    state.feedback = null;
    state.pendingNext = null;
    state.armed = "";
    state.screen = "lesson";
  } catch (error) {
    showError(error);
  }
  state.busy = false;
  render();
}
async function advance() {
  if (state.busy) return;
  if (state.phase === "answer") {
    if (!answerReady()) return;
    state.busy = true;
    const exercise = state.lesson.exercise;
    const answer = exercise.type === "type" ? { text: state.typed }
      : exercise.type === "build" ? { tokens: state.built }
      : exercise.type === "match" ? { pairs: state.pairs }
      : { option_id: state.selected };
    try {
      const data = await api("/api/lesson/check", {
        method: "POST",
        body: { run_id: state.lesson.run_id, exercise_id: exercise.id, answer },
      });
      state.feedback = data;
      state.pendingNext = data.next;
      state.phase = "feedback";
      state.user.gems = data.gems;
      tone(data.correct ? 660 : 196, data.correct ? 0.12 : 0.18);
      if (data.correct) setTimeout(() => tone(880, 0.12), 90);
    } catch (error) {
      showError(error);
    }
    state.busy = false;
    render();
    return;
  }
  if (state.pendingNext) {
    state.lesson.exercise = state.pendingNext;
    state.lesson.index += 1;
    state.lesson.correct = state.feedback.progress.correct;
    state.pendingNext = null;
    state.feedback = null;
    state.phase = "answer";
    state.armed = "";
    render();
    return;
  }
  await finishLesson();
}
async function finishLesson() {
  state.busy = true;
  try {
    const result = await api("/api/lesson/finish", { method: "POST", body: { run_id: state.lesson.run_id } });
    state.result = result;
    if (result.user) state.user = result.user;
    state.screen = "result";
    await loadCourse();
  } catch (error) {
    showError(error);
  }
  state.busy = false;
  render();
}
async function loadWords() {
  const params = new URLSearchParams({
    level: state.wordLevel,
    q: state.wordQuery,
    page: String(state.wordPage),
    translated: state.wordTranslated ? "1" : "0",
  });
  const path = state.wordTab === "grammar" ? "/api/grammar" : "/api/words";
  const data = await api(`${path}?${params}`);
  if (state.wordTab === "grammar") state.grammar = data;
  else state.words = data;
}
async function openTab(tab) {
  state.toast = "";
  if (tab === "learn") {
    await loadCourse();
    state.screen = "path";
  } else if (tab === "words") {
    state.screen = "words";
    render();
    await loadWords();
  } else if (tab === "practice") {
    state.screen = "practice";
  } else if (tab === "profile") {
    state.screen = "profile";
    render();
    const board = await api("/api/leaderboard");
    state.leaders = board.leaders;
    const me = await api("/api/me");
    state.user = me.user;
  }
  render();
}

app.addEventListener("click", async (event) => {
  const target = event.target.closest("[data-action]");
  if (!target || state.busy && ["advance", "open-lesson", "start-practice"].includes(target.dataset.action)) return;
  const action = target.dataset.action;
  if (action === "set-lang") {
    saveDraft();
    const next = target.dataset.lang;
    if (state.user) {
      const data = await api("/api/settings", { method: "POST", body: { lang: next } });
      state.user = data.user;
      state.lang = data.user.lang;
      if (state.course) await loadCourse();
      if (state.screen === "words") await loadWords();
      if (state.screen === "profile") state.leaders = (await api("/api/leaderboard")).leaders;
    } else {
      state.lang = next;
      localStorage.setItem("lumen_lang", next);
    }
    render();
  } else if (action === "auth-mode") {
    saveDraft();
    state.authMode = state.authMode === "login" ? "register" : "login";
    state.error = "";
    render();
  } else if (action === "demo") {
    state.draft.username = target.dataset.user;
    state.draft.password = "lumen2026";
    state.authMode = "login";
    render();
    submitAuth();
  } else if (action === "goal") {
    const data = await api("/api/settings", { method: "POST", body: { daily_goal: Number(target.dataset.goal) } });
    state.user = data.user;
    await loadCourse();
    state.screen = "path";
    render();
  } else if (action === "tab") {
    await openTab(target.dataset.tab);
  } else if (action === "level") {
    state.level = target.dataset.level;
    render();
  } else if (action === "open-lesson") {
    if (target.dataset.state === "locked") {
      state.toast = t("locked");
      render();
      return;
    }
    await openLesson(target.dataset.id);
  } else if (action === "pick") {
    if (state.phase !== "answer") return;
    state.selected = target.dataset.id;
    tone(520, 0.05);
    render();
  } else if (action === "build") {
    if (state.phase !== "answer") return;
    const [word] = state.bank.splice(Number(target.dataset.i), 1);
    state.built.push(word);
    tone(520, 0.04);
    render();
  } else if (action === "unbuild") {
    if (state.phase !== "answer") return;
    const [word] = state.built.splice(Number(target.dataset.i), 1);
    state.bank.push(word);
    render();
  } else if (action === "match") {
    if (state.phase !== "answer") return;
    pickMatch(target.dataset.side, target.dataset.id);
    render();
  } else if (action === "advance") {
    await advance();
  } else if (action === "replay") {
    speak(state.lesson.exercise.speak);
  } else if (action === "reveal-speech") {
    state.revealSpeak = !state.revealSpeak;
    render();
  } else if (action === "ask-close") {
    state.modal = true;
    render();
  } else if (action === "stay") {
    state.modal = false;
    render();
  } else if (action === "abandon") {
    state.modal = false;
    state.lesson = null;
    await openTab("learn");
  } else if (action === "retry-lesson") {
    if (state.result?.mode === "practice") {
      const data = await api("/api/practice/start", { method: "POST", body: {} });
      state.lesson = data;
      state.phase = "answer";
      state.armed = "";
      state.screen = "lesson";
      render();
    } else {
      await openLesson(state.resultLesson || state.lesson?.lesson_id);
    }
  } else if (action === "start-practice") {
    state.busy = true;
    try {
      const data = await api("/api/practice/start", { method: "POST", body: {} });
      state.lesson = data;
      state.phase = "answer";
      state.armed = "";
      state.screen = "lesson";
      state.resultLesson = "practice";
    } catch (error) {
      showError(error);
    }
    state.busy = false;
    render();
  } else if (action === "word-tab") {
    state.wordTab = target.dataset.tab;
    state.wordPage = 1;
    render();
    await loadWords();
    state.focus = "wordSearch";
    render();
  } else if (action === "word-level") {
    state.wordLevel = target.dataset.level;
    state.wordPage = 1;
    await loadWords();
    state.focus = "wordSearch";
    render();
  } else if (action === "translated") {
    state.wordTranslated = !state.wordTranslated;
    state.wordPage = 1;
    await loadWords();
    render();
  } else if (action === "page") {
    state.wordPage = Math.max(1, state.wordPage + Number(target.dataset.dir));
    await loadWords();
    render();
  } else if (action === "sound") {
    const data = await api("/api/settings", { method: "POST", body: { sound_on: !state.user.sound_on } });
    state.user = data.user;
    render();
  } else if (action === "logout") {
    await api("/api/logout", { method: "POST", body: {} }).catch(() => {});
    state.token = "";
    localStorage.removeItem("lumen_token");
    state.user = null;
    state.screen = "auth";
    render();
  } else if (action === "boot") {
    boot();
  }
});

app.addEventListener("submit", (event) => {
  if (event.target.id === "authForm") {
    event.preventDefault();
    submitAuth();
  }
});
app.addEventListener("input", (event) => {
  if (event.target.id === "typeAnswer") {
    state.typed = event.target.value;
    const button = document.getElementById("checkBtn");
    if (button && state.phase === "answer") button.disabled = !state.typed.trim();
  }
  if (event.target.id === "wordSearch") {
    state.wordQuery = event.target.value;
    clearTimeout(state.searchTimer);
    state.searchTimer = setTimeout(async () => {
      state.wordPage = 1;
      await loadWords();
      state.focus = "wordSearch";
      render();
    }, 250);
  }
});
app.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && event.target.id === "typeAnswer") {
    event.preventDefault();
    advance();
  }
});

function pickMatch(side, id) {
  const pairs = state.pairs;
  if (side === "left" && pairs[id]) {
    delete pairs[id];
    state.pick = null;
    return;
  }
  if (side === "right") {
    const owner = Object.keys(pairs).find((key) => pairs[key] === id);
    if (owner) {
      delete pairs[owner];
      state.pick = null;
      return;
    }
  }
  if (!state.pick || state.pick.side === side) {
    state.pick = { side, id };
    return;
  }
  const left = side === "left" ? id : state.pick.id;
  const right = side === "right" ? id : state.pick.id;
  delete pairs[left];
  Object.keys(pairs).forEach((key) => {
    if (pairs[key] === right) delete pairs[key];
  });
  pairs[left] = right;
  state.pick = null;
  tone(520, 0.04);
}

boot();
