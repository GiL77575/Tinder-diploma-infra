/* crush — головна сторінка: випадкове фото пари в hero-блоці.
   Список фото береться з data-hero-photos (заповнюється в home.html),
   тож при кожному завантаженні/перезавантаженні сторінки показується інше. */
(function () {
    'use strict';

    function initHeroPhoto() {
        var img = document.getElementById('landing-hero-photo');
        if (!img || !img.dataset.heroPhotos) return;

        var photos = img.dataset.heroPhotos.split('|').filter(Boolean);
        if (!photos.length) return;

        var random = photos[Math.floor(Math.random() * photos.length)];
        img.src = random;
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initHeroPhoto);
    } else {
        initHeroPhoto();
    }
})();
