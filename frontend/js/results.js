/* Results page (PRD §4 step 7) — the visual centerpiece.

   SadaResults.render(container, attempt, { passage, reciterName, onTryAgain }) */
(function (global) {
  "use strict";

  var SUB_LABELS = {
    melody: "Melody",
    pacing: "Pacing",
    tone: "Tone similarity",
    elongation: "Elongation timing",
  };
  var SUB_HINT = {
    melody: "How closely your pitch movement follows the reciter's.",
    pacing: "How evenly your tempo matches, verse to verse.",
    tone: "How close your vocal timbre is — every voice is different.",
    elongation: "How your held (madd) syllables line up in length.",
  };

  function render(container, attempt, opts) {
    container.innerHTML = "";
    var focusedVerse = null;

    container.appendChild(overallBlock(attempt));
    container.appendChild(subScoreGrid(attempt));

    var verseSection = el("div", "verse-focus");
    container.appendChild(verseChips(attempt, function (v) {
      focusedVerse = (focusedVerse === v) ? null : v;
      paintChips();
      renderTips();
      drawChart();
    }));

    var chartWrap = el("figure", "chart-wrap");
    var canvas = document.createElement("canvas");
    canvas.className = "pitch-chart";
    canvas.setAttribute("role", "img");
    canvas.setAttribute("aria-label",
      "Pitch contour: your recitation compared to " + opts.reciterName + "'s, on a shared time axis.");
    var caption = el("figcaption", "muted");
    caption.innerHTML =
      "<span class='key key-ref'></span> " + esc(opts.reciterName) +
      " &nbsp; <span class='key key-you'></span> You";
    chartWrap.appendChild(canvas);
    chartWrap.appendChild(caption);
    container.appendChild(chartWrap);

    var tipsWrap = el("div", "tips-wrap");
    container.appendChild(tipsWrap);

    var actions = el("div", "results-actions");
    var again = button("btn btn-primary", "Try again");
    again.addEventListener("click", opts.onTryAgain);
    actions.appendChild(again);
    if (opts.savePrompt) {
      var save = button("btn btn-quiet", "Save your attempts");
      save.addEventListener("click", opts.savePrompt);
      actions.appendChild(save);
    }
    container.appendChild(actions);

    function paintChips() {
      container.querySelectorAll(".verse-chip").forEach(function (c) {
        c.classList.toggle("focused", Number(c.dataset.verse) === focusedVerse);
      });
    }

    function renderTips() {
      tipsWrap.innerHTML = "";
      var heading = el("h3", null);
      heading.textContent = focusedVerse ? "Tips for verse " + focusedVerse : "Tips";
      tipsWrap.appendChild(heading);

      var tips = attempt.tips.filter(function (t) {
        return !focusedVerse || t.verse === focusedVerse;
      });
      if (!tips.length) {
        var none = el("p", "muted");
        none.textContent = focusedVerse
          ? "Nothing stood out for this verse — nicely done."
          : "Nothing specific stood out across these verses. Keep practicing with the reciter.";
        tipsWrap.appendChild(none);
        return;
      }
      groupByVerse(tips).forEach(function (group) {
        var block = el("div", "tip-group");
        var vh = el("h4", null);
        vh.textContent = "Verse " + group.verse;
        block.appendChild(vh);
        var ul = el("ul", "tip-list");
        group.tips.forEach(function (t) {
          var li = el("li", "tip tip-" + t.type);
          li.textContent = t.text;
          ul.appendChild(li);
        });
        block.appendChild(ul);
        tipsWrap.appendChild(block);
      });
    }

    function drawChart() {
      drawPitchChart(canvas, attempt, opts.passage, focusedVerse);
    }

    renderTips();
    // Chart needs layout to have happened for clientWidth.
    requestAnimationFrame(drawChart);
    window.addEventListener("resize", debounce(drawChart, 150));
  }

  // --- pieces ---------------------------------------------------

  function overallBlock(attempt) {
    var wrap = el("div", "overall");
    var score = el("div", "overall-score");
    score.textContent = attempt.overall_score;
    var outof = el("span", "overall-outof");
    outof.textContent = "/ 100";
    score.appendChild(outof);
    var label = el("div", "overall-label");
    label.textContent = attempt.label;
    var range = el("p", "muted");
    range.textContent = attempt.start_verse === attempt.end_verse
      ? "Verse " + attempt.start_verse
      : "Verses " + attempt.start_verse + "–" + attempt.end_verse;
    wrap.appendChild(score);
    wrap.appendChild(label);
    wrap.appendChild(range);
    return wrap;
  }

  function subScoreGrid(attempt) {
    var grid = el("div", "subscore-grid");
    Object.keys(SUB_LABELS).forEach(function (key) {
      if (!(key in attempt.sub_scores)) return;
      var card = el("div", "subscore-card");
      var name = el("div", "subscore-name");
      name.textContent = SUB_LABELS[key];
      var val = el("div", "subscore-val");
      val.textContent = attempt.sub_scores[key];
      var meter = el("div", "subscore-meter");
      var fill = el("span", null);
      fill.style.width = clamp(attempt.sub_scores[key]) + "%";
      meter.appendChild(fill);
      var hint = el("p", "subscore-hint muted");
      hint.textContent = SUB_HINT[key];
      card.appendChild(name);
      card.appendChild(val);
      card.appendChild(meter);
      card.appendChild(hint);
      grid.appendChild(card);
    });
    return grid;
  }

  function verseChips(attempt, onPick) {
    var wrap = el("div", "verse-chips");
    var heading = el("h3", "visually-hidden");
    heading.textContent = "Per-verse scores";
    wrap.appendChild(heading);
    attempt.per_verse.forEach(function (pv) {
      var chip = button("verse-chip", "");
      chip.dataset.verse = pv.verse;
      chip.innerHTML = "<span class='vc-num'>V" + pv.verse + "</span><span class='vc-score'>" +
        pv.score + "</span>";
      chip.setAttribute("aria-label", "Verse " + pv.verse + ", score " + pv.score + ". Focus its tips.");
      chip.addEventListener("click", function () { onPick(pv.verse); });
      wrap.appendChild(chip);
    });
    return wrap;
  }

  // --- canvas pitch chart (PRD §6/§8) --------------------------

  function drawPitchChart(canvas, attempt, passage, focusedVerse) {
    var overlay = attempt.pitch_overlay;
    var ctx = canvas.getContext("2d");
    var cssW = canvas.clientWidth || 600;
    var cssH = 260;
    var dpr = window.devicePixelRatio || 1;
    canvas.width = cssW * dpr;
    canvas.height = cssH * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, cssW, cssH);

    var pad = { l: 14, r: 14, t: 14, b: 22 };
    var plotW = cssW - pad.l - pad.r;
    var plotH = cssH - pad.t - pad.b;

    var all = overlay.reference_semitones.concat(overlay.user_semitones_aligned)
      .filter(function (v) { return isFinite(v); });
    var lo = Math.min.apply(null, all), hi = Math.max.apply(null, all);
    if (!isFinite(lo) || lo === hi) { lo = -6; hi = 6; }
    var range = (hi - lo) || 1;
    lo -= range * 0.12; hi += range * 0.12;

    function x(t) { return pad.l + t * plotW; }
    function y(semi) { return pad.t + (1 - (semi - lo) / (hi - lo)) * plotH; }

    // verse boundary markers
    var bounds = verseBoundaries(attempt, passage);
    ctx.strokeStyle = "#e7e1d8";
    ctx.fillStyle = "#9a9186";
    ctx.font = "11px Inter, sans-serif";
    ctx.lineWidth = 1;
    bounds.forEach(function (b) {
      ctx.beginPath(); ctx.moveTo(x(b.t), pad.t); ctx.lineTo(x(b.t), pad.t + plotH); ctx.stroke();
      if (b.label) ctx.fillText(b.label, x(b.t) + 3, pad.t + 11);
    });

    // focused-verse shading
    if (focusedVerse) {
      var seg = bounds.filter(function (b) { return b.verse === focusedVerse; })[0];
      var next = bounds.filter(function (b) { return b.verse === focusedVerse + 1; })[0];
      var x0 = seg ? x(seg.t) : pad.l;
      var x1 = next ? x(next.t) : pad.l + plotW;
      ctx.fillStyle = "rgba(63,111,94,0.08)";
      ctx.fillRect(x0, pad.t, x1 - x0, plotH);
    }

    line(ctx, overlay.time_axis, overlay.reference_semitones, x, y, "#3f6f5e", 2);
    line(ctx, overlay.time_axis, overlay.user_semitones_aligned, x, y, "#c1873b", 2);
  }

  function line(ctx, xs, ys, x, y, color, width) {
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    ctx.lineJoin = "round";
    ctx.beginPath();
    var started = false;
    for (var i = 0; i < xs.length; i++) {
      if (!isFinite(ys[i])) { started = false; continue; }
      var px = x(xs[i]), py = y(ys[i]);
      if (!started) { ctx.moveTo(px, py); started = true; } else { ctx.lineTo(px, py); }
    }
    ctx.stroke();
  }

  function verseBoundaries(attempt, passage) {
    if (!passage || !passage.verses) return [];
    var inRange = passage.verses.filter(function (v) {
      return v.verse_number >= attempt.start_verse && v.verse_number <= attempt.end_verse;
    });
    if (!inRange.length) return [];
    var startMs = inRange[0].start_ms;
    var endMs = inRange[inRange.length - 1].end_ms;
    var span = (endMs - startMs) || 1;
    var out = [];
    inRange.forEach(function (v) {
      out.push({
        verse: v.verse_number,
        t: Math.max(0, Math.min(1, (v.start_ms - startMs) / span)),
        label: "V" + v.verse_number,
      });
    });
    return out;
  }

  // --- helpers ------------------------------------------------

  function groupByVerse(tips) {
    var byVerse = {};
    tips.forEach(function (t) { (byVerse[t.verse] = byVerse[t.verse] || []).push(t); });
    return Object.keys(byVerse).map(Number).sort(function (a, b) { return a - b; })
      .map(function (v) { return { verse: v, tips: byVerse[v] }; });
  }
  function clamp(n) { return Math.max(0, Math.min(100, n)); }
  function el(tag, className) {
    var n = document.createElement(tag);
    if (className) n.className = className;
    return n;
  }
  function button(className, label) {
    var b = el("button", className); b.type = "button";
    if (label) b.textContent = label;
    return b;
  }
  function esc(s) { var d = document.createElement("div"); d.textContent = s; return d.innerHTML; }
  function debounce(fn, ms) {
    var t; return function () { clearTimeout(t); t = setTimeout(fn, ms); };
  }

  global.SadaResults = { render: render };
})(window);
