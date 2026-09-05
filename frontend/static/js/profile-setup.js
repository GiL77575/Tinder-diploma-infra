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
    const btnSkip = document.getElementById('btn-skip');
    const skipBffInput = document.getElementById('skip-bff');
    const skipDatingInput = document.getElementById('skip-dating');
    const stepError = document.getElementById('step-error');
    const photosInput = document.getElementById('photos-input');
    const slots = Array.from(document.querySelectorAll('.photo-slot'));
    const photoBlobs = new Array(6).fill(null);
    const setupPage = document.body.classList.contains('page-setup');
    const cardBody = document.querySelector('.setup-card__body');
    const setupCard = document.querySelector('.setup-card');
    let currentStep = 1;
    let syncBirthDateHidden = () => {};

    /** Картка ніколи не має скролитись сама (лише .setup-card__body).
     * Браузер іноді сам скролює найближчий overflow-контейнер під час
     * фокусу на вкладеному елементі — це «зʼїдає» верх картки. */
    if (setupCard) {
        setupCard.addEventListener('scroll', () => {
            setupCard.scrollTop = 0;
        });
    }

    /** Закриває всі компактні dropdown (дата, рівні хобі/мов). */
    const compactDropdowns = {
        items: [],
        register(api) {
            this.items.push(api);
        },
        closeAll(except) {
            this.items.forEach((api) => {
                if (except && api === except) {
                    return;
                }
                api.close();
            });
        },
    };

    function getCrushFrameMetrics() {
        const frame = document.querySelector('.crush-frame');
        if (!frame) {
            return null;
        }
        const frameRect = frame.getBoundingClientRect();
        const frameWidth = 1920;
        const scale = frameRect.width / frameWidth || 1;
        return { frameRect, scale };
    }

    function positionCompactMenu(trigger, menu) {
        const rect = trigger.getBoundingClientRect();
        const frameMetrics = getCrushFrameMetrics();

        menu.style.position = 'fixed';
        menu.style.right = 'auto';
        menu.style.zIndex = '200';

        if (frameMetrics) {
            const { frameRect, scale } = frameMetrics;
            menu.style.left = `${(rect.left - frameRect.left) / scale}px`;
            menu.style.top = `${(rect.bottom - frameRect.top + 4) / scale}px`;
            menu.style.width = `${rect.width / scale}px`;
            return;
        }

        menu.style.left = `${rect.left}px`;
        menu.style.top = `${rect.bottom + 4}px`;
        menu.style.width = `${rect.width}px`;
    }

    function resetCompactMenuPosition(menu) {
        menu.style.position = '';
        menu.style.top = '';
        menu.style.left = '';
        menu.style.width = '';
        menu.style.right = '';
        menu.style.zIndex = '';
    }

    /** Чи блок «Друзі» лишився порожнім (можна пропустити). */
    function isBffEmpty() {
        return !checked('bff_looking_for')
            && !form.bff_bio.value.trim()
            && !form.querySelector('input[name="bff_hobbies"]:checked')
            && !form.querySelector('input[name="bff_languages"]:checked')
            && !form.querySelector('input[name="bff_interests"]:checked');
    }

    /** Чи блок «Знайомства» лишився порожнім (можна пропустити). */
    function isDatingEmpty() {
        return !checked('dating_looking_for')
            && !form.dating_bio.value.trim()
            && !form.querySelector('input[name="dating_interests"]:checked');
    }

    function setSkipBff(value) {
        if (skipBffInput) {
            skipBffInput.value = value ? '1' : '';
        }
    }

    /** Прапорець «блок Знайомства свідомо пропущено кнопкою Пропустити». */
    function setSkipDating(value) {
        if (skipDatingInput) {
            skipDatingInput.value = value ? '1' : '';
        }
    }

    /** Показує крок wizard і оновлює кнопки «Назад / Далі / Зберегти». */
    function showStep(step) {
        step = Math.max(1, Math.min(4, Number(step) || 1));
        currentStep = step;
        if (step === 4) {
            setSkipBff(false);
        }
        compactDropdowns.closeAll();
        syncBirthDateHidden();
        panels.forEach((panel) => {
            panel.classList.toggle('is-active', Number(panel.dataset.step) === step);
        });
        dots.forEach((dot) => {
            dot.classList.toggle('is-active', Number(dot.dataset.stepDot) === step);
        });
        if (setupPage) {
            document.body.dataset.setupStep = String(step);
        }
        if (btnBack) {
            btnBack.hidden = step === 1;
        }
        if (btnNext) {
            btnNext.hidden = step === 4;
        }
        if (btnSubmit) {
            btnSubmit.hidden = step !== 4;
        }
        if (btnSkip) {
            // На кроці 3 «Пропустити» пропускає лише анкету знайомств і йде далі
            // (до «Друзі»); на кроці 4 — пропускає «Друзі» й одразу зберігає профіль.
            btnSkip.hidden = step !== 3 && step !== 4;
        }
        if (stepError) {
            stepError.hidden = true;
        }
        if (cardBody) {
            cardBody.scrollTop = 0;
        }
        window.scrollTo(0, 0);
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

    /** Повертає вік у повних роках за ISO-датою YYYY-MM-DD або null. */
    function getAgeFromIso(isoDate) {
        const parts = isoDate.split('-').map(Number);
        if (parts.length !== 3 || parts.some((part) => !part)) {
            return null;
        }
        const [year, month, day] = parts;
        const today = new Date();
        let age = today.getFullYear() - year;
        const monthDiff = today.getMonth() + 1 - month;
        if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < day)) {
            age -= 1;
        }
        return age;
    }

    /** Компактні dropdown (день / місяць / рік) замість нативного select. */
    function initBirthDatePicker() {
        const hidden = form.querySelector('input[name="birth_date"]');
        const birthDateRoot = form.querySelector('.birth-date');
        if (!hidden || !birthDateRoot) {
            return;
        }

        const monthNames = [
            'Січень', 'Лютий', 'Березень', 'Квітень', 'Травень', 'Червень',
            'Липень', 'Серпень', 'Вересень', 'Жовтень', 'Листопад', 'Грудень',
        ];
        const currentYear = new Date().getFullYear();
        const maxYear = currentYear - 18;
        const minYear = currentYear - 99;

        const parts = {};
        birthDateRoot.querySelectorAll('.birth-date__field').forEach((field) => {
            const key = field.dataset.part;
            parts[key] = {
                field,
                trigger: field.querySelector('.birth-date__trigger'),
                valueEl: field.querySelector('.birth-date__value'),
                menu: field.querySelector('.birth-date__menu'),
                placeholder: field.querySelector('.birth-date__value').textContent.trim(),
                value: '',
            };
        });

        if (!parts.day || !parts.month || !parts.year) {
            return;
        }

        function daysInMonth(year, month) {
            return new Date(year, month, 0).getDate();
        }

        function closeMenus(exceptPart) {
            Object.values(parts).forEach((part) => {
                if (exceptPart && part === exceptPart) {
                    return;
                }
                part.menu.hidden = true;
                part.trigger.setAttribute('aria-expanded', 'false');
                part.trigger.classList.remove('is-open');
                resetCompactMenuPosition(part.menu);
            });
            birthDateRoot.classList.remove('is-open');
        }

        function openMenu(part) {
            const isOpen = !part.menu.hidden;
            compactDropdowns.closeAll();
            if (isOpen) {
                return;
            }
            part.menu.hidden = false;
            part.trigger.setAttribute('aria-expanded', 'true');
            part.trigger.classList.add('is-open');
            birthDateRoot.classList.add('is-open');
            positionCompactMenu(part.trigger, part.menu);
        }

        Object.values(parts).forEach((part) => {
            part.api = {
                close: () => closeMenus(),
            };
            compactDropdowns.register(part.api);
        });

        function renderMenu(part, items) {
            part.menu.innerHTML = '';
            items.forEach(({ value, label }) => {
                const option = document.createElement('li');
                option.className = 'birth-date__option';
                option.setAttribute('role', 'option');
                option.dataset.value = String(value);
                option.textContent = label;
                if (String(part.value) === String(value)) {
                    option.classList.add('is-selected');
                    option.setAttribute('aria-selected', 'true');
                }
                option.addEventListener('click', (event) => {
                    event.stopPropagation();
                    setPartValue(part, value, label);
                    closeMenus();
                    if (part === parts.month || part === parts.year) {
                        rebuildDays();
                    }
                    syncHidden();
                });
                part.menu.append(option);
            });
        }

        function setPartValue(part, value, label) {
            part.value = value ? String(value) : '';
            part.valueEl.textContent = label || part.placeholder;
            part.trigger.classList.toggle('is-filled', Boolean(part.value));
        }

        function populateMonthMenu() {
            renderMenu(parts.month, monthNames.map((label, index) => ({
                value: index + 1,
                label,
            })));
        }

        function populateYearMenu() {
            const items = [];
            for (let year = maxYear; year >= minYear; year -= 1) {
                items.push({ value: year, label: String(year) });
            }
            renderMenu(parts.year, items);
        }

        function rebuildDays() {
            const year = Number(parts.year.value);
            const month = Number(parts.month.value);
            const totalDays = year && month ? daysInMonth(year, month) : 31;
            const previousDay = parts.day.value;
            const items = [];
            for (let day = 1; day <= totalDays; day += 1) {
                items.push({ value: day, label: String(day) });
            }
            renderMenu(parts.day, items);
            if (previousDay && Number(previousDay) <= totalDays) {
                setPartValue(parts.day, previousDay, String(previousDay));
            } else if (previousDay) {
                setPartValue(parts.day, '', parts.day.placeholder);
            }
        }

        function syncHidden() {
            const year = parts.year.value;
            const month = parts.month.value;
            const day = parts.day.value;
            if (year && month && day) {
                hidden.value = `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
            } else {
                hidden.value = '';
            }
        }

        function applyIsoValue(isoDate) {
            if (!isoDate) {
                return;
            }
            const [year, month, day] = isoDate.split('-');
            if (!year || !month || !day) {
                return;
            }
            setPartValue(parts.year, year, year);
            setPartValue(parts.month, Number(month), monthNames[Number(month) - 1]);
            rebuildDays();
            setPartValue(parts.day, Number(day), String(Number(day)));
            syncHidden();
        }

        Object.values(parts).forEach((part) => {
            part.trigger.addEventListener('click', (event) => {
                event.preventDefault();
                event.stopPropagation();
                openMenu(part);
            });
        });

        populateMonthMenu();
        populateYearMenu();
        rebuildDays();
        applyIsoValue(hidden.value);
        syncBirthDateHidden = syncHidden;
    }

    /** Компактний dropdown для select рівня хобі / мов. */
    function initLevelCompactSelects() {
        form.querySelectorAll('.level-row select').forEach((nativeSelect) => {
            if (nativeSelect.dataset.compactSelect === '1') {
                return;
            }
            nativeSelect.dataset.compactSelect = '1';

            const wrapper = document.createElement('div');
            wrapper.className = 'compact-select';
            nativeSelect.parentNode.insertBefore(wrapper, nativeSelect);
            wrapper.append(nativeSelect);

            nativeSelect.classList.add('compact-select__native');
            nativeSelect.tabIndex = -1;
            nativeSelect.setAttribute('aria-hidden', 'true');

            const trigger = document.createElement('button');
            trigger.type = 'button';
            trigger.className = 'compact-select__trigger birth-date__trigger';
            trigger.setAttribute('aria-haspopup', 'listbox');
            trigger.setAttribute('aria-expanded', 'false');
            trigger.innerHTML = '<span class="compact-select__value birth-date__value"></span>';
            wrapper.append(trigger);

            const menu = document.createElement('ul');
            menu.className = 'compact-select__menu birth-date__menu';
            menu.setAttribute('role', 'listbox');
            menu.hidden = true;
            wrapper.append(menu);

            const valueEl = trigger.querySelector('.compact-select__value');
            const placeholder = nativeSelect.querySelector('option[value=""]')?.textContent.trim() || 'Рівень';

            function syncDisplay() {
                const selectedOption = nativeSelect.selectedOptions[0];
                valueEl.textContent = selectedOption && selectedOption.value
                    ? selectedOption.textContent
                    : placeholder;
                trigger.classList.toggle('is-filled', Boolean(nativeSelect.value));
            }

            function renderMenu() {
                menu.innerHTML = '';
                Array.from(nativeSelect.options).forEach((option) => {
                    if (!option.value) {
                        return;
                    }
                    const item = document.createElement('li');
                    item.className = 'compact-select__option birth-date__option';
                    item.setAttribute('role', 'option');
                    item.textContent = option.textContent;
                    if (nativeSelect.value === option.value) {
                        item.classList.add('is-selected');
                        item.setAttribute('aria-selected', 'true');
                    }
                    item.addEventListener('click', (event) => {
                        event.stopPropagation();
                        nativeSelect.value = option.value;
                        syncDisplay();
                        api.close();
                        nativeSelect.dispatchEvent(new Event('change', { bubbles: true }));
                    });
                    menu.append(item);
                });
            }

            function closeMenu() {
                menu.hidden = true;
                trigger.setAttribute('aria-expanded', 'false');
                trigger.classList.remove('is-open');
                wrapper.classList.remove('is-open');
                resetCompactMenuPosition(menu);
            }

            function ensureEnabled() {
                if (nativeSelect.disabled) {
                    const row = nativeSelect.closest('.level-row');
                    const checkbox = row && row.querySelector('.js-level-toggle');
                    if (checkbox && !checkbox.checked) {
                        checkbox.checked = true;
                        checkbox.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                }
            }

            function openMenu() {
                ensureEnabled();
                const isOpen = !menu.hidden;
                compactDropdowns.closeAll();
                if (isOpen || nativeSelect.disabled) {
                    return;
                }
                renderMenu();
                menu.hidden = false;
                trigger.setAttribute('aria-expanded', 'true');
                trigger.classList.add('is-open');
                wrapper.classList.add('is-open');
            }

            const api = {
                close: closeMenu,
                setDisabled(disabled) {
                    trigger.disabled = disabled;
                    if (disabled) {
                        closeMenu();
                    }
                },
            };
            compactDropdowns.register(api);
            trigger.compactSelectApi = api;

            trigger.addEventListener('click', (event) => {
                event.preventDefault();
                event.stopPropagation();
                openMenu();
            });

            nativeSelect.addEventListener('change', syncDisplay);
            api.setDisabled(nativeSelect.disabled);
            syncDisplay();
        });
    }

    initBirthDatePicker();
    initLevelCompactSelects();

    document.addEventListener('click', (event) => {
        if (event.target.closest('.compact-select') || event.target.closest('.birth-date__field')) {
            return;
        }
        compactDropdowns.closeAll();
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            compactDropdowns.closeAll();
        }
    });

    /** Повертає текст помилки для кроку або порожній рядок. */
    function validateStep(step) {
        syncBirthDateHidden();
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
            const age = getAgeFromIso(form.birth_date.value);
            if (age === null) {
                return 'Перевір дату народження.';
            }
            if (age < 18) {
                return 'Реєстрація доступна з 18 років.';
            }
            if (age > 99) {
                return 'Перевірте дату народження.';
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
            if (skipDatingInput?.value === '1' && isDatingEmpty()) {
                return '';
            }
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
            if (isBffEmpty() || skipBffInput?.value === '1') {
                return '';
            }
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
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'photo-slot__remove js-remove-photo';
        remove.setAttribute('aria-label', 'Видалити фото');
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
                select.dispatchEvent(new Event('change', { bubbles: true }));
            }
            const wrapper = select.closest('.compact-select');
            const trigger = wrapper && wrapper.querySelector('.compact-select__trigger');
            if (trigger && trigger.compactSelectApi) {
                trigger.compactSelectApi.setDisabled(select.disabled);
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
            syncBirthDateHidden();
            compactDropdowns.closeAll();
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

    if (!isEdit && btnSkip) {
        btnSkip.addEventListener('click', () => {
            syncBirthDateHidden();
            compactDropdowns.closeAll();

            // Крок 3: пропускаємо лише анкету знайомств і переходимо до «Друзі».
            // Єдина вимога — заповнені кроки 1–2 (фото й «Про себе»); режим
            // за замовчуванням уже обраний радіо-кнопкою «Основний режим зараз».
            if (currentStep === 3) {
                setSkipDating(true);
                const message = [1, 2].map(validateStep).find(Boolean);
                if (message) {
                    setSkipDating(false);
                    setError(message);
                    return;
                }
                showStep(4);
                return;
            }

            // Крок 4: пропускаємо «Друзі» й одразу зберігаємо профіль.
            setSkipBff(true);
            const message = [1, 2, 3].map(validateStep).find(Boolean);
            if (message) {
                setSkipBff(false);
                setError(message);
                return;
            }
            syncPhotoInput();
            if (!hasAnyPhoto()) {
                setSkipBff(false);
                setError('Додай хоча б одне фото.');
                return;
            }
            form.requestSubmit();
        });
    }

    form.addEventListener('submit', (event) => {
        syncBirthDateHidden();
        compactDropdowns.closeAll();
        let message = '';
        if (isEdit) {
            message = [1, 2, 3, 4].map(validateStep).find(Boolean) || '';
        } else {
            const skipping = skipBffInput?.value === '1' || isBffEmpty();
            if (skipping) {
                message = [1, 2, 3].map(validateStep).find(Boolean) || '';
            } else {
                message = validateStep(4);
            }
        }
        if (message) {
            event.preventDefault();
            setSkipBff(false);
            setError(message);
            return;
        }
        if (!isBffEmpty()) {
            setSkipBff(false);
        }
        if (!isDatingEmpty()) {
            setSkipDating(false);
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
