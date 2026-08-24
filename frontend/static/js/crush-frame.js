(function () {
    var FRAME_W = 1920;
    var FRAME_H = 1080;

    function fit() {
        var frame = document.querySelector(".crush-frame");
        if (!frame) return;
        
        var s = Math.min(window.innerWidth / FRAME_W, window.innerHeight / FRAME_H);
        var x = (window.innerWidth - FRAME_W * s) / 2;
        var y = (window.innerHeight - FRAME_H * s) / 2;
        frame.style.transform = "translate(" + x + "px," + y + "px) scale(" + s + ")";
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", fit);
    } else {
        fit();
    }
    window.addEventListener("resize", fit);
    window.addEventListener("orientationchange", fit);
})();
