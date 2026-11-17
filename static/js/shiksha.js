(function () {
  "use strict";
  var root = document.documentElement;
  var $ = function (s, c) { return (c || document).querySelector(s); };
  var $$ = function (s, c) { return Array.prototype.slice.call((c || document).querySelectorAll(s)); };
  var I18N = {};
  try { I18N = JSON.parse(document.getElementById("i18n").textContent); } catch (e) {}
  function t(key, fallback) { return I18N[key] || fallback; }
  var store = {
    get: function (k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set: function (k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  };

  // ---- theme: stored choice, else follow the OS ----
  function setTheme(t) { root.setAttribute("data-theme", t); store.set("shiksha-theme", t); }
  $$("[data-theme-toggle]").forEach(function (b) {
    b.addEventListener("click", function () { setTheme(root.getAttribute("data-theme") === "dark" ? "light" : "dark"); });
  });

  // ---- sidebar: collapse (desktop) / drawer (mobile) ----
  var app = $(".app");
  $$("[data-collapse]").forEach(function (b) {
    b.addEventListener("click", function () {
      app.classList.toggle("collapsed");
      store.set("shiksha-collapsed", app.classList.contains("collapsed") ? "1" : "");
    });
  });
  function closeNav() { if (app) app.classList.remove("nav-open"); }
  $$("[data-nav-toggle]").forEach(function (b) { b.addEventListener("click", function () { app.classList.toggle("nav-open"); }); });
  $$("[data-nav-close]").forEach(function (b) { b.addEventListener("click", closeNav); });

  // ---- dropdowns: the whole button (text + icon) toggles; click-outside / Esc close ----
  function closeDropdowns(except) {
    $$(".dd.open").forEach(function (d) {
      if (d === except) return;
      d.classList.remove("open");
      var b = $(".dd-btn", d); if (b) b.setAttribute("aria-expanded", "false");
    });
  }
  // Delegated, so dropdowns keep working on content that is swapped in without a page reload.
  document.addEventListener("click", function (e) {
    var btn = e.target.closest && e.target.closest(".dd-btn"), dd = btn && btn.closest(".dd");
    if (dd) {
      var open = !dd.classList.contains("open");
      closeDropdowns(dd);
      dd.classList.toggle("open", open); btn.setAttribute("aria-expanded", open ? "true" : "false");
      if (open) {
        var first = $(".dd-item", dd); if (first && e.detail === 0) first.focus();          // keyboard open → focus first item
        var inp = $("[data-jump-input]", dd); if (inp && e.detail !== 0) setTimeout(function () { inp.focus(); }, 60);
        var cur = $(".jump-item.cur", dd); if (cur) setTimeout(function () { cur.scrollIntoView({ block: "center" }); }, 30);
      }
      return;
    }
    if (!e.target.closest(".dd")) closeDropdowns();
  });
  document.addEventListener("keydown", function (e) {
    var dd = e.target.closest && e.target.closest(".dd.open"); if (!dd || (e.key !== "ArrowDown" && e.key !== "ArrowUp")) return;
    var items = $$(".dd-item", dd), i = items.indexOf(document.activeElement);
    e.preventDefault();
    if (e.key === "ArrowDown") (items[i + 1] || items[0]).focus(); else (items[i - 1] || items[items.length - 1]).focus();
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") { closeDropdowns(); closeNav(); hideSuggest(); }
  });

  // ---- toasts (Django messages) ----
  var ICON = {
    success: '<svg class="i" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/></svg>',
    error: '<svg class="i" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 8v5M12 16h.01"/></svg>',
    info: '<svg class="i" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/></svg>'
  };
  function toast(level, text, ms) {
    var box = $("#toasts"); if (!box) return;
    var kind = level === "error" ? "error" : level === "success" ? "success" : level === "warning" ? "warning" : "info";
    var t = document.createElement("div");
    t.className = "toast " + kind; t.setAttribute("role", kind === "error" ? "alert" : "status");
    t.innerHTML = (ICON[kind] || ICON.info) + '<div class="t-body"></div><button class="t-x" aria-label="Dismiss">&times;</button>';
    t.querySelector(".t-body").textContent = text;
    function kill() { t.classList.add("leaving"); setTimeout(function () { t.remove(); }, 260); }
    t.querySelector(".t-x").addEventListener("click", kill);
    box.appendChild(t); setTimeout(kill, ms || (kind === "error" ? 8000 : 5000));
  }
  window.shikshaToast = toast;
  $$("[data-flash]").forEach(function (m) { toast(m.getAttribute("data-level"), m.textContent.trim()); m.remove(); });

  // ---- global search: live suggestions, "/" or Ctrl/⌘+K to focus, arrows + Enter ----
  var sForm = $("[data-search]"), sInput = sForm && $("input", sForm), sBox = sForm && $(".suggest", sForm), sTimer, sSel = -1, sSeq = 0;
  function hideSuggest() { if (sBox) { sBox.hidden = true; sSel = -1; } }
  function esc(s) { var d = document.createElement("div"); d.textContent = s; return d.innerHTML; }
  function renderSuggest(items, q) {
    if (!items.length) { sBox.innerHTML = '<div class="s-empty">' + esc(t("noResults", "No results for")) + ' “' + esc(q) + '”</div>'; sBox.hidden = false; return; }
    sBox.innerHTML = items.map(function (it) {
      return '<a href="' + esc(it.url) + '"><span class="s-ico"><svg class="i" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' + it.icon + '</svg></span><span><div class="s-title">' + esc(it.title) + '</div><div class="s-sub">' + esc(it.sub) + '</div></span></a>';
    }).join("") + '<a class="s-all" href="' + sForm.getAttribute("action") + "?q=" + encodeURIComponent(q) + '"><span class="s-sub">' + esc(t("seeAll", "See all results for")) + ' “' + esc(q) + '”</span></a>';
    sBox.hidden = false; sSel = -1;
  }
  if (sInput) {
    sInput.addEventListener("input", function () {
      clearTimeout(sTimer); var q = sInput.value.trim();
      if (q.length < 2) { hideSuggest(); return; }
      sTimer = setTimeout(function () {
        var seq = ++sSeq;
        fetch(sForm.getAttribute("data-suggest") + "?q=" + encodeURIComponent(q), { credentials: "same-origin", headers: { "Accept": "application/json" } })
          .then(function (r) { return r.ok ? r.json() : { results: [] }; })
          .then(function (d) { if (seq === sSeq && sInput.value.trim() === q) renderSuggest(d.results, q); })
          .catch(hideSuggest);
      }, 180);
    });
    sInput.addEventListener("keydown", function (e) {
      var links = $$("a", sBox); if (sBox.hidden || !links.length) return;
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault(); sSel = (sSel + (e.key === "ArrowDown" ? 1 : -1) + links.length) % links.length;
        links.forEach(function (l, i) { l.classList.toggle("sel", i === sSel); });
      } else if (e.key === "Enter" && sSel > -1) { e.preventDefault(); links[sSel].click(); }
    });
    document.addEventListener("click", function (e) { if (!e.target.closest("[data-search]")) hideSuggest(); });
  }
  document.addEventListener("keydown", function (e) {
    var typing = /^(INPUT|TEXTAREA|SELECT)$/.test((e.target.tagName || "")) || e.target.isContentEditable;
    if (sInput && ((e.key === "k" && (e.ctrlKey || e.metaKey)) || (e.key === "/" && !typing))) { e.preventDefault(); sInput.focus(); sInput.select(); }
    if (typing || e.ctrlKey || e.metaKey || e.altKey) return;
    // step / page keyboard navigation
    if (e.key === "ArrowLeft") { var p = $("[data-key-prev]"); if (p) { p.click(); } }
    if (e.key === "ArrowRight") { var n = $("[data-key-next]"); if (n) { n.click(); } }
    // quiz: press 1-4 to pick an answer
    var num = parseInt(e.key, 10);
    if (num >= 1 && num <= 6) { var opts = $$(".option input"); if (opts[num - 1]) { opts[num - 1].checked = true; opts[num - 1].dispatchEvent(new Event("change", { bubbles: true })); } }
    if (e.key === "Enter") { var go = $("[data-enter-submit]:not([disabled])"); if (go && document.activeElement === document.body) go.click(); }
  });

  // ---- forms: show/hide password, strength meter, no double-submit, consent gate ----
  $$("[data-toggle-password]").forEach(function (b) {
    b.addEventListener("click", function () {
      var input = document.getElementById(b.getAttribute("data-toggle-password")); if (!input) return;
      var show = input.type === "password"; input.type = show ? "text" : "password";
      b.setAttribute("aria-pressed", show ? "true" : "false");
      $(".on-eye", b).hidden = show; $(".off-eye", b).hidden = !show;
    });
  });
  $$("[data-strength-for]").forEach(function (meter) {
    var input = document.getElementById(meter.getAttribute("data-strength-for")), label = $(".strength-label", meter.parentNode);
    var names = ["", "Weak", "Fair", "Good", "Strong"];
    input.addEventListener("input", function () {
      var v = input.value, s = 0;
      if (v.length >= 8) s++; if (v.length >= 12) s++; if (/[a-z]/.test(v) && /[A-Z]/.test(v)) s++; if (/\d/.test(v) && /[^A-Za-z0-9]/.test(v)) s++;
      if (!v) s = 0; meter.setAttribute("data-s", s); if (label) label.textContent = v ? names[Math.max(s, 1)] : "";
    });
  });
  $$("form").forEach(function (f) {
    f.addEventListener("submit", function (e) {
      var btn = e.submitter || $("button[type=submit], button:not([type])", f);
      if (!btn || btn.name || btn.hasAttribute("data-no-loading") || !btn.classList.contains("btn")) return;
      setTimeout(function () { btn.classList.add("is-loading"); btn.setAttribute("aria-busy", "true"); btn.disabled = true; }, 0);
    });
  });
  window.addEventListener("pageshow", function () { $$(".btn.is-loading").forEach(function (b) { b.classList.remove("is-loading"); b.disabled = false; }); });
  function syncConsent() {
    $$("[data-consent]").forEach(function (box) { var btn = document.getElementById(box.getAttribute("data-consent")); if (btn) btn.disabled = !box.checked; });
  }
  document.addEventListener("change", function (e) { if (e.target.matches && e.target.matches("[data-consent]")) syncConsent(); });
  syncConsent();
  $$("[data-quiz-form]").forEach(function (f) {
    var btn = $("[data-quiz-next]", f); $$("input[name=choice]", f).forEach(function (r) { r.addEventListener("change", function () { btn.disabled = false; }); });
  });

  // ---- in-page quick filter (module catalogue) ----
  var qf = $("[data-filter-input]");
  if (qf) {
    var items = $$("[data-filter-item]"), none = $("[data-filter-none]");
    qf.addEventListener("input", function () {
      var q = qf.value.trim().toLowerCase(), shown = 0;
      items.forEach(function (it) { var m = !q || it.getAttribute("data-filter-item").toLowerCase().indexOf(q) > -1; it.hidden = !m; if (m) shown++; });
      $$("[data-filter-section]").forEach(function (sec) { sec.hidden = !$$("[data-filter-item]:not([hidden])", sec).length; });
      if (none) none.hidden = shown > 0;
    });
  }

  // ---- copy-to-clipboard buttons ----
  $$("[data-copy]").forEach(function (b) {
    b.addEventListener("click", function () {
      var txt = b.getAttribute("data-copy");
      var done = function () { toast("success", t("copied", "Link copied to clipboard.")); };
      if (navigator.clipboard && window.isSecureContext) { navigator.clipboard.writeText(txt).then(done); }
      else { var t = document.createElement("textarea"); t.value = txt; document.body.appendChild(t); t.select(); try { document.execCommand("copy"); done(); } catch (e) {} t.remove(); }
    });
  });

  // ---- Read aloud: voice follows the CONTENT language, not the UI language ----
  var synth = window.speechSynthesis, current = null, token = 0;
  function scriptLang(text, hint) {
    if (/[઀-૿]/.test(text)) return "gu-IN";
    if (/[ऀ-ॿ]/.test(text)) return "hi-IN";
    return hint && hint.indexOf("en") === 0 ? hint : "en-IN";
  }
  // Gujarati and Devanagari letters sit in the same order in Unicode (offset 0x180), so Gujarati text can be
  // read by a Hindi voice when no Gujarati voice is installed (very common on Windows / desktop Chrome).
  function gu2dev(s) { return s.replace(/[઀-૿]/g, function (c) { return String.fromCharCode(c.charCodeAt(0) - 0x180); }); }
  // Short pieces: browsers silently stop long utterances, and this also lets Pause / Stop react quickly.
  function pieces(text, hint) {
    var raw = text.replace(/\s+/g, " ").match(/[^.!?।\n]+[.!?।]*/g) || [text], out = [], buf = "";
    raw.forEach(function (r) {
      r = r.trim(); if (!r) return;
      if ((buf + " " + r).length > 180 && buf) { out.push(buf); buf = r; } else { buf = buf ? buf + " " + r : r; }
    });
    if (buf) out.push(buf);
    return out.map(function (x) { return { text: x, lang: scriptLang(x, hint) }; });
  }
  function loadVoices(cb) {
    var v = synth.getVoices();
    if (v.length) return cb(v);
    var done = false;
    function fin() { if (done) return; done = true; cb(synth.getVoices()); }
    synth.addEventListener("voiceschanged", fin, { once: true });
    setTimeout(fin, 1500);
  }
  function pickVoice(voices, lang) {
    var base = lang.split("-")[0], norm = function (x) { return (x || "").replace("_", "-").toLowerCase(); };
    return voices.find(function (v) { return norm(v.lang) === lang.toLowerCase(); }) ||
           voices.find(function (v) { return norm(v.lang).indexOf(base) === 0; }) || null;
  }
  var warned = {};
  // Information notes ("reading with the Hindi voice") appear ONE time on a device — it is already reading, no need to repeat it.
  function warnOnce(key, level, msg) {
    if (warned[key]) return; warned[key] = 1;
    if (level === "info") { if (store.get("shiksha-note-" + key)) return; store.set("shiksha-note-" + key, "1"); }
    toast(level, msg);
  }
  function markStop() {}
  function stop() { token++; if (synth) synth.cancel(); if (current) current.classList.remove("playing"); current = null; markStop(false); }
  function speak(btn) {
    if (!synth) { toast("error", t("noTts", "Read-aloud is not supported on this browser.")); return; }
    if (current === btn) { stop(); return; }                  // tapping the speaker again stops reading
    stop();
    var target = $(btn.getAttribute("data-speak")); if (!target) return;
    var text = target.innerText.trim(); if (!text) return;
    var parts = pieces(text, target.getAttribute("data-lang") || btn.getAttribute("data-lang"));
    var my = ++token; current = btn; btn.classList.add("playing"); markStop(true);
    loadVoices(function (voices) {
      if (my !== token) return;                          // stopped while voices were loading
      var i = 0;
      (function next() {
        if (my !== token) return;
        if (i >= parts.length) { stop(); return; }
        var p = parts[i++], lang = p.lang, str = p.text, v = pickVoice(voices, lang);
        if (!v && lang === "gu-IN") {                    // no Gujarati voice: use the Hindi voice on transliterated text
          var hv = pickVoice(voices, "hi-IN");
          if (hv) { v = hv; str = gu2dev(str); lang = "hi-IN"; warnOnce("gu2hi", "info", t("gu2hi", "Gujarati voice not found on this device — reading with the Hindi voice instead.")); }
        }
        if (!v && lang !== "en-IN" && voices.length) warnOnce("novoice", "info", t("noVoice", "No voice for this language is installed on this device, so the default voice is used."));
        var u = new SpeechSynthesisUtterance(str);
        u.lang = lang; if (v) { try { u.voice = v; } catch (e) {} } u.rate = 0.95;
        u.onend = next;
        u.onerror = function (ev) {
          if (my !== token || (ev && (ev.error === "canceled" || ev.error === "interrupted"))) return;
          warnOnce("ttserr", "error", t("ttsErr", "Couldn't read this aloud on this device.")); stop();
        };
        synth.speak(u);
      })();
    });
  }
  document.addEventListener("click", function (e) {
    var sp = e.target.closest && e.target.closest("[data-speak]"); if (sp) { speak(sp); return; }
  });
  window.addEventListener("beforeunload", stop);
  function initAutoread(fresh) {
    var auto = $("[data-autoread]"); if (!auto) return;
    auto.checked = store.get("shiksha-autoread") === "1";
    if (auto.checked && synth && fresh) { var ab = $("[data-speak][data-auto]"); if (ab) setTimeout(function () { speak(ab); }, 450); }
  }
  document.addEventListener("change", function (e) {
    if (e.target.matches && e.target.matches("[data-autoread]")) { store.set("shiksha-autoread", e.target.checked ? "1" : ""); if (!e.target.checked) stop(); }
  });
  initAutoread(true);

  // ---- learning-time heartbeat (only while the tab is visible) ----
  var hb = $("[data-heartbeat]");
  if (hb) {
    setInterval(function () {
      if (document.visibilityState !== "visible") return;
      fetch(hb.getAttribute("data-heartbeat"), { method: "POST", headers: { "X-CSRFToken": hb.getAttribute("data-csrf") }, credentials: "same-origin" });
    }, 30000);
  }

  // ---- login page: remembered accounts ("Continue as …") ----
  var acctBox = $("[data-accounts]");
  if (acctBox) {
    var KEY = "shiksha-accounts", list = [];
    try { list = JSON.parse(store.get(KEY) || "[]"); } catch (e) {}
    var form = $("#login-form"), uid = $("#id_username"), pw = $("#id_password");
    // The browser's password manager may have auto-filled ANOTHER account's password when the page loaded.
    // So: picking an account always starts with an empty password box, and changing the identifier by hand
    // clears any password the user did not type themselves.
    var chosen = $("[data-chosen]"), uidField = $("[data-uid-field]"), typedPw = false;
    pw.addEventListener("keydown", function () { typedPw = true; });
    pw.addEventListener("paste", function () { typedPw = true; });
    uid.addEventListener("input", function () { if (!typedPw) pw.value = ""; });
    function resetPw() {
      pw.value = ""; typedPw = false;
      pw.setAttribute("autocomplete", "new-password");        // stops Chrome re-filling a different saved login
      setTimeout(function () { pw.value = ""; }, 60);
    }
    function choose(id) {
      uid.value = id; resetPw();
      chosen.querySelector("strong").textContent = id; chosen.querySelector(".avatar").textContent = id.charAt(0).toUpperCase();
      chosen.hidden = false; uidField.hidden = true; acctBox.hidden = true;
      chosen.classList.remove("pop-in"); void chosen.offsetWidth; chosen.classList.add("pop-in");
      pw.focus();
    }
    var notYou = $("[data-not-you]");
    if (notYou) notYou.addEventListener("click", function () {
      chosen.hidden = true; uidField.hidden = false; acctBox.hidden = !list.length; uid.value = ""; resetPw(); uid.focus();
    });
    function paint() {
      acctBox.innerHTML = ""; acctBox.hidden = !list.length;
      list.forEach(function (id) {
        var b = document.createElement("div"); b.className = "acct"; b.setAttribute("role", "button"); b.tabIndex = 0;
        b.innerHTML = '<div class="avatar"></div><span></span><button type="button" class="x" aria-label="Remove">&times;</button>';
        b.querySelector(".avatar").textContent = id.charAt(0).toUpperCase(); b.querySelector("span").textContent = id;
        function pick() { choose(id); }
        b.addEventListener("click", function (e) {
          if (e.target.closest(".x")) { list = list.filter(function (x) { return x !== id; }); store.set(KEY, JSON.stringify(list)); paint(); return; }
          pick();
        });
        b.addEventListener("keydown", function (e) { if (e.key === "Enter") pick(); });
        acctBox.appendChild(b);
      });
    }
    paint();
    form.addEventListener("submit", function () {   // identifier only — never the password
      var v = uid.value.trim(); if (!v) return;
      list = [v].concat(list.filter(function (x) { return x.toLowerCase() !== v.toLowerCase(); })).slice(0, 4); store.set(KEY, JSON.stringify(list));
    });
  }

  // =====================================================================
  // Celebrations: confetti + "well done" popup (respects reduced-motion)
  // =====================================================================
  var reduced = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  function confetti(duration) {
    if (reduced) return;
    var cv = document.createElement("canvas"); cv.className = "confetti"; document.body.appendChild(cv);
    var ctx = cv.getContext("2d"), W = cv.width = window.innerWidth, H = cv.height = window.innerHeight;
    var colors = ["#c8102e", "#ef4a63", "#f5c542", "#ffffff", "#12b06a", "#7c3aed"], parts = [], n = W < 600 ? 90 : 160;
    for (var i = 0; i < n; i++) parts.push({ x: W / 2 + (Math.random() - .5) * W * .3, y: H * .35, vx: (Math.random() - .5) * 14, vy: -Math.random() * 15 - 5,
      w: 6 + Math.random() * 7, h: 8 + Math.random() * 8, r: Math.random() * 6, vr: (Math.random() - .5) * .35, c: colors[i % colors.length] });
    var t0 = performance.now(), end = duration || 2800;
    (function frame(t) {
      var el = t - t0; ctx.clearRect(0, 0, W, H);
      parts.forEach(function (p) {
        p.vy += .32; p.vx *= .992; p.x += p.vx; p.y += p.vy; p.r += p.vr;
        ctx.save(); ctx.globalAlpha = Math.max(0, 1 - el / end); ctx.translate(p.x, p.y); ctx.rotate(p.r); ctx.fillStyle = p.c; ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h); ctx.restore();
      });
      if (el < end) requestAnimationFrame(frame); else cv.parentNode.removeChild(cv);
    })(t0);
  }
  window.shikshaConfetti = confetti;

  function showCelebration(src) {
    if (!src) return;
    var d = src.dataset, root = document.createElement("div");
    root.className = "celebrate"; root.setAttribute("role", "dialog"); root.setAttribute("aria-modal", "true");
    var img = document.querySelector(".fab img"), mascot = img ? img.src.replace("vivi-sm", "vivi") : "";
    root.innerHTML = '<div class="celebrate-card"><img src="' + mascot + '" alt=""><div class="c-check"><svg viewBox="0 0 52 52" width="52" height="52"><circle cx="26" cy="26" r="23" fill="none" stroke="currentColor" stroke-width="3"/><path d="M15 27l8 8 14-16" fill="none" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/></svg></div><h2></h2><p></p><div class="c-actions"></div></div>';
    root.querySelector("h2").textContent = d.title; root.querySelector("p").textContent = d.text;
    var act = root.querySelector(".c-actions");
    function close() { root.classList.add("out"); setTimeout(function () { if (root.parentNode) root.parentNode.removeChild(root); }, 220); document.removeEventListener("keydown", onKey); }
    function onKey(e) { if (e.key === "Escape") close(); }
    if (d.ctaUrl && d.ctaLabel) { var a = document.createElement("a"); a.className = "btn lg"; a.href = d.ctaUrl; a.textContent = d.ctaLabel; act.appendChild(a); }
    var c = document.createElement("button"); c.type = "button"; c.className = "btn ghost"; c.textContent = d.ctaUrl ? t("notNow", "Not now") : t("cont", "Continue"); c.addEventListener("click", close); act.appendChild(c);
    root.addEventListener("click", function (e) { if (e.target === root) close(); });
    document.addEventListener("keydown", onKey); document.body.appendChild(root); confetti(3200);
    if (src.parentNode) src.parentNode.removeChild(src);
  }
  showCelebration($("#celebrate-src"));

  // animated progress rings (0 -> value)
  function animateRings(scope) {
    if (reduced) return;
    $$(".ring[style*='--p']", scope).forEach(function (r) {
      var v = parseFloat(r.style.getPropertyValue("--p")); if (!v) return;
      r.style.setProperty("--p", 0); void r.offsetWidth; r.classList.add("ring-anim");
      requestAnimationFrame(function () { r.style.setProperty("--p", v); });
    });
  }
  animateRings(document);

  // =====================================================================
  // Soft navigation inside a module: mark-complete / next / previous swap only
  // the changed parts of the page — no reload, no jump back to the top.
  // =====================================================================
  var SWAP = ["mod-head", "mod-tabs", "sop-area"], busy = false;
  function swapFrom(doc) {
    SWAP.forEach(function (id) { var o = document.getElementById(id), n = doc.getElementById(id); if (o && n) o.replaceWith(document.adoptNode(n)); });
  }
  function ensureStepVisible() {
    var card = document.getElementById("step-card"); if (!card) return;
    var r = card.getBoundingClientRect(), vh = window.innerHeight;
    if (r.top < 70 || r.top > vh * 0.6) window.scrollTo({ top: window.scrollY + r.top - 78, behavior: reduced ? "auto" : "smooth" });
  }
  // A friendly nudge after each completed step (the full celebration still shows at 100%).
  function cheer() {
    var p = $("#sop-area .sop-progress"); if (!p || window.__prevDone == null) return;
    var done = parseInt(p.dataset.done, 10), total = parseInt(p.dataset.total, 10), left = total - done;
    if (done > window.__prevDone && left > 0 && !$("#celebrate-src")) {
      var msg = t(left <= 2 ? "almost" : "cheer", "").replace("{n}", left); if (msg) toast("success", msg, 2200);
      if (navigator.vibrate) { try { navigator.vibrate(18); } catch (e) {} }
    }
  }
  function softGo(url, form, trigger) {
    if (busy) return; busy = true;
    var oldFill = $("#sop-area .sop-fill"), oldW = oldFill ? oldFill.style.width : null, oldMark = $("#sop-area .sop-mark"), oldL = oldMark ? oldMark.style.left : null;
    var prog0 = $("#sop-area .sop-progress"); window.__prevDone = prog0 ? parseInt(prog0.dataset.done, 10) : null;
    var oldCard = document.getElementById("step-card"), prevN = oldCard ? parseInt(oldCard.dataset.step, 10) : null;
    var init = { credentials: "same-origin", headers: { "X-Requested-With": "fetch" } };
    if (form) { init.method = "POST"; init.body = new FormData(form); }
    if (trigger) trigger.classList.add("is-loading");
    fetch(url, init).then(function (r) { return r.text().then(function (t) { return { url: r.url, text: t, ok: r.ok }; }); })
      .then(function (res) {
        var doc = new DOMParser().parseFromString(res.text, "text/html");
        if (!res.ok || !doc.getElementById("sop-area")) { window.location.href = url; return; }
        stop(); swapFrom(doc);
        history.replaceState(null, "", res.url);
        $$("[data-flash]", doc).forEach(function (m) { toast(m.getAttribute("data-level"), m.textContent.trim()); });
        // progress bar: glide from the old value to the new one
        var nf = $("#sop-area .sop-fill"), nm = $("#sop-area .sop-mark"), bar = $("#sop-area .sop-progress");
        if (nf && oldW !== null && !reduced) {
          var tw = nf.style.width, tl = nm ? nm.style.left : null;
          nf.style.width = oldW; if (nm && oldL !== null) nm.style.left = oldL; void nf.offsetWidth;
          nf.style.width = tw; if (nm && tl !== null) nm.style.left = tl;
          if (parseFloat(tw) > parseFloat(oldW) && bar) { bar.classList.add("pulse"); setTimeout(function () { bar.classList.remove("pulse"); }, 900); }
        }
        // step card: slide in from the right when moving forward, from the left when going back
        var card = document.getElementById("step-card"), newN = card ? parseInt(card.dataset.step, 10) : null;
        if (card && prevN !== null && newN !== prevN && !reduced) card.classList.add(newN > prevN ? "enter-fwd" : "enter-back");
        syncConsent(); initAutoread(true); animateRings(document.getElementById("mod-head")); ensureStepVisible();
        showCelebration(doc.getElementById("celebrate-src"));
        cheer();
      })
      .catch(function () { toast("error", t("net", "Couldn't reach the server. Please try again.")); if (trigger) { trigger.classList.remove("is-loading"); trigger.disabled = false; } })
      .then(function () { busy = false; });
  }
  document.addEventListener("click", function (e) {
    var a = e.target.closest && e.target.closest("a[data-soft]");
    if (!a || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || !document.getElementById("sop-area")) return;
    e.preventDefault(); softGo(a.href, null, null);
  });
  document.addEventListener("submit", function (e) {
    var f = e.target; if (!f.matches || !f.matches("form[data-soft-form]") || !document.getElementById("sop-area")) return;
    e.preventDefault(); softGo(f.getAttribute("action") || window.location.href, f, e.submitter || f.querySelector("button[type=submit]"));
  });

  // "Jump to step": type a number (or pick from the list). Out-of-range numbers are clamped.
  function jumpTo(box) {
    var input = $("[data-jump-input]", box), max = parseInt(input.getAttribute("max"), 10) || 1, n = parseInt(input.value, 10);
    if (!n) { input.focus(); return; }
    n = Math.min(Math.max(n, 1), max);
    var u = new URL(window.location.href); u.searchParams.set("tab", "sops"); u.searchParams.set("step", n);
    closeDropdowns(); softGo(u.href, null, null);
  }
  document.addEventListener("click", function (e) {
    var go = e.target.closest && e.target.closest("[data-jump-go]"); if (go) { e.preventDefault(); jumpTo(go.closest(".jump-box")); }
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && e.target.matches && e.target.matches("[data-jump-input]")) { e.preventDefault(); jumpTo(e.target.closest(".jump-box")); }
  });

  // sticky offsets: the progress bar sits right under the (variable-height) top bar
  function setStickyTop() {
    var tb = $(".topbar"), vb = $(".viewbar"); if (!tb) return;
    root.style.setProperty("--stick-top", ((vb ? vb.offsetHeight : 0) + tb.offsetHeight) + "px");
  }
  setStickyTop(); window.addEventListener("resize", setStickyTop); window.addEventListener("load", setStickyTop);

  // =====================================================================
  // Image galleries: thumbnail switcher + full-screen lightbox (arrows / swipe / Esc)
  // =====================================================================
  document.addEventListener("click", function (e) {
    var th = e.target.closest && e.target.closest(".g-thumb"); if (!th) return;
    var g = th.closest("[data-gallery]"), main = g.querySelector(".g-main");
    main.href = th.dataset.src; main.dataset.caption = th.dataset.cap || ""; main.querySelector("img").src = th.dataset.src;
    $$(".g-thumb", g).forEach(function (x) { x.classList.toggle("on", x === th); });
  });
  function openLightbox(links, start) {
    var i = start, root = document.createElement("div");
    root.className = "lightbox"; root.setAttribute("role", "dialog"); root.setAttribute("aria-modal", "true");
    root.innerHTML = '<button type="button" class="lb-x" aria-label="Close">&times;</button><button type="button" class="lb-nav lb-prev" aria-label="Previous">&#8249;</button><figure><img alt=""><figcaption></figcaption></figure><button type="button" class="lb-nav lb-next" aria-label="Next">&#8250;</button>';
    var img = root.querySelector("img"), cap = root.querySelector("figcaption");
    function show() { var l = links[i]; img.src = l.href; cap.textContent = l.dataset.caption || ""; root.classList.toggle("single", links.length < 2); }
    function go(d) { i = (i + d + links.length) % links.length; show(); }
    function close() { document.removeEventListener("keydown", key); if (root.parentNode) root.parentNode.removeChild(root); }
    function key(e) { if (e.key === "Escape") close(); else if (e.key === "ArrowLeft") go(-1); else if (e.key === "ArrowRight") go(1); }
    root.querySelector(".lb-x").addEventListener("click", close);
    root.querySelector(".lb-prev").addEventListener("click", function () { go(-1); });
    root.querySelector(".lb-next").addEventListener("click", function () { go(1); });
    root.addEventListener("click", function (e) { if (e.target === root) close(); });
    var sx = null;
    root.addEventListener("touchstart", function (e) { sx = e.touches[0].clientX; }, { passive: true });
    root.addEventListener("touchend", function (e) { if (sx === null) return; var dx = e.changedTouches[0].clientX - sx; if (Math.abs(dx) > 50) go(dx < 0 ? 1 : -1); sx = null; }, { passive: true });
    document.addEventListener("keydown", key); document.body.appendChild(root); show();
  }
  document.addEventListener("click", function (e) {
    var a = e.target.closest && e.target.closest("a[data-lightbox]"); if (!a || e.button !== 0 || e.metaKey || e.ctrlKey) return;
    e.preventDefault();
    var g = a.dataset.lightbox, links = $$('.g-hidden a[data-lightbox="' + g + '"]');
    if (!links.length) links = $$('a[data-lightbox="' + g + '"]');
    var idx = links.findIndex(function (l) { return l.href === a.href; });
    openLightbox(links, Math.max(idx, 0));
  });

  // Text size for SOP steps (normal → large → extra large), remembered on this device.
  (function () {
    var sizes = ["", "l", "xl"], root = document.documentElement;
    try { root.dataset.text = localStorage.getItem("shiksha-text") || ""; } catch (e) {}
    document.addEventListener("click", function (e) {
      if (!e.target.closest || !e.target.closest("[data-textsize]")) return;
      var i = (sizes.indexOf(root.dataset.text || "") + 1) % sizes.length;
      root.dataset.text = sizes[i]; try { localStorage.setItem("shiksha-text", sizes[i]); } catch (err) {}
    });
  })();

  // ---- Feel-good touches: cards fade up as they appear, numbers count up, buttons ripple ----
  (function () {
    document.documentElement.classList.add("js");
    if (reduced) return;
    if ("IntersectionObserver" in window) {
      var io = new IntersectionObserver(function (es) { es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } }); }, { threshold: .08 });
      $$(".stat, .mod-card, .kb-card, .quick a, .card.hover, .gl-card").forEach(function (el, i) { el.classList.add("reveal"); el.style.transitionDelay = Math.min(i % 8, 7) * 45 + "ms"; io.observe(el); });
    }
    $$(".stat strong").forEach(function (el) {
      var m = el.firstChild && el.firstChild.nodeType === 3 ? el.firstChild.nodeValue.match(/^(\d+)(.*)$/) : null; if (!m) return;
      var end = parseInt(m[1], 10), tail = m[2], t0 = null; if (end < 2) return;
      (function step(ts) { t0 = t0 || ts; var k = Math.min(1, (ts - t0) / 700); el.firstChild.nodeValue = Math.round(end * (1 - Math.pow(1 - k, 3))) + tail; if (k < 1) requestAnimationFrame(step); })(performance.now());
    });
    document.addEventListener("pointerdown", function (e) {
      var b = e.target.closest && e.target.closest(".btn, .quick a, .kb-cat"); if (!b || b.disabled) return;
      var r = b.getBoundingClientRect(), s = document.createElement("span"), d = Math.max(r.width, r.height);
      s.className = "ripple"; s.style.cssText = "width:" + d + "px;height:" + d + "px;left:" + (e.clientX - r.left - d / 2) + "px;top:" + (e.clientY - r.top - d / 2) + "px";
      if (getComputedStyle(b).position === "static") b.style.position = "relative";
      b.style.overflow = "hidden"; b.appendChild(s); setTimeout(function () { b.removeChild(s); }, 600);
    });
  })();

  // ---- Tap bounce: anything you press gives a small, satisfying pop ----
  (function () {
    if (reduced) return;
    var SEL = ".btn, .quick a, .kb-card, .kb-cat, .chip, .mod-card, .card.hover, .acct, .bottom-nav a, .bottom-nav button, .nav a, .icon-btn, .dd-btn, .dd-item, .tab, .jump-item";
    document.addEventListener("pointerdown", function (e) {
      var el = e.target.closest && e.target.closest(SEL); if (!el || el.disabled || el.classList.contains("disabled")) return;
      el.classList.remove("pop"); void el.offsetWidth; el.classList.add("pop");
      el.addEventListener("animationend", function done(ev) { if (ev.animationName === "pop") { el.classList.remove("pop"); el.removeEventListener("animationend", done); } });
    }, { passive: true });
  })();

  // ---- 3D: cards tilt toward the pointer; the sign-in scene has parallax depth. Mouse devices only, never with "reduce motion".
  (function () {
    if (reduced || !window.matchMedia || !matchMedia("(hover: hover) and (pointer: fine)").matches) return;
    var SEL = ".mod-card, .kbx-card, .kbx-tile, .quick-big a, .stat, .chart-card, .acct-menu .card, .journey li, .card.hover, .tilt-soft", cur = null, raf = 0, ev = null;
    function reset(el) { if (!el) return; el.style.transform = ""; el.classList.remove("tilting"); }
    function apply() {
      raf = 0; if (!ev) return;
      var el = ev.target.closest && ev.target.closest(SEL);
      if (cur && cur !== el) reset(cur);
      cur = el; if (!el) return;
      var r = el.getBoundingClientRect(), x = (ev.clientX - r.left) / r.width, y = (ev.clientY - r.top) / r.height;
      var max = el.classList.contains("tilt-soft") || r.width > 600 ? 2.2 : 7;
      el.classList.add("tilting");
      el.style.transform = "perspective(1000px) rotateX(" + ((0.5 - y) * max * 2).toFixed(2) + "deg) rotateY(" + ((x - 0.5) * max * 2).toFixed(2) + "deg) translateZ(8px)";
    }
    document.addEventListener("pointermove", function (e) { ev = e; if (!raf) raf = requestAnimationFrame(apply); }, { passive: true });
    document.addEventListener("pointerleave", function () { reset(cur); cur = null; });
    window.addEventListener("blur", function () { reset(cur); cur = null; });
    // parallax: elements with data-depth drift slightly with the pointer (sign-in page)
    var layers = $$("[data-depth]");
    if (layers.length) document.addEventListener("pointermove", function (e) {
      var nx = e.clientX / innerWidth - 0.5, ny = e.clientY / innerHeight - 0.5;
      layers.forEach(function (l) { var d = parseFloat(l.getAttribute("data-depth")) || 10; l.style.translate = (nx * d).toFixed(1) + "px " + (ny * d).toFixed(1) + "px"; });
    }, { passive: true });
  })();
})();
