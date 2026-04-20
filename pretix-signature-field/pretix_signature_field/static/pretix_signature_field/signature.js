/**
 * pretix-signature-field – signature pad
 *
 * Initialisation strategy (double-hook, guard against double-init):
 *   1. Native DOMContentLoaded / immediate if DOM already ready.
 *   2. jQuery $(document).ready – Pretix loads jQuery and some pages inject
 *      form HTML via jQuery AJAX after the native ready event has fired.
 *
 * Canvas sizing fix:
 *   getBoundingClientRect() returns 0 when the element is not yet painted
 *   (e.g. script runs before first layout pass).  We use offsetWidth /
 *   offsetHeight as a reliable fallback, then re-size on the first
 *   ResizeObserver tick so HiDPI and responsive layouts are handled cleanly.
 */
(function () {
    'use strict';

    /* ── Placeholder text drawn on an empty canvas ── */
    var PLACEHOLDER_COLOR = '#bbb';
    var PLACEHOLDER_FONT  = 'italic 14px sans-serif';
    var PLACEHOLDER_TEXT  = '✏ Signez ici';   // overridden by data-placeholder if set

    /* ── One-time init per wrapper ──────────────────────────────────────────── */

    function initPad(wrapper) {
        // Guard: skip if already initialised
        if (wrapper.hasAttribute('data-sig-ready')) { return; }
        wrapper.setAttribute('data-sig-ready', '1');

        var inputId     = wrapper.getAttribute('data-signature-input');
        var previewUrl  = wrapper.getAttribute('data-signature-preview') || '';
        var hiddenInput = document.getElementById(inputId);
        var canvas      = wrapper.querySelector('.signature-pad-canvas');
        var clearBtn    = wrapper.querySelector('.signature-pad-clear');

        if (!hiddenInput || !canvas) { return; }

        var ctx      = canvas.getContext('2d');
        var drawing  = false;
        var lastX    = 0;
        var lastY    = 0;
        var hasMark  = false;
        var placeholder = wrapper.getAttribute('data-placeholder') || PLACEHOLDER_TEXT;

        /* ── Canvas buffer sizing ────────────────────────────────────────────
         * canvas.width / canvas.height  = buffer resolution (physical pixels)
         * CSS width / height            = display size  (set in .css file)
         *
         * offsetWidth is available even before getBoundingClientRect is stable,
         * as long as the element is in the document and not display:none.
         * Fall back to 600 × 200 if for some reason layout is still 0.
         */
        function getDisplaySize() {
            return {
                w: canvas.offsetWidth  || canvas.parentElement.offsetWidth  || 600,
                h: canvas.offsetHeight || 200,
            };
        }

        function applyContextStyles() {
            ctx.strokeStyle = '#1a1a1a';
            ctx.lineWidth   = 2;
            ctx.lineCap     = 'round';
            ctx.lineJoin    = 'round';
            ctx.fillStyle   = '#1a1a1a';
        }

        function drawPlaceholder() {
            if (hasMark) { return; }
            var size = getDisplaySize();
            ctx.save();
            ctx.font      = PLACEHOLDER_FONT;
            ctx.fillStyle = PLACEHOLDER_COLOR;
            ctx.textAlign = 'center';
            ctx.fillText(placeholder, size.w / 2, size.h / 2 + 5);
            ctx.restore();
        }

        function resizeCanvas(restoreData) {
            var dpr  = window.devicePixelRatio || 1;
            var size = getDisplaySize();

            // Setting width/height resets the context – do it before styling
            canvas.width  = Math.round(size.w * dpr);
            canvas.height = Math.round(size.h * dpr);
            ctx.scale(dpr, dpr);
            applyContextStyles();

            if (restoreData) {
                var img = new Image();
                img.onload = function () {
                    ctx.drawImage(img, 0, 0, size.w, size.h);
                };
                img.src = restoreData;
            } else {
                drawPlaceholder();
            }
        }

        // Initial sizing – defer one animation frame so CSS layout is settled.
        // Restore order of priority:
        //   1. A data-URL already in the hidden input (draft re-display).
        //   2. data-signature-preview URL pointing to a stored file.
        //   3. Empty canvas with placeholder.
        requestAnimationFrame(function () {
            var restoreUrl = hiddenInput.value || previewUrl || null;
            resizeCanvas(restoreUrl);
            if (restoreUrl) { hasMark = true; }
        });

        /* ── Coordinate helper ───────────────────────────────────────────── */

        function getPos(e) {
            var rect = canvas.getBoundingClientRect();
            var src  = e.touches ? e.touches[0] : e;
            return {
                x: src.clientX - rect.left,
                y: src.clientY - rect.top,
            };
        }

        /* ── Drawing handlers ────────────────────────────────────────────── */

        function onStart(e) {
            e.preventDefault();
            drawing = true;

            // Clear placeholder on first stroke
            if (!hasMark) {
                var size = getDisplaySize();
                ctx.clearRect(0, 0, size.w, size.h);
                applyContextStyles();
            }

            var pos = getPos(e);
            lastX = pos.x;
            lastY = pos.y;

            // Dot for a single tap/click
            ctx.beginPath();
            ctx.arc(lastX, lastY, ctx.lineWidth / 2, 0, Math.PI * 2);
            ctx.fill();
            hasMark = true;
        }

        function onMove(e) {
            if (!drawing) { return; }
            e.preventDefault();
            var pos = getPos(e);
            ctx.beginPath();
            ctx.moveTo(lastX, lastY);
            ctx.lineTo(pos.x, pos.y);
            ctx.stroke();
            lastX = pos.x;
            lastY = pos.y;
        }

        function onEnd() {
            if (!drawing) { return; }
            drawing = false;
            if (hasMark) {
                hiddenInput.value = canvas.toDataURL('image/png');
            }
        }

        /* ── Event listeners ─────────────────────────────────────────────── */

        // Mouse
        canvas.addEventListener('mousedown', onStart);
        canvas.addEventListener('mousemove', onMove);
        canvas.addEventListener('mouseup',   onEnd);
        canvas.addEventListener('mouseleave', onEnd);

        // Touch (passive:false to allow preventDefault and block page scroll)
        canvas.addEventListener('touchstart',  onStart, { passive: false });
        canvas.addEventListener('touchmove',   onMove,  { passive: false });
        canvas.addEventListener('touchend',    onEnd);
        canvas.addEventListener('touchcancel', onEnd);

        /* ── Clear button ────────────────────────────────────────────────── */

        if (clearBtn) {
            clearBtn.addEventListener('click', function () {
                var size = getDisplaySize();
                ctx.clearRect(0, 0, size.w, size.h);
                applyContextStyles();
                hiddenInput.value = '';
                hasMark = false;
                drawPlaceholder();
            });
        }

        /* ── Responsive resize ───────────────────────────────────────────── */

        if (typeof ResizeObserver !== 'undefined') {
            var roTimer;
            new ResizeObserver(function () {
                // Debounce to avoid thrashing during layout animations
                clearTimeout(roTimer);
                roTimer = setTimeout(function () {
                    var saved = hasMark ? canvas.toDataURL('image/png') : null;
                    resizeCanvas(saved);
                }, 100);
            }).observe(wrapper);
        }
    }

    /* ── Scan the page and init every pad found ─────────────────────────────── */

    function initAll() {
        var pads = document.querySelectorAll('.signature-pad-wrapper[data-signature-input]');
        for (var i = 0; i < pads.length; i++) {
            initPad(pads[i]);
        }
    }

    /* ── Bootstrap: native + jQuery ─────────────────────────────────────────── */

    // 1. Native path
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAll);
    } else {
        // DOM already ready (script loaded async / deferred)
        initAll();
    }

    // 2. jQuery path – Pretix uses jQuery; pages built with jQuery AJAX may
    //    inject form HTML after DOMContentLoaded has already fired.
    //    $(document).ready() is safe to call even when the document is already
    //    ready: jQuery fires the callback immediately in that case.
    if (typeof window.jQuery !== 'undefined') {
        window.jQuery(document).ready(initAll);
    } else if (typeof window.$ !== 'undefined' && typeof window.$.fn !== 'undefined') {
        window.$(document).ready(initAll);
    }

}());
