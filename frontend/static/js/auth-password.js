(function () {
    function syncFilledState(input) {
        input.classList.toggle("is-filled", input.value.length > 0);
    }

    document.querySelectorAll(".password-wrapper input").forEach(function (input) {
        syncFilledState(input);
        input.addEventListener("input", function () {
            syncFilledState(input);
        });
    });

    document.querySelectorAll(".toggle-password").forEach(function (btn) {
        btn.addEventListener("click", function () {
            var input = document.getElementById(btn.getAttribute("data-target"));
            if (!input) return;
            var show = input.type === "password";
            input.type = show ? "text" : "password";
            var eye = btn.querySelector(".icon-eye");
            var eyeOff = btn.querySelector(".icon-eye-off");
            if (eye) eye.hidden = show;
            if (eyeOff) eyeOff.hidden = !show;
            btn.setAttribute("aria-label", show ? "Сховати пароль" : "Показати пароль");
        });
    });
})();
