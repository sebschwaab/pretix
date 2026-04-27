/* pretix-modern-theme — modern.js
 * Dark mode toggle + UI enhancements.
 * NOTE: dark-mode init is done inline in <head> (see base.html) to avoid FOUC. */
(function () {
  'use strict';

  /* ── Dark mode toggle ────────────────────────────────────────────────── */
  var STORAGE_KEY = 'mt-theme';

  function getTheme() {
    return localStorage.getItem(STORAGE_KEY) ||
      (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  }

  function applyTheme(t) {
    document.documentElement.setAttribute('data-theme', t);
    localStorage.setItem(STORAGE_KEY, t);
    var btn = document.getElementById('mt-theme-toggle');
    if (btn) {
      btn.setAttribute('aria-pressed', t === 'dark' ? 'true' : 'false');
      btn.setAttribute('data-label', t === 'dark' ? 'Mode clair' : 'Mode sombre');
      btn.querySelector('.mt-icon-sun')  && (btn.querySelector('.mt-icon-sun').style.display  = t === 'dark' ? '' : 'none');
      btn.querySelector('.mt-icon-moon') && (btn.querySelector('.mt-icon-moon').style.display = t === 'dark' ? 'none' : '');
    }
  }

  function toggleTheme() {
    applyTheme(getTheme() === 'dark' ? 'light' : 'dark');
  }

  /* ── Qty stepper animation ───────────────────────────────────────────── */
  function animateSteppers() {
    document.querySelectorAll('.input-item-count').forEach(function (input) {
      if (input.dataset.mtWired) return;
      input.dataset.mtWired = '1';
      input.addEventListener('change', function () {
        var val = parseInt(input.value, 10) || 0;
        var wrapper = input.closest('.input-item-count-group');
        if (wrapper) {
          wrapper.classList.toggle('mt-has-value', val > 0);
        }
      });
      /* Trigger initial state */
      var event = new Event('change');
      input.dispatchEvent(event);
    });
  }

  /* ── Fade-in on scroll (Intersection Observer) ───────────────────────── */
  function initFadeIn() {
    if (!('IntersectionObserver' in window)) return;
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) {
          e.target.classList.add('mt-visible');
          io.unobserve(e.target);
        }
      });
    }, { threshold: 0.08 });

    document.querySelectorAll('.mt-fadein').forEach(function (el) {
      io.observe(el);
    });
  }

  /* ── Smooth cart count badge ─────────────────────────────────────────── */
  function updateCartBadge() {
    var badge = document.getElementById('mt-cart-count');
    if (!badge) return;
    var inputs = document.querySelectorAll('.input-item-count');
    var total = 0;
    inputs.forEach(function (i) { total += parseInt(i.value, 10) || 0; });
    badge.textContent = total > 0 ? total : '';
    badge.style.display = total > 0 ? '' : 'none';
  }

  /* ── Burger menu ─────────────────────────────────────────────────────── */
  function initBurger() {
    var burger = document.getElementById('mt-burger');
    var menu   = document.getElementById('mt-nav-actions');
    if (!burger || !menu) return;

    burger.addEventListener('click', function (e) {
      e.stopPropagation();
      var open = menu.classList.toggle('open');
      burger.setAttribute('aria-expanded', String(open));
    });

    document.addEventListener('click', function (e) {
      if (menu.classList.contains('open') && !menu.contains(e.target) && !burger.contains(e.target)) {
        menu.classList.remove('open');
        burger.setAttribute('aria-expanded', 'false');
      }
    });
  }

  /* ── Bootstrap ───────────────────────────────────────────────────────── */
  function init() {
    /* Theme toggle button */
    var btn = document.getElementById('mt-theme-toggle');
    if (btn) btn.addEventListener('click', toggleTheme);

    initBurger();

    /* Apply correct icon state now */
    applyTheme(getTheme());

    animateSteppers();
    initFadeIn();

    /* Re-run on qty changes */
    document.addEventListener('change', function (e) {
      if (e.target && e.target.classList.contains('input-item-count')) {
        updateCartBadge();
        var wrapper = e.target.closest('.input-item-count-group');
        if (wrapper) wrapper.classList.toggle('mt-has-value', parseInt(e.target.value, 10) > 0);
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  /* jQuery path (Pretix loads jQuery, some pages build DOM after DOMContentLoaded) */
  if (typeof window.jQuery !== 'undefined') {
    window.jQuery(document).ready(function () {
      animateSteppers();
      updateCartBadge();
    });
  }
}());
