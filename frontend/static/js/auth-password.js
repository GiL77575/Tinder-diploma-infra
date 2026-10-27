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

    function syncEyeState(btn, input) {
        var passwordHidden = input.type === "password";
        btn.classList.toggle("is-password-hidden", passwordHidden);
        btn.setAttribute("aria-label", passwordHidden ? "Показати пароль" : "Сховати пароль");
    }

    document.querySelectorAll(".toggle-password").forEach(function (btn) {
        var input = document.getElementById(btn.getAttribute("data-target"));
        if (input) syncEyeState(btn, input);

        btn.addEventListener("click", function () {
            var field = document.getElementById(btn.getAttribute("data-target"));
            if (!field) return;
            field.type = field.type === "password" ? "text" : "password";
            syncEyeState(btn, field);
        });
    });
})();
