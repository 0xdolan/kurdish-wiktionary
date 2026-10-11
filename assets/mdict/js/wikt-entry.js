(function () {
  function closest(el, sel) {
    while (el && el.nodeType === 1) {
      if (el.matches(sel)) return el;
      el = el.parentElement;
    }
    return null;
  }

  function setActiveTocLink(entry, activeId) {
    entry.querySelectorAll(".wikt-toc-link").forEach(function (a) {
      var on = a.getAttribute("data-target-id") === activeId;
      a.classList.toggle("wikt-toc-link--active", on);
      if (on) a.setAttribute("aria-current", "location");
      else a.removeAttribute("aria-current");
    });
  }

  function bindToc(entry) {
    var list = entry.querySelector(".wikt-toc-list");
    if (!list) return;

    list.innerHTML = "";
    var items = [];

    var head = entry.querySelector("#wikt-sec-head");
    if (head) {
      var hw = entry.querySelector(".wikt-headword");
      items.push({
        id: "wikt-sec-head",
        el: head,
        labelKu: hw ? hw.textContent : "Sernav",
        labelEn: "Headword",
        openOnNav: false,
      });
    }

    entry.querySelectorAll(".wikt-fold[data-section-key]").forEach(function (details) {
      var id = details.id;
      if (!id) return;
      var summary = details.querySelector("summary.wikt-section");
      if (!summary) return;
      var ku = summary.querySelector(".wikt-section-ku");
      var en = summary.querySelector(".wikt-section-en");
      items.push({
        id: id,
        el: details,
        labelKu: ku ? ku.textContent : details.getAttribute("data-section-key"),
        labelEn: en ? en.textContent : details.getAttribute("data-section-key"),
        openOnNav: true,
      });
    });

    items.forEach(function (item) {
      var li = document.createElement("li");
      var a = document.createElement("a");
      a.href = "#" + item.id;
      a.className = "wikt-toc-link";
      if (item.id === "wikt-sec-head") {
        a.classList.add("wikt-toc-link--head");
      }
      a.setAttribute("data-target-id", item.id);
      var spanKu = document.createElement("span");
      spanKu.className = "wikt-toc-label-ku";
      spanKu.textContent = item.labelKu || "";
      var spanEn = document.createElement("span");
      spanEn.className = "wikt-toc-label-en";
      spanEn.textContent = item.labelEn || "";
      a.appendChild(spanKu);
      a.appendChild(spanEn);
      a.addEventListener("click", function (ev) {
        ev.preventDefault();
        if (item.openOnNav && item.el && item.el.tagName === "DETAILS") {
          item.el.open = true;
        }
        item.el.scrollIntoView({ behavior: "smooth", block: "start" });
        setActiveTocLink(entry, item.id);
      });
      li.appendChild(a);
      list.appendChild(li);
    });

    if (typeof IntersectionObserver !== "undefined" && items.length) {
      var observer = new IntersectionObserver(
        function (entries) {
          var visible = entries
            .filter(function (e) {
              return e.isIntersecting;
            })
            .sort(function (a, b) {
              return a.boundingClientRect.top - b.boundingClientRect.top;
            });
          if (visible.length) {
            setActiveTocLink(entry, visible[0].target.id);
          }
        },
        { root: null, rootMargin: "-20% 0px -55% 0px", threshold: 0 }
      );
      items.forEach(function (item) {
        if (item.el) observer.observe(item.el);
      });
    }
  }

  function bindLangToggle() {
    document.addEventListener("change", function (ev) {
      var target = ev.target;
      if (!target || target.id !== "wikt-en-labels") return;
      var root = closest(target, ".wikt-entry") || document.body;
      root.classList.toggle("wikt-show-en", target.checked);
    });
  }

  function initEntry(entry) {
    bindToc(entry);
  }

  function init() {
    bindLangToggle();
    document.querySelectorAll(".wikt-entry").forEach(initEntry);
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
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
