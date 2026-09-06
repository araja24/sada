/* Sada single-page flow controller (PRD §4).
   Steps are <section class="step"> elements toggled with [hidden]; this module
   owns navigation + the reciter/passage-selection steps (issue #8). Recording
   (issue #9) and results (issue #10) are delegated to SadaRecord / SadaResults. */
(function () {
  "use strict";

  var STEPS = ["welcome", "auth", "reciter", "passage", "record", "analyzing", "results"];
  var navStack = [];
  var authMode = "signup"; // or "login"

  var state = {
    reciter: null, // {id, slug, name, description}
    passage: null, // full /api/passages/fatiha payload
    startVerse: null,
    endVerse: null,
    lastAttempt: null,
  };

  var els = {};
  function $(id) { return document.getElementById(id); }

  document.addEventListener("DOMContentLoaded", function () {
    STEPS.forEach(function (s) { els[s] = $("step-" + s); });
    els.errorBanner = $("error-banner");

    $("start-btn").addEventListener("click", function () { goReciter(); });

    $("nav-home").addEventListener("click", function (e) {
      e.preventDefault();
      stopRefAudio();
      showStep("welcome", { replace: true });
    });
    $("nav-practice").addEventListener("click", function () {
      stopRefAudio();
      goReciter();
    });
    $("nav-attempts").addEventListener("click", goMyAttempts);
    document.querySelectorAll("[data-back]").forEach(function (b) {
      b.addEventListener("click", back);
    });
    $("to-record-btn").addEventListener("click", goRecord);

    $("auth-form").addEventListener("submit", submitAuth);
    $("auth-toggle").addEventListener("click", function () {
      setAuthMode(authMode === "signup" ? "login" : "signup");
    });

    setupRefPlayer();
    Promise.resolve(refreshAccountNav()).then(renderRecentAttempts);
    showStep("welcome", { replace: true });
  });

  // --- navigation --------------------------------------------------

  function showStep(name, opts) {
    opts = opts || {};
    STEPS.forEach(function (s) { els[s].hidden = s !== name; });
    if (!opts.replace) navStack.push(name);
    clearError();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function back() {
    stopRefAudio();
    navStack.pop(); // current
    var prev = navStack.pop() || "welcome";
    showStep(prev);
  }

  // --- step: reciter ---------------------------------------------

  function goReciter() {
    showStep("reciter");
    var list = $("reciter-list");
    list.innerHTML = "<p class='muted'>Loading reciters…</p>";
    SadaApi.reciters().then(function (reciters) {
      if (!reciters.length) {
        list.innerHTML =
          "<p class='muted'>No reciter reference data has been built yet. " +
          "Run <code>scripts/build_reference.py</code> to add one.</p>";
        return;
      }
      list.innerHTML = "";
      reciters.forEach(function (r) {
        var card = document.createElement("button");
        card.className = "reciter-card";
        card.type = "button";
        card.innerHTML = "<h3></h3><p></p>";
        card.querySelector("h3").textContent = r.name;
        card.querySelector("p").textContent = r.description || "";
        card.addEventListener("click", function () { chooseReciter(r); });
        list.appendChild(card);
      });
    }).catch(showError);
  }

  function chooseReciter(reciter) {
    state.reciter = reciter;
    showStep("passage");
    var vl = $("verse-list");
    vl.innerHTML = "<li class='muted'>Loading verses…</li>";
    SadaApi.passage(reciter.id).then(function (passage) {
      state.passage = passage;
      var verses = passage.verses;
      state.startVerse = verses[0].verse_number;
      state.endVerse = verses[verses.length - 1].verse_number;
      renderVerses();
      prepareRefAudio();
    }).catch(showError);
  }

  // --- step: passage / verse range ------------------------------

  function renderVerses() {
    var vl = $("verse-list");
    vl.innerHTML = "";
    state.passage.verses.forEach(function (v) {
      var li = document.createElement("li");
      li.className = "verse-row";
      li.dataset.verse = v.verse_number;
      li.setAttribute("role", "button");
      li.tabIndex = 0;
      var text = document.createElement("span");
      text.className = "text";
      text.textContent = v.arabic_text || "(verse " + v.verse_number + ")";
      var num = document.createElement("span");
      num.className = "num";
      num.textContent = v.verse_number;
      li.appendChild(text);
      li.appendChild(num);
      li.addEventListener("click", function () { pickVerse(v.verse_number); });
      li.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pickVerse(v.verse_number); }
      });
      vl.appendChild(li);
    });
    paintRange();
  }

  // Two-tap range: first tap sets both ends; next tap extends/moves.
  var pendingStart = null;
  function pickVerse(n) {
    if (pendingStart === null) {
      pendingStart = n;
      state.startVerse = n;
      state.endVerse = n;
    } else {
      state.startVerse = Math.min(pendingStart, n);
      state.endVerse = Math.max(pendingStart, n);
      pendingStart = null;
    }
    paintRange();
  }

  function paintRange() {
    var lo = state.startVerse, hi = state.endVerse;
    document.querySelectorAll("#verse-list .verse-row").forEach(function (row) {
      var n = Number(row.dataset.verse);
      row.classList.toggle("in-range", n >= lo && n <= hi);
      row.classList.toggle("endpoint", n === lo || n === hi);
    });
    var readout = $("range-readout");
    readout.textContent = lo === hi
      ? "Verse " + lo + " selected"
      : "Verses " + lo + "–" + hi + " selected";
    prepareRefAudio();
  }

  // --- reference playback --------------------------------------

  function setupRefPlayer() {
    var btn = $("ref-play-btn");
    var audio = $("ref-audio");
    btn.addEventListener("click", function () {
      if (audio.paused) { audio.play(); } else { audio.pause(); }
    });
    audio.addEventListener("play", function () {
      btn.textContent = "⏸ Pause";
      btn.setAttribute("aria-pressed", "true");
    });
    audio.addEventListener("pause", function () {
      btn.textContent = "▶ Listen to the reciter";
      btn.setAttribute("aria-pressed", "false");
      clearSpeaking();
    });
    audio.addEventListener("ended", clearSpeaking);
    audio.addEventListener("timeupdate", highlightSpeakingVerse);
  }

  function prepareRefAudio() {
    if (!state.passage) return;
    var player = $("ref-player");
    player.hidden = false;
    var audio = $("ref-audio");
    var url = state.passage.reference_audio_url;
    if (audio.getAttribute("src") !== url) audio.src = url;
  }

  function rangeVerses() {
    return state.passage.verses.filter(function (v) {
      return v.verse_number >= state.startVerse && v.verse_number <= state.endVerse;
    });
  }

  function highlightSpeakingVerse() {
    var audio = $("ref-audio");
    var ms = audio.currentTime * 1000;
    var active = null;
    rangeVerses().forEach(function (v) {
      if (ms >= v.start_ms && ms <= v.end_ms) active = v.verse_number;
    });
    document.querySelectorAll("#verse-list .verse-row").forEach(function (row) {
      row.classList.toggle("speaking", Number(row.dataset.verse) === active);
    });
    // Stop once we've played past the selected range's end.
    var last = rangeVerses().slice(-1)[0];
    if (last && ms > last.end_ms + 400) audio.pause();
  }

  function clearSpeaking() {
    document.querySelectorAll("#verse-list .verse-row.speaking")
      .forEach(function (r) { r.classList.remove("speaking"); });
  }
  function clearSpeakingHard() { clearSpeaking(); }

  function stopRefAudio() {
    var audio = $("ref-audio");
    if (audio && !audio.paused) audio.pause();
    if (audio) audio.currentTime = 0;
  }

  // When the range changes, seek the reference audio to the range start so
  // "Listen" plays the chosen verses.
  function seekRefToRangeStart() {
    var audio = $("ref-audio");
    var first = rangeVerses()[0];
    if (audio && first) audio.currentTime = first.start_ms / 1000;
  }
  document.addEventListener("DOMContentLoaded", function () {
    $("ref-audio").addEventListener("loadedmetadata", seekRefToRangeStart);
  });

  // --- step: record / analyze / results -----------------------

  function goRecord() {
    stopRefAudio();
    showStep("record");
    SadaRecord.mount($("record-mount"), {
      reciterName: state.reciter.name,
      startVerse: state.startVerse,
      endVerse: state.endVerse,
      onSubmit: submitAttempt,
    });
  }

  function submitAttempt(audioBlob) {
    showStep("analyzing", { replace: false });
    var form = new FormData();
    form.append("reciter_id", state.reciter.id);
    form.append("start_verse", state.startVerse);
    form.append("end_verse", state.endVerse);
    form.append("audio", audioBlob, "recitation.webm");

    SadaApi.submitAttempt(form).then(function (attempt) {
      state.lastAttempt = attempt;
      showResults(attempt);
      renderRecentAttempts();
    }).catch(function (err) {
      // Stay on the record step with the take intact (§5.10 friendly message).
      showStep("record");
      SadaRecord.recover();
      showError(err);
    });
  }

  function showResults(attempt) {
    showStep("results");
    SadaResults.render($("results-mount"), attempt, {
      passage: state.passage,
      reciterName: state.reciter ? state.reciter.name : "the reciter",
      onTryAgain: state.reciter ? goRecord : function () { showStep("welcome"); },
      savePrompt: currentUser ? null : function () { setAuthMode("signup"); showStep("auth"); },
    });
  }

  // --- account nav + auth (docs/adr/0002) --------------------

  var currentUser = null;

  function refreshAccountNav() {
    var nav = $("account-nav");
    if (!nav) return;
    return SadaApi.me().then(function (user) {
      currentUser = user && user.email ? user : null;
      nav.hidden = false;
      nav.innerHTML = "";
      if (currentUser) {
        nav.appendChild(textEl("span", "muted", currentUser.email));
        nav.appendChild(navButton("Log out", function () {
          SadaApi.logout().then(function () {
            refreshAccountNav();
            renderRecentAttempts();
          });
        }));
      } else {
        nav.appendChild(navButton("Log in", function () { setAuthMode("login"); showStep("auth"); }));
        nav.appendChild(navButton("Sign up", function () { setAuthMode("signup"); showStep("auth"); }));
      }
    }).catch(function () { /* nav is optional chrome */ });
  }

  function setAuthMode(mode) {
    authMode = mode;
    $("auth-title").textContent = mode === "signup" ? "Save your attempts" : "Welcome back";
    $("auth-submit").textContent = mode === "signup" ? "Sign up" : "Log in";
    $("auth-toggle").textContent = mode === "signup"
      ? "I already have an account" : "I need to create an account";
    $("auth-intro").hidden = mode === "login";
    $("auth-password").setAttribute("autocomplete", mode === "signup" ? "new-password" : "current-password");
  }

  function submitAuth(e) {
    e.preventDefault();
    clearError();
    var email = $("auth-email").value.trim();
    var password = $("auth-password").value;
    var submit = $("auth-submit");
    submit.disabled = true;
    var call = authMode === "signup" ? SadaApi.signup : SadaApi.login;
    call(email, password).then(function () {
      $("auth-form").reset();
      return refreshAccountNav();
    }).then(function () {
      renderRecentAttempts();
      back(); // return to wherever they came from
    }).catch(function (err) {
      showError(err);
    }).then(function () {
      submit.disabled = false;
    });
  }

  // --- recent attempts (issue #11) --------------------------

  function goMyAttempts() {
    stopRefAudio();
    showStep("welcome", { replace: true });
    var box = $("recent-attempts");
    if (box && !box.hidden) {
      box.scrollIntoView({ behavior: "smooth", block: "start" });
    } else if (!currentUser) {
      setAuthMode("login");
      showStep("auth");
    }
  }

  function renderRecentAttempts() {
    var box = $("recent-attempts");
    if (!box) return;
    SadaApi.recentAttempts().then(function (rows) {
      if (!rows || !rows.length) { box.hidden = true; box.innerHTML = ""; return; }
      box.hidden = false;
      box.innerHTML = "";
      box.appendChild(textEl("h2", "recent-title", currentUser ? "Your attempts" : "Your recent attempts"));
      var ul = document.createElement("ul");
      ul.className = "recent-list";
      rows.forEach(function (r) {
        var li = document.createElement("li");
        var b = document.createElement("button");
        b.type = "button";
        b.className = "recent-item";
        b.innerHTML = "<span class='recent-score'>" + r.overall_score + "</span>" +
          "<span class='recent-meta'><strong>" + esc(r.label) + "</strong>" +
          "<span class='muted'> · verses " + r.start_verse + "–" + r.end_verse + " · " +
          new Date(r.created_at).toLocaleDateString() + "</span></span>";
        b.addEventListener("click", function () { openAttempt(r); });
        li.appendChild(b);
        ul.appendChild(li);
      });
      box.appendChild(ul);
      if (!currentUser) {
        box.appendChild(navButton("Sign up to keep these", function () {
          setAuthMode("signup"); showStep("auth");
        }));
      }
    }).catch(function () { box.hidden = true; });
  }

  function openAttempt(summary) {
    Promise.all([SadaApi.attempt(summary.attempt_id), SadaApi.passage(summary.reciter_id)])
      .then(function (out) {
        var attempt = out[0];
        state.passage = out[1];
        state.reciter = null;
        state.lastAttempt = attempt;
        showResults(attempt);
      }).catch(showError);
  }

  function esc(s) { var d = document.createElement("div"); d.textContent = s; return d.innerHTML; }
  function textEl(tag, cls, text) {
    var n = document.createElement(tag); if (cls) n.className = cls; n.textContent = text; return n;
  }
  function navButton(label, onClick) {
    var b = document.createElement("button");
    b.type = "button"; b.className = "btn btn-quiet back-btn"; b.textContent = label;
    b.addEventListener("click", onClick);
    return b;
  }

  // --- errors ------------------------------------------------

  function showError(err) {
    var msg = err && err.message ? err.message : String(err);
    els.errorBanner.textContent = msg;
    els.errorBanner.hidden = false;
    els.errorBanner.scrollIntoView({ behavior: "smooth", block: "center" });
  }
  function clearError() {
    els.errorBanner.hidden = true;
    els.errorBanner.textContent = "";
  }

  // expose a tiny hook for record.js / results.js error reporting
  window.SadaFlow = { showError: showError, clearError: clearError };
})();
