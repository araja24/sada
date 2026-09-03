/* Placeholder — the real recording UI lands in issue #9.
   Exposes SadaRecord.mount(container, opts) so the flow controller (app.js)
   has a stable contract to build against now. */
(function (global) {
  "use strict";
  global.SadaRecord = {
    mount: function (container, opts) {
      container.innerHTML =
        "<p class='muted'>Recording for verses " + opts.startVerse + "–" +
        opts.endVerse + " (" + opts.reciterName + ") — coming in issue #9.</p>";
    },
  };
})(window);
