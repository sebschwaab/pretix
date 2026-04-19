/**
 * pretix-signature-field – vanilla JS signature pad
 *
 * For each .signature-pad-wrapper element on the page:
 *   - wires up the <canvas> to capture mouse/touch drawing
 *   - serialises the drawing to a PNG data-URL and stores it in the
 *     associated hidden <input>
 *   - restores a previous signature from the hidden input on page load
 *   - handles the "Clear" button
 *
 * No external dependencies required.
 */
(function () {
    'use strict';

    /**
     * Initialise one signature pad.
     * @param {HTMLElement} wrapper - .signature-pad-wrapper element
     */
    function initPad(wrapper) {
        var inputId = wrapper.getAttribute('data-signature-input');
        var hiddenInput = document.getElementById(inputId);
        var canvas = wrapper.querySelector('.signature-pad-canvas');
        var clearBtn = wrapper.querySelector('.signature-pad-clear');

        if (!hiddenInput || !canvas) {
            return;
        }

        var ctx = canvas.getContext('2d');
        var drawing = false;
        var lastX = 0;
        var lastY = 0;
        var hasMark = false; // track whether anything has been drawn

        // ── Canvas setup ────────────────────────────────────────────────────

        function resizeCanvas() {
            // Preserve any existing content across resize
            var data = hasMark ? canvas.toDataURL('image/png') : null;

            // Physical pixels (accounts for device pixel ratio)
            var dpr = window.devicePixelRatio || 1;
            var rect = canvas.getBoundingClientRect();
            canvas.width = Math.round(rect.width * dpr);
            canvas.height = Math.round(rect.height * dpr);
            ctx.scale(dpr, dpr);

            ctx.strokeStyle = '#1a1a1a';
            ctx.lineWidth = 2;
            ctx.lineCap = 'round';
            ctx.lineJoin = 'round';

            if (data) {
                var img = new Image();
                img.onload = function () { ctx.drawImage(img, 0, 0, rect.width, rect.height); };
                img.src = data;
            }
        }

        resizeCanvas();

        // Restore a previously saved signature
        if (hiddenInput.value) {
            var stored = hiddenInput.value;
            var restoreImg = new Image();
            restoreImg.onload = function () {
                var rect = canvas.getBoundingClientRect();
                ctx.drawImage(restoreImg, 0, 0, rect.width, rect.height);
                hasMark = true;
            };
            restoreImg.src = stored;
        }

        // ── Coordinate helpers ───────────────────────────────────────────────

        function getPos(e) {
            var rect = canvas.getBoundingClientRect();
            if (e.touches && e.touches.length > 0) {
                return {
                    x: e.touches[0].clientX - rect.left,
                    y: e.touches[0].clientY - rect.top,
                };
            }
            return {
                x: e.clientX - rect.left,
                y: e.clientY - rect.top,
            };
        }

        // ── Drawing ──────────────────────────────────────────────────────────

        function onStart(e) {
            e.preventDefault();
            drawing = true;
            var pos = getPos(e);
            lastX = pos.x;
            lastY = pos.y;

            // Draw a dot for a simple tap/click without movement
            ctx.beginPath();
            ctx.arc(lastX, lastY, ctx.lineWidth / 2, 0, Math.PI * 2);
            ctx.fillStyle = ctx.strokeStyle;
            ctx.fill();
            hasMark = true;
            hiddenInput.value = canvas.toDataURL('image/png');
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
            hasMark = true;
        }

        function onEnd(e) {
            if (!drawing) { return; }
            drawing = false;
            if (hasMark) {
                hiddenInput.value = canvas.toDataURL('image/png');
            }
        }

        // Mouse events
        canvas.addEventListener('mousedown', onStart);
        canvas.addEventListener('mousemove', onMove);
        canvas.addEventListener('mouseup', onEnd);
        canvas.addEventListener('mouseleave', onEnd);

        // Touch events (passive: false so we can preventDefault to stop scrolling)
        canvas.addEventListener('touchstart', onStart, { passive: false });
        canvas.addEventListener('touchmove', onMove, { passive: false });
        canvas.addEventListener('touchend', onEnd);
        canvas.addEventListener('touchcancel', onEnd);

        // ── Clear button ─────────────────────────────────────────────────────

        if (clearBtn) {
            clearBtn.addEventListener('click', function () {
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                hiddenInput.value = '';
                hasMark = false;
            });
        }

        // Re-size if the container changes width (e.g. responsive layout shift)
        if (typeof ResizeObserver !== 'undefined') {
            new ResizeObserver(function () {
                resizeCanvas();
            }).observe(wrapper);
        }
    }

    // ── Bootstrap ────────────────────────────────────────────────────────────

    function initAll() {
        document.querySelectorAll('.signature-pad-wrapper').forEach(initPad);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAll);
    } else {
        initAll();
    }
}());
