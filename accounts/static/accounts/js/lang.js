/**
 * lang.js — JoeLinkAI shared language switcher
 *
 * Targets ONLY elements with class="lang-text" + data-lang="en|fr|ar".
 * Never touches <html>, <body>, or any element that merely carries a
 * semantic lang= attribute.
 */
(function () {
  "use strict";

  function applyLang(lang) {
    // 1. Persist
    localStorage.setItem("jla-lang", lang);

    // 2. Toggle translation spans — class-based selector ONLY
    document.querySelectorAll(".lang-text").forEach(function (el) {
      el.style.display = (el.dataset.lang === lang) ? "" : "none";
    });

    // 3. Update document language + direction
    document.documentElement.lang = lang;
    document.documentElement.dir = (lang === "ar") ? "rtl" : "ltr";

    // 4. Update active state on switcher buttons
    document.querySelectorAll(".lang-btn").forEach(function (b) {
      b.classList.toggle("active", b.dataset.lang === lang);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var savedLang = localStorage.getItem("jla-lang") || "en";
    applyLang(savedLang);

    document.querySelectorAll(".lang-btn").forEach(function (b) {
      b.addEventListener("click", function () {
        applyLang(b.dataset.lang);
      });
    });
  });
})();