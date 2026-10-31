/* Kurdish Wiktionary dictionary pages: themes, contents, audio, images, translation search.
   Articles stay readable with scripts off: audio links use sound://, sections use <details>. */
(function () {
  var STORE_THEME = "wk-theme";
  var STORE_LABELS = "wk-labels";
  var THEME_ORDER = ["auto", "light", "dark"];
  var THEME_LABEL = { auto: "Otomatîk", light: "Ronî", dark: "Tarî" };
  var FILTER_ABOVE_ITEMS = 12;

  function read(key) {
    try {
      return window.localStorage.getItem(key);
    } catch (e) {
      return null;
    }
  }

  function write(key, value) {
    try {
      window.localStorage.setItem(key, value);
    } catch (e) {
      /* Some dictionary apps disable storage; the choice then lasts for this page only. */
    }
  }

  function closest(el, selector) {
    while (el && el.nodeType === 1) {
      if (el.matches(selector)) return el;
      el = el.parentElement;
    }
    return null;
  }

  function applyTheme(theme) {
    var root = document.documentElement;
    if (theme === "light" || theme === "dark") root.setAttribute("data-theme", theme);
    else root.removeAttribute("data-theme");
    var buttons = document.querySelectorAll(".wk-theme-btn");
    for (var i = 0; i < buttons.length; i++) {
      buttons[i].textContent = THEME_LABEL[theme] || THEME_LABEL.auto;
      buttons[i].setAttribute("data-mode", theme);
      buttons[i].setAttribute("aria-label", "Rûkar: " + (THEME_LABEL[theme] || THEME_LABEL.auto));
    }
  }

  function currentTheme() {
    return read(STORE_THEME) || document.documentElement.getAttribute("data-theme") || "auto";
  }

  function applyLabels(mode) {
    var articles = document.querySelectorAll(".wk");
    for (var i = 0; i < articles.length; i++) {
      articles[i].classList.toggle("wk--en", mode === "en");
    }
    var buttons = document.querySelectorAll(".wk-labels-btn");
    for (var j = 0; j < buttons.length; j++) {
      buttons[j].textContent = mode === "en" ? "English" : "Kurdî";
    }
  }

  function buildTools(article) {
    var tools = article.querySelector(".wk-tools");
    if (!tools || tools.firstChild) return;
    tools.innerHTML =
      '<button type="button" class="wk-tool wk-labels-btn" title="Sernavên beşan">Kurdî</button>' +
      '<button type="button" class="wk-tool wk-theme-btn" title="Rûkar">Otomatîk</button>';
  }

  function sectionLabel(summary) {
    var ku = summary.querySelector(".wk-sec-ku, .wk-lang-name");
    var en = summary.querySelector(".wk-sec-en");
    return { ku: ku ? ku.textContent : "", en: en ? en.textContent : ku ? ku.textContent : "" };
  }

  function buildNav(article) {
    var nav = article.querySelector(".wk-nav");
    if (!nav || nav.firstChild) return;
    var targets = article.querySelectorAll(".wk-lang, .wk-sec");
    if (targets.length < 3) {
      nav.style.display = "none";
      article.classList.add("wk--no-nav");
      return;
    }
    var title = document.createElement("p");
    title.className = "wk-nav-title";
    title.textContent = "Naverok";
    nav.appendChild(title);
    var list = document.createElement("ul");
    list.className = "wk-nav-list";
    var links = [];
    for (var i = 0; i < targets.length; i++) {
      var target = targets[i];
      var summary = target.querySelector("summary");
      if (!summary || !target.id) continue;
      var label = sectionLabel(summary);
      var item = document.createElement("li");
      item.className = target.classList.contains("wk-lang") ? "wk-nav-lang" : "wk-nav-sec";
      var link = document.createElement("a");
      link.href = "#" + target.id;
      link.setAttribute("data-target", target.id);
      link.innerHTML =
        '<span class="wk-sec-ku"></span><span class="wk-sec-en"></span>';
      link.children[0].textContent = label.ku;
      link.children[1].textContent = label.en;
      item.appendChild(link);
      list.appendChild(item);
      links.push(link);
    }
    nav.appendChild(list);
    if (typeof IntersectionObserver === "undefined") return;
    var observer = new IntersectionObserver(
      function (entries) {
        for (var n = 0; n < entries.length; n++) {
          if (!entries[n].isIntersecting) continue;
          var id = entries[n].target.id;
          for (var m = 0; m < links.length; m++) {
            var on = links[m].getAttribute("data-target") === id;
            links[m].classList.toggle("is-active", on);
            if (on && nav.scrollWidth > nav.clientWidth && links[m].scrollIntoView) {
              list.scrollLeft = links[m].parentElement.offsetLeft - 16;
            }
          }
        }
      },
      { rootMargin: "-15% 0px -70% 0px" }
    );
    // Sections only: a language fold contains its sections, so both would light up at once.
    var observed = article.querySelectorAll(".wk-sec");
    for (var t = 0; t < observed.length; t++) observer.observe(observed[t]);
  }

  function openAncestors(el) {
    while (el) {
      if (el.tagName === "DETAILS") el.open = true;
      el = el.parentElement;
    }
  }

  function buildFilters(article) {
    var sections = article.querySelectorAll(".wk-sec--translations");
    for (var i = 0; i < sections.length; i++) {
      var body = sections[i].querySelector(".wk-sec-body");
      if (!body || body.querySelector(".wk-filter")) continue;
      if (body.querySelectorAll("li").length <= FILTER_ABOVE_ITEMS) continue;
      var input = document.createElement("input");
      input.type = "search";
      input.className = "wk-filter";
      input.placeholder = "Li zimanekî bigere…";
      input.setAttribute("aria-label", "Li zimanekî bigere");
      body.insertBefore(input, body.firstChild);
    }
  }

  var player = null;
  var playingCard = null;

  function stopPlaying() {
    if (playingCard) playingCard.classList.remove("is-playing");
    playingCard = null;
    if (player) player.pause();
  }

  function playCard(card) {
    var source = card.getAttribute("data-audio");
    if (!source) return false;
    if (playingCard === card) {
      stopPlaying();
      return true;
    }
    stopPlaying();
    player = new Audio(source);
    playingCard = card;
    card.classList.add("is-playing");
    player.addEventListener("ended", stopPlaying);
    var started = player.play();
    if (started && started.catch) {
      started.catch(function () {
        // The app can't load the file itself: hand over to its sound:// handler.
        card.classList.remove("is-playing");
        playingCard = null;
        window.location.href = card.getAttribute("href");
      });
    }
    return true;
  }

  function closeLightbox() {
    var box = document.querySelector(".wk-lightbox");
    if (box) box.parentNode.removeChild(box);
  }

  function openLightbox(image) {
    closeLightbox();
    var box = document.createElement("div");
    box.className = "wk-lightbox";
    box.setAttribute("role", "dialog");
    var close = document.createElement("button");
    close.type = "button";
    close.className = "wk-lightbox-close";
    close.setAttribute("aria-label", "Bigire");
    close.textContent = "×";
    var large = document.createElement("img");
    large.src = image.getAttribute("src");
    large.alt = image.getAttribute("alt") || "";
    box.appendChild(close);
    box.appendChild(large);
    if (large.alt) {
      var caption = document.createElement("p");
      caption.textContent = large.alt;
      box.appendChild(caption);
    }
    document.body.appendChild(box);
    close.focus();
  }

  function onClick(event) {
    var target = event.target;
    var card = closest(target, ".wk-voice");
    if (card && playCard(card)) {
      event.preventDefault();
      return;
    }
    if (closest(target, ".wk-labels-btn")) {
      var next = closest(target, ".wk").classList.contains("wk--en") ? "ku" : "en";
      write(STORE_LABELS, next);
      applyLabels(next);
      return;
    }
    if (closest(target, ".wk-theme-btn")) {
      var index = THEME_ORDER.indexOf(currentTheme());
      var theme = THEME_ORDER[(index + 1) % THEME_ORDER.length];
      write(STORE_THEME, theme);
      applyTheme(theme);
      return;
    }
    var navLink = closest(target, ".wk-nav a");
    if (navLink) {
      var section = document.getElementById(navLink.getAttribute("data-target"));
      if (section) {
        event.preventDefault();
        openAncestors(section);
        section.scrollIntoView({ behavior: "smooth", block: "start" });
      }
      return;
    }
    if (closest(target, ".wk-lightbox-close") || target.className === "wk-lightbox") {
      closeLightbox();
      return;
    }
    var figureImage = target.tagName === "IMG" && closest(target, ".wk-fig");
    if (figureImage) openLightbox(target);
  }

  function onInput(event) {
    if (!event.target.classList || !event.target.classList.contains("wk-filter")) return;
    var query = event.target.value.toLocaleLowerCase();
    var items = event.target.parentElement.querySelectorAll("li");
    for (var i = 0; i < items.length; i++) {
      var text = items[i].textContent.toLocaleLowerCase();
      items[i].style.display = !query || text.indexOf(query) >= 0 ? "" : "none";
    }
  }

  function onKey(event) {
    if (event.key === "Escape") closeLightbox();
  }

  function init() {
    var articles = document.querySelectorAll(".wk");
    for (var i = 0; i < articles.length; i++) {
      buildTools(articles[i]);
      buildNav(articles[i]);
      buildFilters(articles[i]);
    }
    applyTheme(currentTheme());
    applyLabels(read(STORE_LABELS) === "en" ? "en" : "ku");
    if (window.__wkBound) return;
    window.__wkBound = true;
    document.addEventListener("click", onClick);
    document.addEventListener("input", onInput);
    document.addEventListener("keydown", onKey);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
