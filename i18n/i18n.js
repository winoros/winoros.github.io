(function(global) {
  "use strict";

  var SUPPORTED = ["zh-CN", "en"];
  var DEFAULT_LOCALE = "en";
  var STORAGE_KEY = "winoros-lang";
  var THEME_STORAGE_KEY = "winoros-theme";

  var store = { "zh-CN": {}, "en": {} };
  var listeners = [];
  var currentLocale = DEFAULT_LOCALE;
  var hasUrlLangParam = false;

  function safeStorageGet(key) {
    try { return global.localStorage ? global.localStorage.getItem(key) : null; }
    catch (_) { return null; }
  }

  function safeStorageSet(key, val) {
    try { if (global.localStorage) global.localStorage.setItem(key, val); }
    catch (_) {}
  }

  function escHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function normalizeLocale(raw) {
    if (!raw || typeof raw !== "string") return null;
    var lower = raw.trim().toLowerCase();
    if (lower.indexOf("zh") === 0) return "zh-CN";
    if (lower.indexOf("en") === 0) return "en";
    return null;
  }

  function deepMerge(target, src) {
    if (!src || typeof src !== "object") return target;
    Object.keys(src).forEach(function(k) {
      var sv = src[k];
      if (sv && typeof sv === "object" && !Array.isArray(sv)) {
        if (!target[k] || typeof target[k] !== "object") target[k] = {};
        deepMerge(target[k], sv);
      } else {
        target[k] = sv;
      }
    });
    return target;
  }

  function lookup(locale, key) {
    var cur = store[locale];
    if (!cur) return undefined;
    var parts = key.split(".");
    for (var i = 0; i < parts.length; i++) {
      if (cur == null || typeof cur !== "object") return undefined;
      cur = cur[parts[i]];
    }
    return cur;
  }

  function resolveRaw(key, locale) {
    var loc = locale || currentLocale;
    var val = lookup(loc, key);
    if (val !== undefined) return val;
    for (var i = 0; i < SUPPORTED.length; i++) {
      if (SUPPORTED[i] !== loc) {
        val = lookup(SUPPORTED[i], key);
        if (val !== undefined) return val;
      }
    }
    return undefined;
  }

  function interpolate(template, params, escapeParams) {
    if (typeof template !== "string") return "";
    if (!params) return template;
    return template.replace(/\{([a-zA-Z0-9_]+)\}/g, function(m, name) {
      if (!Object.prototype.hasOwnProperty.call(params, name)) return m;
      var v = params[name] == null ? "" : String(params[name]);
      return escapeParams ? escHtml(v) : v;
    });
  }

  function detectInitialLocale() {
    try {
      var params = new URLSearchParams(global.location.search || "");
      var qLang = normalizeLocale(params.get("lang"));
      if (qLang) {
        hasUrlLangParam = true;
        return qLang;
      }
    } catch (_) {}

    var saved = normalizeLocale(safeStorageGet(STORAGE_KEY));
    if (saved) return saved;

    try {
      var navList = (global.navigator && global.navigator.languages) || [];
      var primary = navList.length ? navList[0] : (global.navigator && global.navigator.language);
      if (primary && typeof primary === "string") {
        return primary.trim().toLowerCase().indexOf("zh") === 0 ? "zh-CN" : "en";
      }
    } catch (_) {}

    return DEFAULT_LOCALE;
  }

  function syncUrlParam(locale, forceParam) {
    try {
      var proto = global.location && global.location.protocol;
      if (proto !== "http:" && proto !== "https:") return;
      var url = new URL(global.location.href);
      if (forceParam || url.searchParams.has("lang")) {
        url.searchParams.set("lang", locale === "zh-CN" ? "zh" : "en");
        global.history.replaceState(null, "", url.toString());
        hasUrlLangParam = true;
      }
    } catch (_) {}
  }

  function updateKeepLangLinks(root) {
    var scope = root || global.document;
    if (!scope || !scope.querySelectorAll) return;
    var nodes = scope.querySelectorAll("a[data-keep-lang]");
    var shortCode = currentLocale === "zh-CN" ? "zh" : "en";
    for (var i = 0; i < nodes.length; i++) {
      var a = nodes[i];
      var baseHref = a.getAttribute("data-base-href") || a.getAttribute("href");
      if (!a.getAttribute("data-base-href")) a.setAttribute("data-base-href", baseHref);
      if (hasUrlLangParam) {
        var sep = baseHref.indexOf("?") === -1 ? "?" : "&";
        a.setAttribute("href", baseHref + sep + "lang=" + shortCode);
      } else {
        a.setAttribute("href", baseHref);
      }
    }
  }

  function applyDOM(root) {
    var doc = global.document;
    if (!doc) return;
    var scope = root || doc;

    if (scope === doc) {
      doc.documentElement.setAttribute("lang", currentLocale);
      var titleKey = doc.documentElement.getAttribute("data-i18n-title");
      if (titleKey) {
        var ttl = api.t(titleKey);
        if (ttl) doc.title = ttl;
      }
      var metaDesc = doc.querySelector("meta[name=\"description\"][data-i18n-content]");
      if (metaDesc) {
        var desc = api.t(metaDesc.getAttribute("data-i18n-content"));
        if (desc) metaDesc.setAttribute("content", desc);
      }
    }

    var textNodes = scope.querySelectorAll("[data-i18n]");
    for (var i = 0; i < textNodes.length; i++) {
      var el = textNodes[i];
      var val = api.t(el.getAttribute("data-i18n"));
      el.textContent = val;
      if (el.hasAttribute("data-i18n-hide-empty")) {
        el.hidden = !val;
      }
    }

    var htmlNodes = scope.querySelectorAll("[data-i18n-html]");
    for (var j = 0; j < htmlNodes.length; j++) {
      var hel = htmlNodes[j];
      hel.innerHTML = api.tHtml(hel.getAttribute("data-i18n-html"));
    }

    var phNodes = scope.querySelectorAll("[data-i18n-placeholder]");
    for (var k = 0; k < phNodes.length; k++) {
      var pel = phNodes[k];
      pel.setAttribute("placeholder", api.t(pel.getAttribute("data-i18n-placeholder")));
    }

    var ttlNodes = scope.querySelectorAll("[data-i18n-title]");
    for (var m = 0; m < ttlNodes.length; m++) {
      var tel = ttlNodes[m];
      if (tel === doc.documentElement) continue;
      tel.setAttribute("title", api.t(tel.getAttribute("data-i18n-title")));
    }

    var ariaNodes = scope.querySelectorAll("[data-i18n-aria-label]");
    for (var n = 0; n < ariaNodes.length; n++) {
      var ael = ariaNodes[n];
      ael.setAttribute("aria-label", api.t(ael.getAttribute("data-i18n-aria-label")));
    }

    var btns = scope.querySelectorAll("[data-lang-opt]");
    for (var b = 0; b < btns.length; b++) {
      var btn = btns[b];
      var opt = normalizeLocale(btn.getAttribute("data-lang-opt"));
      var isAct = opt === currentLocale;
      btn.classList.toggle("active", isAct);
      btn.setAttribute("aria-pressed", isAct ? "true" : "false");
    }

    updateKeepLangLinks(scope);
  }

  function initTheme(btnId) {
    var doc = global.document;
    if (!doc) return;
    var root = doc.documentElement;
    var saved = safeStorageGet(THEME_STORAGE_KEY);
    if (saved === "light" || saved === "dark") {
      root.setAttribute("data-theme", saved);
    }
    var btn = doc.getElementById(btnId || "themeBtn");
    if (btn && !btn.hasAttribute("data-theme-bound")) {
      btn.setAttribute("data-theme-bound", "1");
      btn.addEventListener("click", function() {
        var cur = root.getAttribute("data-theme");
        var sysDark = false;
        try { sysDark = global.matchMedia("(prefers-color-scheme: dark)").matches; } catch (_) {}
        var next = cur ? (cur === "dark" ? "light" : "dark") : (sysDark ? "light" : "dark");
        root.setAttribute("data-theme", next);
        safeStorageSet(THEME_STORAGE_KEY, next);
      });
    }
  }

  var switcherBound = false;
  function bindSwitcher() {
    var doc = global.document;
    if (!doc || switcherBound) return;
    switcherBound = true;
    doc.addEventListener("click", function(e) {
      var btn = e.target && e.target.closest ? e.target.closest("[data-lang-opt]") : null;
      if (!btn) return;
      var target = normalizeLocale(btn.getAttribute("data-lang-opt"));
      if (target) api.setLocale(target, { persist: true, syncUrl: true });
    });
  }

  var api = {
    SUPPORTED: SUPPORTED,
    escHtml: escHtml,
    extend: function(locale, partial) {
      var norm = normalizeLocale(locale);
      if (!norm) return;
      deepMerge(store[norm], partial);
    },
    getLocale: function() {
      return currentLocale;
    },
    t: function(key, params, locale) {
      var raw = resolveRaw(key, locale);
      if (typeof raw !== "string") return key;
      return interpolate(raw, params, false);
    },
    tHtml: function(key, params, locale) {
      var raw = resolveRaw(key, locale);
      if (typeof raw !== "string") return escHtml(key);
      return interpolate(raw, params, true);
    },
    dict: function(key, locale) {
      return resolveRaw(key, locale);
    },
    setLocale: function(nextRaw, opts) {
      var next = normalizeLocale(nextRaw) || DEFAULT_LOCALE;
      var options = opts || {};
      var changed = next !== currentLocale;
      currentLocale = next;
      if (options.persist !== false) {
        safeStorageSet(STORAGE_KEY, currentLocale);
      }
      if (options.syncUrl) {
        syncUrlParam(currentLocale, true);
      }
      applyDOM();
      if (changed || options.forceNotify) {
        for (var i = 0; i < listeners.length; i++) {
          listeners[i](currentLocale);
        }
      }
    },
    onChange: function(fn) {
      if (typeof fn === "function") listeners.push(fn);
    },
    applyDOM: applyDOM,
    init: function(opts) {
      var options = opts || {};
      currentLocale = detectInitialLocale();
      initTheme(options.themeBtnId || "themeBtn");
      bindSwitcher();
      applyDOM();
      return currentLocale;
    }
  };

  global.SiteI18n = api;
})(window);
