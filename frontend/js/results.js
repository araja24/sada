/* Placeholder — the real results page lands in issue #10.
   Exposes SadaResults.render(container, attempt, opts). */
(function (global) {
  "use strict";
  global.SadaResults = {
    render: function (container, attempt, opts) {
      container.innerHTML =
        "<p>Overall score: <strong>" + attempt.overall_score + "</strong> — " +
        attempt.label + "</p><p class='muted'>Full results view coming in issue #10.</p>";
      var again = document.createElement("button");
      again.className = "btn btn-primary";
      again.textContent = "Try again";
      again.addEventListener("click", opts.onTryAgain);
      container.appendChild(again);
    },
  };
})(window);
