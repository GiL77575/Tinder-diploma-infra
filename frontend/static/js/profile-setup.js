/** Wizard анкети / редагування: кроки, фото 800×800, рівні хобі та мов. */
(function () {
    const form = document.getElementById('setup-form');
    if (!form) {
        return;
    }

    const isEdit = form.dataset.mode === 'edit';
    const panels = Array.from(form.querySelectorAll('.panel'));
    const dots = Array.from(document.querySelectorAll('[data-step-dot]'));
    const btnBack = document.getElementById('btn-back');
    const btnNext = document.getElementById('btn-next');
    const btnSubmit = document.getElementById('btn-submit');
    const stepError = document.getElementById('step-error');
    const photosInput = document.getElementById('photos-input');
    const slots = Array.from(document.querySelectorAll('.photo-slot'));
    const photoBlobs = new Array(6).fill(null);
    let currentStep = 1;

    /** Показує крок wizard і оновлює кнопки «Назад / Далі / Зберегти». */
    function showStep(step) {
        currentStep = step;
        panels.forEach((panel) => {
            panel.classList.toggle('is-active', Number(panel.dataset.step) === step);
        });
        dots.forEach((dot) => {
            dot.classList.toggle('is-active', Number(dot.dataset.stepDot) <= step);
        });
        if (btnBack) {
            btnBack.hidden = step === 1;
        }
        if (btnNext) {
            btnNext.hidden = step === 4;
        }
        if (btnSubmit) {
            btnSubmit.hidden = step !== 4;
        }
        stepError.hidden = true;
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    /** Показує текст помилки під кнопками кроку. */
    function setError(message) {
        stepError.textContent = message;
        stepError.hidden = false;
    }

    /** Повертає обраний radio/checkbox з таким name або null. */
    function checked(name) {
        return form.querySelector(`input[name="${name}"]:checked`);
    }

    /** Чи є хоча б одне нове або вже збережене фото. */
    function hasAnyPhoto() {
        return photoBlobs.some(Boolean) || Boolean(form.querySelector('input[name="keep_photos"]'));
    }

    /** Повертає текст помилки для кроку або порожній рядок. */
    function validateStep(step) {
        if (step === 1) {
            if (!hasAnyPhoto()) {
                return 'Додай хоча б одне фото.';
            }
        }
        if (step === 2) {
            if (!form.display_name.value.trim()) {
                return 'Вкажи ім’я для профілю.';
            }
            if (!form.birth_date.value) {
                return 'Вкажи дату народження.';
            }
            if (!checked('gender')) {
                return 'Обери стать.';
            }
            if (!checked('orientation')) {
                return 'Обери орієнтацію.';
            }
            if (!form.city.value.trim()) {
                return 'Вкажи місто.';
            }
        }
        if (step === 3) {
            if (!checked('dating_looking_for')) {
                return 'Обери, кого шукаєш у режимі знайомств.';
            }
            if (!form.dating_bio.value.trim()) {
                return 'Напиши опис для знайомств.';
            }
            if (!form.querySelector('input[name="dating_interests"]:checked')) {
                return 'Обери хоча б один інтерес для знайомств.';
            }
        }
        if (step === 4) {
            if (!checked('bff_looking_for')) {
                return 'Обери ціль у пошуку друзів.';
            }
            if (!form.bff_bio.value.trim()) {
                return 'Напиши опис для пошуку друзів.';
            }
            const hobbies = Array.from(form.querySelectorAll('input[name="bff_hobbies"]:checked'));
            if (!hobbies.length) {
                return 'Обери хоча б одне хобі.';
            }
            const missingLevel = hobbies.some((input) => {
                const select = document.getElementById(`hobby-level-${input.value}`);
                return !select || !select.value;
            });
            if (missingLevel) {
                return 'Для кожного хобі обери рівень (початківець / профі).';
            }
            const languages = Array.from(form.querySelectorAll('input[name="bff_languages"]:checked'));
            const missingLang = languages.some((input) => {
                const select = document.getElementById(`language-level-${input.value}`);
                return !select || !select.value;
            });
            if (missingLang) {
                return 'Для кожної мови обери рівень.';
            }
        }
        return '';
    }

    /** Обрізає зображення до квадрата 800×800 і повертає JPEG-blob. */
    function cropToSquare(file) {
        return new Promise((resolve, reject) => {
            const image = new Image();
            const url = URL.createObjectURL(file);
            image.onload = () => {
                const side = Math.min(image.width, image.height);
                const sx = (image.width - side) / 2;
                const sy = (image.height - side) / 2;
                const canvas = document.createElement('canvas');
                canvas.width = 800;
                canvas.height = 800;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(image, sx, sy, side, side, 0, 0, 800, 800);
                canvas.toBlob(
                    (blob) => {
                        URL.revokeObjectURL(url);
                        if (!blob) {
                            reject(new Error('Не вдалося обробити фото.'));
                            return;
                        }
                        resolve(blob);
                    },
                    'image/jpeg',
                    0.88
                );
            };
            image.onerror = () => {
                URL.revokeObjectURL(url);
                reject(new Error('Не вдалося прочитати фото.'));
            };
            image.src = url;
        });
    }

    /** Записує оброблені фото в hidden input перед відправкою форми. */
    function syncPhotoInput() {
        const transfer = new DataTransfer();
        photoBlobs.filter(Boolean).forEach((blob, index) => {
            transfer.items.add(new File([blob], `photo-${index + 1}.jpg`, { type: 'image/jpeg' }));
        });
        photosInput.files = transfer.files;
    }

    /** Показує «+» у порожньому слоті галереї. */
    function ensurePlus(slot) {
        let plus = slot.querySelector('.photo-slot__plus');
        if (!plus) {
            plus = document.createElement('span');
            plus.className = 'photo-slot__plus';
            plus.textContent = '+';
            slot.prepend(plus);
        }
        plus.hidden = false;
        return plus;
    }

    /** Додає кнопку видалення фото, якщо її ще немає. */
    function ensureRemoveButton(slot) {
        if (slot.querySelector('.js-remove-photo')) {
            return;
        }
        const remove = document.createElement('span');
        remove.className = 'photo-slot__remove js-remove-photo';
        remove.setAttribute('aria-label', 'Видалити фото');
        remove.textContent = '×';
        slot.append(remove);
    }

    /** Очищає слот: прев’ю, keep_photos і кнопку видалення. */
    function clearSlotMedia(slot) {
        slot.querySelectorAll('img').forEach((img) => img.remove());
        slot.querySelectorAll('input[name="keep_photos"]').forEach((input) => input.remove());
        slot.querySelectorAll('.js-remove-photo').forEach((btn) => btn.remove());
        ensurePlus(slot);
        slot.classList.remove('is-filled');
    }

    /** Малює прев’ю нового фото в слоті. */
    function renderSlot(index) {
        const slot = slots[index];
        const blob = photoBlobs[index];
        clearSlotMedia(slot);
        if (!blob) {
            return;
        }
        const plus = slot.querySelector('.photo-slot__plus');
        if (plus) {
            plus.hidden = true;
        }
        const img = document.createElement('img');
        img.alt = 'Фото профілю';
        img.src = URL.createObjectURL(blob);
        slot.prepend(img);
        slot.classList.add('is-filled');
        ensureRemoveButton(slot);
    }

    slots.forEach((slot) => {
        slot.addEventListener('click', (event) => {
            const index = Number(slot.dataset.slot);
            if (event.target.closest('.js-remove-photo')) {
                event.preventDefault();
                event.stopPropagation();
                photoBlobs[index] = null;
                clearSlotMedia(slot);
                syncPhotoInput();
                return;
            }
            const picker = document.createElement('input');
            picker.type = 'file';
            picker.accept = 'image/jpeg,image/png,image/webp';
            picker.addEventListener('change', async () => {
                const file = picker.files && picker.files[0];
                if (!file) {
                    return;
                }
                try {
                    const blob = await cropToSquare(file);
                    photoBlobs[index] = blob;
                    renderSlot(index);
                    syncPhotoInput();
                } catch (error) {
                    setError(error.message);
                }
            });
            picker.click();
        });
    });

    form.querySelectorAll('.js-level-toggle').forEach((checkbox) => {
        const select = document.getElementById(checkbox.dataset.levelTarget);
        const sync = () => {
            if (!select) {
                return;
            }
            select.disabled = !checkbox.checked;
            if (!checkbox.checked) {
                select.value = '';
            }
        };
        checkbox.addEventListener('change', sync);
        sync();
    });

    /** Лічильник символів для textarea (наприклад 12/500). */
    function bindCounter(name, counterId) {
        const field = form.querySelector(`[name="${name}"]`);
        const counter = document.getElementById(counterId);
        if (!field || !counter) {
            return;
        }
        const update = () => {
            counter.textContent = `${field.value.length}/500`;
        };
        field.addEventListener('input', update);
        update();
    }
    bindCounter('dating_bio', 'dating-bio-count');
    bindCounter('bff_bio', 'bff-bio-count');

    if (!isEdit && btnNext) {
        btnNext.addEventListener('click', () => {
            const message = validateStep(currentStep);
            if (message) {
                setError(message);
                return;
            }
            showStep(currentStep + 1);
        });
    }

    if (!isEdit && btnBack) {
        btnBack.addEventListener('click', () => {
            showStep(Math.max(1, currentStep - 1));
        });
    }

    form.addEventListener('submit', (event) => {
        const steps = isEdit ? [1, 2, 3, 4] : [4];
        const message = steps.map(validateStep).find(Boolean);
        if (message) {
            event.preventDefault();
            setError(message);
            return;
        }
        syncPhotoInput();
        if (!hasAnyPhoto()) {
            event.preventDefault();
            setError('Додай хоча б одне фото.');
        }
    });

    if (isEdit) {
        panels.forEach((panel) => panel.classList.add('is-active'));
        if (btnSubmit) {
            btnSubmit.hidden = false;
        }
    } else {
        const errorStep = Number(form.dataset.errorStep || 0);
        showStep(errorStep || 1);
    }
})();
