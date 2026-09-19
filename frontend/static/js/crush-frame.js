(function () {
    var DEFAULT_W = 1920;
    var DEFAULT_H = 1080;
    var raf = 0;

    function viewportSize() {
        var vv = window.visualViewport;
        if (vv && vv.width && vv.height) {
            return { w: vv.width, h: vv.height };
        }
        return {
            w: window.innerWidth || document.documentElement.clientWidth || DEFAULT_W,
            h: window.innerHeight || document.documentElement.clientHeight || DEFAULT_H,
        };
    }

    function ensureSpacer(frame) {
        var parent = frame.parentNode;
        if (!parent) return null;
        var spacer = parent.querySelector(".crush-frame-spacer");
        if (!spacer) {
            spacer = document.createElement("div");
            spacer.className = "crush-frame-spacer";
            spacer.setAttribute("aria-hidden", "true");
            parent.appendChild(spacer);
        }
        return spacer;
    }

    function fit() {
        raf = 0;
        var frame = document.querySelector(".crush-frame");
        if (!frame) return;

        var FRAME_W = parseFloat(frame.getAttribute("data-frame-w")) || DEFAULT_W;
        var FRAME_H = parseFloat(frame.getAttribute("data-frame-h")) || DEFAULT_H;
        var mode = frame.getAttribute("data-frame-fit") || "contain";

        frame.style.width = FRAME_W + "px";
        frame.style.height = FRAME_H + "px";

        var vp = viewportSize();
        var s;
        var x;
        var y;

        if (mode === "width") {
            s = vp.w / FRAME_W;
            if (!isFinite(s) || s <= 0) s = 1;
            x = 0;
            y = 0;
            var spacer = ensureSpacer(frame);
            if (spacer) {
                spacer.style.width = "1px";
                spacer.style.height = Math.ceil(FRAME_H * s) + "px";
            }
        } else {
            s = Math.min(vp.w / FRAME_W, vp.h / FRAME_H);
            if (!isFinite(s) || s <= 0) s = 1;
            x = (vp.w - FRAME_W * s) / 2;
            y = (vp.h - FRAME_H * s) / 2;
            var box = frame.parentNode && frame.parentNode.querySelector(".crush-frame-spacer");
            if (box) {
                box.style.height = "0px";
            }
        }

        var t = "translate(" + x + "px," + y + "px) scale(" + s + ")";
        frame.style.webkitTransform = t;
        frame.style.transform = t;
        document.documentElement.style.setProperty("--crush-frame-scale", String(s));
        document.documentElement.style.setProperty("--crush-frame-x", x + "px");
        document.documentElement.style.setProperty("--crush-frame-y", y + "px");
    }

    function scheduleFit() {
        if (raf) return;
        if (window.requestAnimationFrame) {
            raf = window.requestAnimationFrame(fit);
        } else {
            raf = setTimeout(fit, 16);
        }
    }

    window.crushFrameFit = fit;

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", fit);
    } else {
        fit();
    }

    window.addEventListener("resize", scheduleFit);
    window.addEventListener("orientationchange", scheduleFit);
    if (window.visualViewport) {
        window.visualViewport.addEventListener("resize", scheduleFit);
        window.visualViewport.addEventListener("scroll", scheduleFit);
    }
})();
