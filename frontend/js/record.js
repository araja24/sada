/* Recording step (PRD §4 steps 5-6): mic capture with a live timer and a
   visible 3:00 cap, playback + re-record, then submit.

   SadaRecord.mount(container, { reciterName, startVerse, endVerse, onSubmit })
   — onSubmit(blob) is called with the recorded audio when the user submits. */
(function (global) {
  "use strict";

  var CAP_SECONDS = 180; // PRD: hard 3:00 cap

  function mount(container, opts) {
    var session = {
      stream: null,
      recorder: null,
      chunks: [],
      blob: null,
      objectUrl: null,
      startedAt: 0,
      tick: null,
    };

    container.innerHTML = "";
    var root = el("div", "recorder");
    container.appendChild(root);

    var intro = el("p", "muted");
    intro.textContent =
      "Recite verses " + opts.startVerse + "–" + opts.endVerse +
      " in one take, imitating " + opts.reciterName +
      ". Recording stops automatically at 3:00.";
    root.appendChild(intro);

    var timer = el("div", "rec-timer");
    timer.textContent = "0:00";
    timer.setAttribute("aria-live", "off");
    root.appendChild(timer);

    var cap = el("div", "rec-cap muted");
    cap.textContent = "of 3:00 max";
    root.appendChild(cap);

    var controls = el("div", "rec-controls");
    root.appendChild(controls);

    var startBtn = button("btn btn-primary", "● Start recording");
    var stopBtn = button("btn btn-quiet", "■ Stop");
    var reRecordBtn = button("btn btn-quiet", "Re-record");
    var submitBtn = button("btn btn-primary", "Submit for analysis");
    var preview = el("audio", "rec-preview");
    preview.controls = true;

    controls.appendChild(startBtn);

    startBtn.addEventListener("click", startRecording);
    stopBtn.addEventListener("click", function () { stopRecording(); });
    reRecordBtn.addEventListener("click", resetToStart);
    submitBtn.addEventListener("click", function () {
      if (!session.blob) return;
      submitBtn.disabled = true;
      submitBtn.textContent = "Submitting…";
      opts.onSubmit(session.blob);
    });

    function setControls(nodes) {
      controls.innerHTML = "";
      nodes.forEach(function (n) { controls.appendChild(n); });
    }

    function startRecording() {
      clearFlowError();
      if (!navigator.mediaDevices || !window.MediaRecorder) {
        return flowError("This browser can't record audio. Try a recent Chrome, Firefox, or Safari.");
      }
      startBtn.disabled = true;
      navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
        session.stream = stream;
        session.chunks = [];
        session.recorder = new MediaRecorder(stream);
        session.recorder.addEventListener("dataavailable", function (e) {
          if (e.data && e.data.size) session.chunks.push(e.data);
        });
        session.recorder.addEventListener("stop", onRecorderStop);
        session.recorder.start();
        session.startedAt = Date.now();
        session.tick = setInterval(updateTimer, 200);
        timer.classList.add("live");
        setControls([stopBtn]);
      }).catch(function () {
        startBtn.disabled = false;
        flowError("We need microphone access to record. Enable it in your browser settings and try again.");
      });
    }

    function updateTimer() {
      var secs = (Date.now() - session.startedAt) / 1000;
      timer.textContent = fmt(secs);
      if (secs >= CAP_SECONDS) stopRecording();
    }

    function stopRecording() {
      if (session.recorder && session.recorder.state !== "inactive") {
        session.recorder.stop();
      }
      clearInterval(session.tick);
      timer.classList.remove("live");
    }

    function onRecorderStop() {
      stopTracks();
      var type = session.recorder && session.recorder.mimeType ? session.recorder.mimeType : "audio/webm";
      session.blob = new Blob(session.chunks, { type: type });
      if (session.objectUrl) URL.revokeObjectURL(session.objectUrl);
      session.objectUrl = URL.createObjectURL(session.blob);
      preview.src = session.objectUrl;

      var elapsed = fmt((Date.now() - session.startedAt) / 1000);
      timer.textContent = elapsed;
      setControls([preview, reRecordBtn, submitBtn]);
      submitBtn.disabled = false;
      submitBtn.textContent = "Submit for analysis";
    }

    function resetToStart() {
      clearFlowError();
      session.blob = null;
      session.chunks = [];
      if (session.objectUrl) { URL.revokeObjectURL(session.objectUrl); session.objectUrl = null; }
      timer.textContent = "0:00";
      startBtn.disabled = false;
      setControls([startBtn]);
    }

    function stopTracks() {
      if (session.stream) {
        session.stream.getTracks().forEach(function (t) { t.stop(); });
        session.stream = null;
      }
    }
  }

  // --- helpers ---------------------------------------------------

  function fmt(totalSeconds) {
    var s = Math.max(0, Math.floor(totalSeconds));
    return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
  }
  function el(tag, className) {
    var n = document.createElement(tag);
    if (className) n.className = className;
    return n;
  }
  function button(className, label) {
    var b = el("button", className);
    b.type = "button";
    b.textContent = label;
    return b;
  }
  function flowError(msg) {
    if (global.SadaFlow) global.SadaFlow.showError({ message: msg });
  }
  function clearFlowError() {
    if (global.SadaFlow) global.SadaFlow.clearError();
  }

  global.SadaRecord = { mount: mount, CAP_SECONDS: CAP_SECONDS };
})(window);
