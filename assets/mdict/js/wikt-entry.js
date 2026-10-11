(function () {
  function closest(el, sel) {
    while (el && el.nodeType === 1) {
      if (el.matches(sel)) return el;
      el = el.parentElement;
    }
    return null;
  }

  function bindLangToggle() {
    document.addEventListener("change", function (ev) {
      var target = ev.target;
      if (!target || target.id !== "wikt-en-labels") return;
      var root = closest(target, ".wikt-entry") || document.body;
      root.classList.toggle("wikt-show-en", target.checked);
    });
  }

  document.addEventListener("click", function (ev) {
    var btn = closest(ev.target, ".wikt-audio-btn");
    if (btn) {
      var src = btn.getAttribute("data-audio-src");
      if (!src) return;
      var audio = btn._wiktAudio || new Audio(src);
      btn._wiktAudio = audio;
      audio.play();
      return;
    }

    var thumb = closest(ev.target, ".wikt-thumb-open");
    if (thumb) {
      var full = thumb.getAttribute("data-full-src");
      if (!full) return;
      var overlay = document.createElement("div");
      overlay.className = "wikt-lightbox";
      overlay.innerHTML =
        '<button type="button" class="wikt-lightbox-close" aria-label="Close">&times;</button>' +
        '<img class="wikt-lightbox-img" src="' +
        full.replace(/"/g, "&quot;") +
        '" alt="" />';
      document.body.appendChild(overlay);
      overlay.addEventListener("click", function (e) {
        if (
          e.target === overlay ||
          e.target.classList.contains("wikt-lightbox-close")
        ) {
          overlay.remove();
        }
      });
    }
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindLangToggle);
  } else {
    bindLangToggle();
  }
})();
