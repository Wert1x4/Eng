/* Lumen on the device. Lessons, accounts and progress stay in this browser. */
window.lumenDevice = (() => {
  const KEY = "lumen_device_v1";
  let pack = null;
  let db = null;

  function today() {
    const now = new Date();
    const month = String(now.getMonth() + 1).padStart(2, "0");
    const day = String(now.getDate()).padStart(2, "0");
    return `${now.getFullYear()}-${month}-${day}`;
  }
  function yesterday() {
    const now = new Date();
    now.setDate(now.getDate() - 1);
    const month = String(now.getMonth() + 1).padStart(2, "0");
    const day = String(now.getDate()).padStart(2, "0");
    return `${now.getFullYear()}-${month}-${day}`;
  }
  function fail(code) {
    const error = new Error(code);
    error.code = code;
    throw error;
  }
  function save() {
    localStorage.setItem(KEY, JSON.stringify(db));
  }
  function load() {
    try {
      db = JSON.parse(localStorage.getItem(KEY) || "null");
    } catch (error) {
      db = null;
    }
    if (!db || !db.users) {
      const now = today();
      db = {
        users: (pack.accounts || []).map((user) => ({ ...user, last_active: now, daily_xp: 0, daily_date: now })),
        sessions: {},
        progress: JSON.parse(JSON.stringify(pack.progress || {})),
        mistakes: {},
        runs: {},
        nextId: Math.max(0, ...(pack.accounts || []).map((user) => user.id)) + 1,
      };
      save();
    }
  }
  function sha256Bytes(bytes) {
    const k = Uint32Array.from([
      0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
      0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
      0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
      0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
      0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
      0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
      0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
      0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
    ]);
    const hash = Uint32Array.from([
      0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
    ]);
    const bitLength = bytes.length * 8;
    const withPad = new Uint8Array((((bytes.length + 9 + 63) >> 6) << 6));
    withPad.set(bytes);
    withPad[bytes.length] = 0x80;
    const view = new DataView(withPad.buffer);
    view.setUint32(withPad.length - 4, bitLength, false);
    const w = new Uint32Array(64);
    const rot = (value, bits) => (value >>> bits) | (value << (32 - bits));
    for (let offset = 0; offset < withPad.length; offset += 64) {
      for (let i = 0; i < 16; i += 1) w[i] = view.getUint32(offset + i * 4, false);
      for (let i = 16; i < 64; i += 1) {
        const s0 = rot(w[i - 15], 7) ^ rot(w[i - 15], 18) ^ (w[i - 15] >>> 3);
        const s1 = rot(w[i - 2], 17) ^ rot(w[i - 2], 19) ^ (w[i - 2] >>> 10);
        w[i] = (w[i - 16] + s0 + w[i - 7] + s1) | 0;
      }
      let [a, b, c, d, e, f, g, h] = hash;
      for (let i = 0; i < 64; i += 1) {
        const s1 = rot(e, 6) ^ rot(e, 11) ^ rot(e, 25);
        const ch = (e & f) ^ (~e & g);
        const temp1 = (h + s1 + ch + k[i] + w[i]) | 0;
        const s0 = rot(a, 2) ^ rot(a, 13) ^ rot(a, 22);
        const maj = (a & b) ^ (a & c) ^ (b & c);
        const temp2 = (s0 + maj) | 0;
        h = g; g = f; f = e; e = (d + temp1) | 0; d = c; c = b; b = a; a = (temp1 + temp2) | 0;
      }
      hash[0] = (hash[0] + a) | 0;
      hash[1] = (hash[1] + b) | 0;
      hash[2] = (hash[2] + c) | 0;
      hash[3] = (hash[3] + d) | 0;
      hash[4] = (hash[4] + e) | 0;
      hash[5] = (hash[5] + f) | 0;
      hash[6] = (hash[6] + g) | 0;
      hash[7] = (hash[7] + h) | 0;
    }
    return [...hash].map((word) => (word >>> 0).toString(16).padStart(8, "0")).join("");
  }
  async function sha256(text) {
    const bytes = new TextEncoder().encode(text);
    try {
      if (crypto.subtle) {
        const digest = await crypto.subtle.digest("SHA-256", bytes);
        return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
      }
    } catch (error) {
      /* iPhone on a home address has no subtle crypto */
    }
    return sha256Bytes(bytes);
  }
  function userByToken(token) {
    const id = db.sessions[token];
    return db.users.find((user) => user.id === id) || null;
  }
  function tokenFrom(options) {
    const header = (options.headers && options.headers.Authorization) || "";
    return header.startsWith("Bearer ") ? header.slice(7) : localStorage.getItem("lumen_token") || "";
  }
  function requireUser(options) {
    const user = userByToken(tokenFrom(options));
    if (!user) fail("unauthorized");
    if (user.daily_date !== today()) {
      user.daily_xp = 0;
      user.daily_date = today();
      save();
    }
    return user;
  }
  function visibleStreak(user) {
    if (user.last_active === today() || user.last_active === yesterday()) return user.streak || 0;
    return 0;
  }
  function publicUser(user) {
    const done = Object.values(db.progress[String(user.id)] || {}).filter((item) => item.stars > 0);
    const accuracy = done.length ? Math.round(done.reduce((sum, item) => sum + item.best_accuracy, 0) / done.length * 100) : 0;
    return {
      id: user.id,
      username: user.username,
      display_name: user.display_name,
      lang: user.lang,
      is_admin: !!user.is_admin,
      xp: user.xp || 0,
      streak: visibleStreak(user),
      best_streak: user.best_streak || 0,
      gems: user.gems || 0,
      daily_goal: user.daily_goal || 50,
      daily_xp: user.daily_xp || 0,
      sound_on: user.sound_on !== false,
      lessons_done: done.length,
      accuracy,
    };
  }
  function norm(text) {
    return String(text || "").trim().toLowerCase().replaceAll("ё", "е").replaceAll("’", "'").replaceAll("ʼ", "'").replaceAll("`", "'").replace(/[^\w\s'-]/gu, "").replace(/\s+/g, " ").trim();
  }
  function grade(exercise, answer) {
    answer = answer || {};
    if (exercise.type === "choice" || exercise.type === "listen" || exercise.type === "fill") return answer.option_id === exercise.correct_id;
    if (exercise.type === "build") return (answer.tokens || []).map(norm).join("\n") === (exercise.answer_tokens || []).map(norm).join("\n");
    if (exercise.type === "type") return (exercise.accept || []).includes(norm(answer.text || ""));
    if (exercise.type === "match") {
      const got = answer.pairs || {};
      const keys = Object.keys(exercise.pairs || {});
      return keys.length === Object.keys(got).length && keys.every((key) => String(got[key]) === String(exercise.pairs[key]));
    }
    return false;
  }
  function pub(exercise) {
    if (!exercise) return null;
    const copy = { ...exercise };
    ["correct_id", "accept", "pairs", "answer_tokens", "reveal", "explain", "key"].forEach((field) => delete copy[field]);
    return copy;
  }
  function courseFor(user) {
    const lang = user.lang;
    const done = db.progress[String(user.id)] || {};
    let unlocked = true;
    const states = {};
    pack.order.forEach((id) => {
      const row = done[id];
      if (row && row.stars > 0) states[id] = ["done", row.stars];
      else if (user.is_admin || unlocked) {
        states[id] = ["open", 0];
        if (!user.is_admin) unlocked = false;
      } else states[id] = ["locked", 0];
    });
    return {
      levels: pack.levels.map((level) => {
        const seen = [];
        pack.order.forEach((id) => {
          const item = pack.meta[id];
          if (item.level === level.id && !seen.includes(item.unit_id)) seen.push(item.unit_id);
        });
        return {
          id: level.id,
          title: level.title[lang],
          units: seen.map((unitId) => {
            const unit = pack.units[unitId];
            return {
              id: unitId,
              title: unit.title[lang],
              goal: unit.goal[lang],
              color: unit.color,
              lessons: pack.order.filter((id) => pack.meta[id].unit_id === unitId).map((id) => ({
                id,
                title: pack.meta[id].title[lang],
                kind: pack.meta[id].kind,
                state: states[id][0],
                stars: states[id][1],
              })),
            };
          }),
        };
      }),
    };
  }
  function lessonState(user, lessonId) {
    if (!pack.meta[lessonId]) return "missing";
    if (user.is_admin) return (db.progress[String(user.id)] || {})[lessonId]?.stars > 0 ? "done" : "open";
    for (const id of pack.order) {
      if (id === lessonId) return (db.progress[String(user.id)] || {})[id]?.stars > 0 ? "done" : "open";
      if (!((db.progress[String(user.id)] || {})[id]?.stars > 0)) return "locked";
    }
    return "locked";
  }
  function payload(user, run) {
    const exercises = run.exercises;
    const exercise = exercises[run.answered] || null;
    const meta = pack.meta[run.lesson_id];
    const unit = meta ? pack.units[meta.unit_id] : null;
    const lang = user.lang;
    const title = meta ? pack.kinds[meta.kind][lang] : (lang === "uk" ? "Практика" : "Практика");
    return {
      run_id: run.id,
      mode: run.mode,
      lesson_id: run.lesson_id,
      title,
      unit_title: unit ? unit.title[lang] : title,
      tip: meta && meta.kind === "grammar" && unit ? unit.grammar_tip[lang] : "",
      tip_title: meta && meta.kind === "grammar" && unit ? unit.grammar_title[lang] : "",
      index: exercise ? run.answered + 1 : exercises.length,
      total: exercises.length,
      correct: run.correct,
      exercise: pub(exercise),
    };
  }
  function touch(user) {
    const current = today();
    let streak = 1;
    if (user.last_active === current) streak = user.streak || 1;
    else if (user.last_active === yesterday()) streak = (user.streak || 0) + 1;
    user.streak = streak;
    user.best_streak = Math.max(user.best_streak || 0, streak);
    user.last_active = current;
    return streak;
  }
  function nextLesson(lessonId) {
    const index = pack.order.indexOf(lessonId);
    if (index < 0 || index + 1 >= pack.order.length) return null;
    return pack.order[index + 1];
  }
  function pageOf(items, page, size) {
    const start = (page - 1) * size;
    return {
      page,
      pages: Math.max(1, Math.ceil(items.length / size)),
      total: items.length,
      items: items.slice(start, start + size),
    };
  }

  async function ready() {
    if (pack) return;
    const response = await fetch("/pack.json");
    if (!response.ok) fail("offline");
    pack = await response.json();
    load();
  }

  async function handle(path, options = {}) {
    await ready();
    const body = options.body || {};
    const url = new URL(path, "http://local");
    const route = url.pathname;
    const query = url.searchParams;
    if (route === "/api/login") {
      const username = String(body.username || "").trim().toLowerCase();
      const password = await sha256(String(body.password || ""));
      const user = db.users.find((item) => item.username === username && item.password === password);
      if (!user) fail("bad_login");
      const token = Math.random().toString(36).slice(2) + Math.random().toString(36).slice(2);
      db.sessions[token] = user.id;
      save();
      return { token, user: publicUser(user) };
    }
    if (route === "/api/register") {
      const username = String(body.username || "").trim().toLowerCase();
      const display = String(body.display_name || "").trim();
      const password = String(body.password || "");
      const lang = body.lang === "uk" || body.lang === "ru" ? body.lang : "";
      if (!/^[a-z][a-z0-9_]{2,19}$/.test(username)) fail("bad_username");
      if (display.length < 1 || display.length > 32) fail("bad_name");
      if (password.length < 4 || password.length > 64) fail("weak_password");
      if (!lang) fail("bad_lang");
      if (db.users.some((item) => item.username === username)) fail("taken");
      const user = {
        id: db.nextId++,
        username,
        display_name: display,
        password: await sha256(password),
        lang,
        is_admin: false,
        xp: 0,
        streak: 0,
        best_streak: 0,
        gems: 5,
        daily_goal: 50,
        daily_xp: 0,
        daily_date: today(),
        last_active: null,
        sound_on: true,
      };
      db.users.push(user);
      db.progress[String(user.id)] = {};
      const token = Math.random().toString(36).slice(2) + Math.random().toString(36).slice(2);
      db.sessions[token] = user.id;
      save();
      return { token, user: publicUser(user) };
    }
    if (route === "/api/logout") {
      delete db.sessions[tokenFrom(options)];
      save();
      return { ok: true };
    }
    const user = requireUser(options);
    if (route === "/api/me") return { user: publicUser(user) };
    if (route === "/api/course") return courseFor(user);
    if (route === "/api/settings") {
      if (body.lang === "ru" || body.lang === "uk") user.lang = body.lang;
      if (body.daily_goal === 20 || body.daily_goal === 50 || body.daily_goal === 100) user.daily_goal = body.daily_goal;
      if ("sound_on" in body) user.sound_on = !!body.sound_on;
      save();
      return { user: publicUser(user) };
    }
    if (route === "/api/leaderboard") {
      const leaders = db.users.slice().sort((a, b) => b.xp - a.xp || a.username.localeCompare(b.username)).map((item) => ({
        username: item.username,
        display_name: item.display_name,
        xp: item.xp || 0,
        streak: visibleStreak(item),
        lang: item.lang,
        is_admin: !!item.is_admin,
        you: item.id === user.id,
      }));
      return { leaders };
    }
    if (route === "/api/words" || route === "/api/grammar") {
      const level = (query.get("level") || "").toUpperCase();
      const text = (query.get("q") || "").trim().toLowerCase();
      const page = Math.max(1, parseInt(query.get("page") || "1", 10) || 1);
      if (route === "/api/grammar") {
        let items = pack.grammar.filter((item) => !level || item.level === level);
        if (text) items = items.filter((item) => item.item.toLowerCase().includes(text));
        const result = pageOf(items, page, 50);
        result.level = level || "A1";
        return result;
      }
      let items = pack.words.filter((item) => !level || item.level === level);
      if (query.get("translated") === "1") items = items.filter((item) => item.ru || item.uk);
      if (text) items = items.filter((item) => item.headword.toLowerCase().includes(text) || (item.ru || "").toLowerCase().includes(text) || (item.uk || "").toLowerCase().includes(text));
      return pageOf(items, page, 40);
    }
    if (route === "/api/lesson/start" || route === "/api/practice/start") {
      let exercises;
      let lessonId = "practice";
      let mode = "practice";
      if (route === "/api/lesson/start") {
        lessonId = String(body.lesson_id || "");
        mode = "lesson";
        const state = lessonState(user, lessonId);
        if (state === "missing") fail("not_found");
        if (state === "locked") fail("locked");
        const existing = Object.values(db.runs).find((run) => run.user_id === user.id && run.lesson_id === lessonId && run.mode === "lesson" && run.lang === user.lang && !run.finished);
        if (existing && Date.now() - existing.created < 6 * 60 * 60 * 1000) return payload(user, existing);
        exercises = JSON.parse(JSON.stringify(pack.lessons[lessonId][user.lang]));
      } else {
        const bag = (db.mistakes[String(user.id)] || {})[user.lang] || {};
        exercises = Object.values(bag).sort((a, b) => b.wrong_count - a.wrong_count).slice(0, 8).map((item) => ({ ...item.payload, id: Math.random().toString(36).slice(2, 8) }));
        if (exercises.length < 6) {
          const doneIds = Object.entries(db.progress[String(user.id)] || {}).filter(([, row]) => row.stars > 0).map(([id]) => id);
          const last = doneIds.sort().slice(-1)[0];
          const unitId = last ? pack.meta[last].unit_id : pack.order[0] && pack.meta[pack.order[0]].unit_id;
          const extraId = pack.order.find((id) => pack.meta[id].unit_id === unitId && pack.meta[id].kind === "words");
          const seen = new Set(exercises.map((item) => item.key));
          (pack.lessons[extraId][user.lang] || []).forEach((exercise) => {
            if (exercises.length >= 8 || seen.has(exercise.key)) return;
            seen.add(exercise.key);
            exercises.push(JSON.parse(JSON.stringify(exercise)));
          });
        }
        exercises = exercises.slice(0, 8);
      }
      const run = {
        id: Math.random().toString(36).slice(2) + Math.random().toString(36).slice(2),
        user_id: user.id,
        lesson_id: lessonId,
        mode,
        lang: user.lang,
        exercises,
        answered: 0,
        correct: 0,
        finished: false,
        created: Date.now(),
      };
      db.runs[run.id] = run;
      save();
      return payload(user, run);
    }
    if (route === "/api/lesson/check") {
      const run = db.runs[body.run_id];
      if (!run || run.user_id !== user.id || run.finished) fail("not_found");
      const exercise = run.exercises[run.answered];
      if (!exercise) fail("finished");
      if (body.exercise_id && body.exercise_id !== exercise.id) fail("stale");
      const ok = grade(exercise, body.answer || {});
      run.correct += ok ? 1 : 0;
      run.answered += 1;
      const mistakes = db.mistakes[String(user.id)] || (db.mistakes[String(user.id)] = {});
      const langBag = mistakes[run.lang] || (mistakes[run.lang] = {});
      if (ok && langBag[exercise.key]) {
        langBag[exercise.key].wrong_count -= 1;
        if (langBag[exercise.key].wrong_count <= 0) delete langBag[exercise.key];
      } else if (!ok && run.mode === "lesson") {
        const prev = langBag[exercise.key];
        langBag[exercise.key] = { payload: exercise, wrong_count: (prev ? prev.wrong_count : 0) + 1 };
      }
      save();
      const hasNext = run.answered < run.exercises.length;
      return {
        correct: ok,
        reveal: exercise.reveal || "",
        explain: exercise.explain || "",
        gems: user.gems || 0,
        progress: { index: run.answered, total: run.exercises.length, correct: run.correct },
        next: hasNext ? pub(run.exercises[run.answered]) : null,
      };
    }
    if (route === "/api/lesson/finish") {
      const run = db.runs[body.run_id];
      if (!run || run.user_id !== user.id) fail("not_found");
      if (run.finished && run.result) return run.result;
      const total = run.exercises.length;
      const correct = run.correct;
      const ratio = total ? correct / total : 0;
      let passed;
      let stars;
      let xpGain;
      let gemsGain;
      if (run.mode === "practice") {
        passed = run.answered === total && total > 0;
        stars = correct === total && passed ? 3 : ratio >= 0.85 ? 2 : passed ? 1 : 0;
        xpGain = correct * 4;
        gemsGain = 0;
      } else {
        passed = run.answered === total && ratio >= 0.7;
        if (!passed) {
          stars = 0;
          xpGain = 0;
          gemsGain = 0;
        } else {
          stars = correct === total ? 3 : ratio >= 0.85 ? 2 : 1;
          const bag = db.progress[String(user.id)] || (db.progress[String(user.id)] = {});
          const prev = bag[run.lesson_id];
          const times = prev ? prev.times_done : 0;
          xpGain = correct * (times === 0 ? 10 : 3) + (correct === total && times === 0 ? 20 : 0);
          gemsGain = (times === 0 ? 6 : 0) + (correct === total && times === 0 ? 4 : 0);
          bag[run.lesson_id] = {
            stars: Math.max(stars, prev ? prev.stars : 0),
            best_accuracy: Math.max(ratio, prev ? prev.best_accuracy : 0),
            times_done: times + 1,
            xp_awarded: (prev ? prev.xp_awarded : 0) + xpGain,
          };
        }
      }
      const streak = touch(user);
      user.xp = (user.xp || 0) + xpGain;
      user.gems = (user.gems || 0) + gemsGain;
      user.daily_xp = (user.daily_date === today() ? user.daily_xp || 0 : 0) + xpGain;
      user.daily_date = today();
      const result = {
        passed,
        stars,
        accuracy: Math.round(ratio * 100),
        correct,
        total,
        xp_gain: xpGain,
        gems_gain: gemsGain,
        streak,
        mode: run.mode,
        next_lesson_id: run.mode === "lesson" && passed ? nextLesson(run.lesson_id) : null,
        user: publicUser(user),
      };
      run.finished = true;
      run.result = result;
      save();
      return result;
    }
    fail("not_found");
  }

  return { ready, handle };
})();
