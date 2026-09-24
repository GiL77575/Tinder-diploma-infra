/* crush — сторінка чату: перемикач режимів, метчі, діалоги, свайпи, WebSocket. */
(() => {
    'use strict';

    const API = {
        matches: (mode) => `/app/matches/?mode=${encodeURIComponent(mode)}`,
        discover: (mode) => `/app/discover/?mode=${encodeURIComponent(mode)}`,
        like: '/app/like/',
        conversations: (mode) => `/app/conversations/?mode=${encodeURIComponent(mode)}`,
        conversationOpen: '/app/conversations/open/',
        conversationMessages: (id) => `/app/conversations/${id}/messages/`,
        conversationRead: (id) => `/app/conversations/${id}/read/`,
        conversationSendPhoto: (id) => `/app/conversations/${id}/photo/`,
        conversationEditMessage: (cid, mid) => `/app/conversations/${cid}/messages/${mid}/edit/`,
        conversationDeleteMessage: (cid, mid) => `/app/conversations/${cid}/messages/${mid}/delete/`,
        unmatch: (id) => `/app/unmatch/${id}/`,
        meetingMine: '/app/meetings/mine/',
        meetingCreate: '/app/meetings/create/',
        meetingDetail: (id) => `/app/meetings/${id}/`,
        meetingEdit: (id) => `/app/meetings/${id}/edit/`,
        meetingCancel: (id) => `/app/meetings/${id}/cancel/`,
        meetingJoin: (id) => `/app/meetings/${id}/join/`,
        meetingLeave: (id) => `/app/meetings/${id}/leave/`,
        meetingChat: (id) => `/app/meetings/${id}/chat/`,
    };

    const ALLOWED_PHOTO_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
    const MAX_PHOTO_BYTES = 5 * 1024 * 1024;

    const SWIPE_DRAG_THRESHOLD = 110;
    const SWIPE_MOVE_DEADZONE = 6;

    const body = document.body;
    const urlMode = new URLSearchParams(window.location.search).get('mode');
    const state = {
        mode: (urlMode === 'dating' || urlMode === 'bff')
            ? urlMode
            : (body.dataset.initialMode || 'dating'),
        myUserId: parseInt(body.dataset.myUserId, 10) || null,
        conversationId: null,
        ws: null,
        wsReconnectAttempts: 0,
        inboxWs: null,
        inboxReconnectAttempts: 0,
        activeMatchId: null,
        activeMeetingId: null,
        myMeeting: null,
        chatKind: 'match',
        activeCandidateUserId: null,
        activeCandidate: null,
        swipeLocked: false,
        animating: false,
        cardWasDragged: false,
        sending: false,
        pendingPhoto: null,
        pendingPhotoUrl: null,
        editingMessageId: null,
        menuMessageId: null,
        pendingDeleteMessageId: null,
        pendingDeleteConversationId: null,
        deleteTimerId: null,
        deleteTickId: null,
        deleteSecondsLeft: 0,
    };

    const els = {
        modeSwitch: document.getElementById('mode-switch'),
        modeButtons: Array.from(document.querySelectorAll('.mode-switch__btn')),
        matchesGrid: document.getElementById('matches-grid'),
        dialogsList: document.getElementById('dialogs-list'),
        discoverView: document.getElementById('discover-view'),
        swipeCard: document.getElementById('swipe-card'),
        swipeActions: document.getElementById('swipe-actions'),
        likeBtn: document.getElementById('like-btn'),
        dislikeBtn: document.getElementById('dislike-btn'),
        expandProfileBtn: document.getElementById('expand-profile-btn'),
        fullProfileOverlay: document.getElementById('full-profile-overlay'),
        fullProfileBackdrop: document.getElementById('full-profile-backdrop'),
        fullProfileClose: document.getElementById('full-profile-close'),
        fullProfileMainPhoto: document.getElementById('full-profile-main-photo'),
        fullProfileThumbs: document.getElementById('full-profile-thumbs'),
        fullProfileName: document.getElementById('full-profile-name'),
        fullProfileCity: document.getElementById('full-profile-city'),
        fullProfileMeta: document.getElementById('full-profile-meta'),
        fullProfileBio: document.getElementById('full-profile-bio'),
        fullProfileTags: document.getElementById('full-profile-tags'),
        fullProfileSkills: document.getElementById('full-profile-skills'),
        fullProfileMeeting: document.getElementById('full-profile-meeting'),
        fullProfileMeetingDate: document.getElementById('full-profile-meeting-date'),
        fullProfileMeetingDesc: document.getElementById('full-profile-meeting-desc'),
        fullProfileJoinBtn: document.getElementById('full-profile-join-btn'),
        chatView: document.getElementById('chat-view'),
        chatBackBtn: document.getElementById('chat-back-btn'),
        chatMessages: document.getElementById('chat-messages'),
        chatForm: document.getElementById('chat-form'),
        chatInput: document.getElementById('chat-input'),
        chatAttachBtn: document.getElementById('chat-attach-btn'),
        chatPhotoInput: document.getElementById('chat-photo-input'),
        chatPhotoPreview: document.getElementById('chat-photo-preview'),
        chatPhotoPreviewImg: document.getElementById('chat-photo-preview-img'),
        chatPhotoPreviewRemove: document.getElementById('chat-photo-preview-remove'),
        chatLightbox: document.getElementById('chat-lightbox'),
        chatLightboxImage: document.getElementById('chat-lightbox-image'),
        chatLightboxClose: document.getElementById('chat-lightbox-close'),
        chatPartnerAvatar: document.getElementById('chat-partner-avatar'),
        chatPartnerName: document.getElementById('chat-partner-name'),
        chatPartnerStatus: document.getElementById('chat-partner-status'),
        matchesMore: document.getElementById('matches-more'),
        dialogsTitle: document.getElementById('dialogs-title'),
        meetingActions: document.getElementById('meeting-actions'),
        createMeetingBtn: document.getElementById('create-meeting-btn'),
        editMeetingBtn: document.getElementById('edit-meeting-btn'),
        cancelMeetingBtn: document.getElementById('cancel-meeting-btn'),
        meetingFormOverlay: document.getElementById('meeting-form-overlay'),
        meetingForm: document.getElementById('meeting-form'),
        meetingFormTitle: document.getElementById('meeting-form-title'),
        meetingFormSubmit: document.getElementById('meeting-form-submit'),
        meetingFormError: document.getElementById('meeting-form-error'),
        meetingFormName: document.getElementById('meeting-form-name'),
        meetingFormLocation: document.getElementById('meeting-form-location'),
        meetingFormDate: document.getElementById('meeting-form-date'),
        meetingFormTime: document.getElementById('meeting-form-time'),
        meetingFormDay: document.getElementById('meeting-form-day'),
        meetingFormMonth: document.getElementById('meeting-form-month'),
        meetingFormDayLabel: document.getElementById('meeting-form-day-label'),
        meetingFormMonthLabel: document.getElementById('meeting-form-month-label'),
        meetingFormDayMenu: document.getElementById('meeting-form-day-menu'),
        meetingFormMonthMenu: document.getElementById('meeting-form-month-menu'),
        meetingFormDayTrigger: document.getElementById('meeting-form-day-trigger'),
        meetingFormMonthTrigger: document.getElementById('meeting-form-month-trigger'),
        meetingFormDescription: document.getElementById('meeting-form-description'),
        meetingFormPhoto: document.getElementById('meeting-form-photo'),
        meetingFormPhotoPreview: document.getElementById('meeting-form-photo-preview'),
        meetingFormIntro: document.querySelector('.meeting-form__intro'),
        meetingViewOverlay: document.getElementById('meeting-view-overlay'),
        meetingViewTitle: document.getElementById('meeting-view-title'),
        meetingViewLocation: document.getElementById('meeting-view-location'),
        meetingViewDate: document.getElementById('meeting-view-date'),
        meetingViewTime: document.getElementById('meeting-view-time'),
        meetingViewDescription: document.getElementById('meeting-view-description'),
        meetingViewActions: document.getElementById('meeting-view-actions'),
        meetingConfirmOverlay: document.getElementById('meeting-confirm-overlay'),
        meetingConfirmYes: document.getElementById('meeting-confirm-yes'),
        chatMoreBtn: document.getElementById('chat-more-btn'),
        chatMoreMenu: document.getElementById('chat-more-menu'),
        chatUnmatchBtn: document.getElementById('chat-unmatch-btn'),
        chatLeaveMeetingBtn: document.getElementById('chat-leave-meeting-btn'),
        msgMenu: document.getElementById('msg-menu'),
        chatEditBar: document.getElementById('chat-edit-bar'),
        chatEditPreview: document.getElementById('chat-edit-preview'),
        chatEditCancel: document.getElementById('chat-edit-cancel'),
        chatUndoBar: document.getElementById('chat-undo-bar'),
        chatUndoSeconds: document.getElementById('chat-undo-seconds'),
        chatUndoBtn: document.getElementById('chat-undo-btn'),
    };

    function csrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.content : '';
    }

    async function apiFetch(url, options = {}) {
        const opts = Object.assign({ credentials: 'same-origin' }, options);
        opts.headers = Object.assign(
            { 'X-Requested-With': 'XMLHttpRequest' },
            options.headers || {},
        );
        if (options.method && options.method !== 'GET') {
            opts.headers['X-CSRFToken'] = csrfToken();
            opts.headers['Content-Type'] = 'application/json';
        }
        let response;
        try {
            response = await fetch(url, opts);
        } catch (err) {
            throw new Error('Немає зв’язку з сервером. Оновіть сторінку.');
        }
        if (!response.ok) {
            let detail = '';
            try {
                detail = (await response.json()).error || '';
            } catch (e) { /* ignore */ }
            throw new Error(detail || `Помилка запиту (${response.status})`);
        }
        return response.json();
    }

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str == null ? '' : String(str);
        return div.innerHTML;
    }

    function avatarPlaceholder() {
        return 'data:image/svg+xml;utf8,' + encodeURIComponent(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 56 56">'
            + '<rect width="56" height="56" rx="28" fill="#F4EDFF"/>'
            + '<circle cx="28" cy="22" r="9" fill="#C7A9F2"/>'
            + '<path d="M10 48c3.5-8 10.7-13 18-13s14.5 5 18 13" fill="#C7A9F2"/>'
            + '</svg>',
        );
    }

    function applyModeChrome(mode) {
        body.dataset.mode = mode;
        if (els.dialogsTitle) {
            els.dialogsTitle.textContent = mode === 'bff' ? 'Діалоги/Групи' : 'Діалоги';
        }
        if (els.meetingActions) {
            els.meetingActions.hidden = mode !== 'bff';
        }
        if (mode === 'bff') {
            refreshMyMeeting();
        } else {
            state.myMeeting = null;
            updateMeetingSidebarButtons();
        }
    }

    function updateMeetingSidebarButtons() {
        const hasMeeting = Boolean(state.myMeeting);
        if (els.createMeetingBtn) els.createMeetingBtn.hidden = hasMeeting;
        if (els.editMeetingBtn) els.editMeetingBtn.hidden = !hasMeeting;
        if (els.cancelMeetingBtn) els.cancelMeetingBtn.hidden = !hasMeeting;
    }

    async function refreshMyMeeting() {
        if (state.mode !== 'bff') {
            state.myMeeting = null;
            updateMeetingSidebarButtons();
            return;
        }
        try {
            const data = await apiFetch(API.meetingMine);
            state.myMeeting = data.meeting || null;
        } catch (err) {
            console.error('Не вдалося завантажити зустріч', err);
            state.myMeeting = null;
        }
        updateMeetingSidebarButtons();
    }

    function syncMeetingOpenClass() {
        const open = Boolean(
            (els.meetingFormOverlay && !els.meetingFormOverlay.hidden)
            || (els.meetingViewOverlay && !els.meetingViewOverlay.hidden)
            || (els.meetingConfirmOverlay && !els.meetingConfirmOverlay.hidden)
        );
        body.classList.toggle('is-meeting-open', open);
    }

    function closeMeetingOverlays() {
        closeMeetingSelectMenus();
        if (els.meetingFormOverlay) els.meetingFormOverlay.hidden = true;
        if (els.meetingViewOverlay) els.meetingViewOverlay.hidden = true;
        if (els.meetingConfirmOverlay) els.meetingConfirmOverlay.hidden = true;
        if (els.meetingFormError) {
            els.meetingFormError.hidden = true;
            els.meetingFormError.textContent = '';
        }
        syncMeetingOpenClass();
    }

    const MEETING_MONTHS = {
        '01': 'Січень',
        '02': 'Лютий',
        '03': 'Березень',
        '04': 'Квітень',
        '05': 'Травень',
        '06': 'Червень',
        '07': 'Липень',
        '08': 'Серпень',
        '09': 'Вересень',
        '10': 'Жовтень',
        '11': 'Листопад',
        '12': 'Грудень',
    };

    function closeMeetingSelectMenus(exceptRoot) {
        document.querySelectorAll('.meeting-form__select.is-open').forEach((root) => {
            if (exceptRoot && root === exceptRoot) return;
            root.classList.remove('is-open');
            const trigger = root.querySelector('.meeting-form__select-trigger');
            const menu = root.querySelector('.meeting-form__select-menu');
            if (trigger) trigger.setAttribute('aria-expanded', 'false');
            if (menu) menu.hidden = true;
        });
    }

    function setMeetingSelectValue(kind, value, labelText) {
        const input = kind === 'day' ? els.meetingFormDay : els.meetingFormMonth;
        const label = kind === 'day' ? els.meetingFormDayLabel : els.meetingFormMonthLabel;
        const menu = kind === 'day' ? els.meetingFormDayMenu : els.meetingFormMonthMenu;
        if (!input || !label) return;
        input.value = value || '';
        if (!value) {
            label.textContent = kind === 'day' ? 'Число' : 'Місяць';
            label.classList.add('is-placeholder');
        } else {
            label.textContent = labelText || value;
            label.classList.remove('is-placeholder');
        }
        if (menu) {
            menu.querySelectorAll('[role="option"]').forEach((opt) => {
                opt.classList.toggle('is-active', opt.dataset.value === value);
            });
        }
        syncMeetingDateFromSelects();
    }

    function fillMeetingDayOptions() {
        if (!els.meetingFormDayMenu || els.meetingFormDayMenu.dataset.filled === '1') return;
        for (let day = 1; day <= 31; day += 1) {
            const li = document.createElement('li');
            const value = String(day).padStart(2, '0');
            li.setAttribute('role', 'option');
            li.dataset.value = value;
            li.tabIndex = -1;
            li.textContent = String(day);
            els.meetingFormDayMenu.appendChild(li);
        }
        els.meetingFormDayMenu.dataset.filled = '1';
    }

    function daysInMonth(year, month) {
        return new Date(year, month, 0).getDate();
    }

    function resolveMeetingYear(month, day) {
        const now = new Date();
        let year = now.getFullYear();
        const candidate = new Date(year, Number(month) - 1, Number(day), 18, 0, 0);
        if (candidate <= now) {
            year += 1;
        }
        return year;
    }

    function syncMeetingDateFromSelects() {
        if (!els.meetingFormDate || !els.meetingFormDay || !els.meetingFormMonth) return '';
        const day = els.meetingFormDay.value;
        const month = els.meetingFormMonth.value;
        if (!day || !month) {
            els.meetingFormDate.value = '';
            return '';
        }
        const year = resolveMeetingYear(month, day);
        const maxDay = daysInMonth(year, Number(month));
        const safeDay = Math.min(Number(day), maxDay);
        const dayStr = String(safeDay).padStart(2, '0');
        if (dayStr !== day) {
            setMeetingSelectValue('day', dayStr, String(safeDay));
            return els.meetingFormDate.value;
        }
        const iso = `${year}-${month}-${dayStr}`;
        els.meetingFormDate.value = iso;
        return iso;
    }

    function setMeetingDateSelects(isoDate) {
        fillMeetingDayOptions();
        if (!isoDate || !els.meetingFormDay || !els.meetingFormMonth) return;
        const parts = String(isoDate).split('-');
        if (parts.length < 3) return;
        const month = parts[1];
        const day = parts[2];
        setMeetingSelectValue('month', month, MEETING_MONTHS[month] || month);
        setMeetingSelectValue('day', day, String(Number(day)));
    }

    function initMeetingSelect(kind) {
        const root = document.querySelector(`[data-meeting-select="${kind}"]`);
        const trigger = kind === 'day' ? els.meetingFormDayTrigger : els.meetingFormMonthTrigger;
        const menu = kind === 'day' ? els.meetingFormDayMenu : els.meetingFormMonthMenu;
        if (!root || !trigger || !menu) return;

        trigger.addEventListener('click', (evt) => {
            evt.preventDefault();
            const willOpen = menu.hidden;
            closeMeetingSelectMenus(willOpen ? root : null);
            if (!willOpen) return;
            if (kind === 'day') fillMeetingDayOptions();
            menu.hidden = false;
            root.classList.add('is-open');
            trigger.setAttribute('aria-expanded', 'true');
        });

        menu.addEventListener('click', (evt) => {
            const opt = evt.target.closest('[role="option"]');
            if (!opt) return;
            const value = opt.dataset.value || '';
            setMeetingSelectValue(kind, value, opt.textContent.trim());
            closeMeetingSelectMenus();
        });
    }

    function clearMeetingPhotoPreview() {
        if (els.meetingFormPhoto) els.meetingFormPhoto.value = '';
        if (els.meetingFormPhotoPreview) {
            els.meetingFormPhotoPreview.classList.remove('has-preview');
            els.meetingFormPhotoPreview.style.backgroundImage = '';
        }
    }

    function openMeetingForm(meeting) {
        closeMeetingOverlays();
        fillMeetingDayOptions();
        const editing = Boolean(meeting);
        if (els.meetingFormTitle) {
            els.meetingFormTitle.textContent = editing ? 'Редагування зустрічі' : 'Створення зустрічі';
        }
        if (els.meetingFormSubmit) {
            els.meetingFormSubmit.textContent = editing
                ? 'Зберегти та запустити у стрічку оновлені дані'
                : 'Зберегти та запустити у стрічку';
        }
        if (els.meetingFormIntro) {
            els.meetingFormIntro.hidden = false;
        }
        clearMeetingPhotoPreview();
        if (els.meetingForm) {
            els.meetingForm.dataset.meetingId = editing ? String(meeting.id) : '';
            els.meetingFormName.value = editing ? meeting.title : '';
            els.meetingFormLocation.value = editing
                ? (meeting.location || 'Уточнюється в чаті')
                : 'Уточнюється в чаті';
            els.meetingFormTime.value = editing ? (meeting.time || '18:00') : '18:00';
            els.meetingFormDescription.value = editing ? meeting.description : '';
            if (editing && meeting.date) {
                setMeetingDateSelects(meeting.date);
            } else {
                setMeetingSelectValue('day', '', '');
                setMeetingSelectValue('month', '', '');
                if (els.meetingFormDate) els.meetingFormDate.value = '';
            }
        }
        if (els.meetingFormOverlay) {
            els.meetingFormOverlay.hidden = false;
            syncMeetingOpenClass();
        }
    }

    function formatMeetingDateLabel(meeting) {
        if (!meeting.starts_at) return meeting.date || '';
        const date = new Date(meeting.starts_at);
        if (Number.isNaN(date.getTime())) return meeting.date || '';
        return date.toLocaleDateString('uk-UA', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric',
        });
    }

    function renderMeetingView(meeting) {
        if (!els.meetingViewOverlay) return;
        els.meetingViewTitle.textContent = meeting.title || '';
        els.meetingViewLocation.textContent = meeting.location || '';
        els.meetingViewDate.textContent = formatMeetingDateLabel(meeting);
        els.meetingViewTime.textContent = meeting.time || '';
        els.meetingViewDescription.textContent = meeting.description || '';
        els.meetingViewActions.innerHTML = '';

        if (meeting.can_join) {
            const joinBtn = document.createElement('button');
            joinBtn.type = 'button';
            joinBtn.className = 'create-meeting-btn';
            joinBtn.textContent = 'Приєднатися';
            joinBtn.addEventListener('click', () => joinMeetingAndOpen(meeting.id));
            els.meetingViewActions.appendChild(joinBtn);
        } else if (meeting.can_open_chat) {
            const openBtn = document.createElement('button');
            openBtn.type = 'button';
            openBtn.className = 'create-meeting-btn';
            openBtn.textContent = 'Відкрити чат';
            openBtn.addEventListener('click', () => openMeetingChat(meeting));
            els.meetingViewActions.appendChild(openBtn);
        }

        els.meetingViewOverlay.hidden = false;
        syncMeetingOpenClass();
    }

    async function openMeetingById(meetingId) {
        try {
            const data = await apiFetch(API.meetingDetail(meetingId));
            renderMeetingView(data.meeting);
        } catch (err) {
            window.alert(err.message || 'Не вдалося відкрити зустріч.');
        }
    }

    async function joinMeetingAndOpen(meetingId) {
        try {
            const data = await apiFetch(API.meetingJoin(meetingId), { method: 'POST' });
            closeMeetingOverlays();
            await openMeetingChat(data.meeting);
            loadDialogs();
        } catch (err) {
            window.alert(err.message || 'Не вдалося приєднатися.');
        }
    }

    async function openMeetingChat(meeting) {
        let conversationId = meeting.conversation_id;
        if (!conversationId) {
            const data = await apiFetch(API.meetingChat(meeting.id));
            conversationId = data.conversation_id;
        }
        closeMeetingOverlays();
        state.activeMatchId = null;
        state.activeMeetingId = meeting.id;
        openChat(conversationId, {
            displayName: meeting.title,
            kind: 'meeting',
            meetingId: meeting.id,
        });
    }

    async function submitMeetingForm(evt) {
        evt.preventDefault();
        if (!els.meetingForm) return;
        const meetingId = els.meetingForm.dataset.meetingId;
        const date = syncMeetingDateFromSelects();
        const payload = {
            title: els.meetingFormName.value.trim(),
            location: (els.meetingFormLocation.value || 'Уточнюється в чаті').trim(),
            description: els.meetingFormDescription.value.trim(),
            date,
            time: els.meetingFormTime.value || '18:00',
        };
        if (els.meetingFormError) {
            els.meetingFormError.hidden = true;
            els.meetingFormError.textContent = '';
        }
        if (!date) {
            if (els.meetingFormError) {
                els.meetingFormError.textContent = 'Вкажіть дату зустрічі.';
                els.meetingFormError.hidden = false;
            }
            return;
        }
        try {
            const url = meetingId ? API.meetingEdit(meetingId) : API.meetingCreate;
            const data = await apiFetch(url, {
                method: 'POST',
                body: JSON.stringify(payload),
            });
            state.myMeeting = data.meeting;
            updateMeetingSidebarButtons();
            closeMeetingOverlays();
            loadDialogs();
        } catch (err) {
            if (els.meetingFormError) {
                els.meetingFormError.textContent = err.message || 'Помилка збереження.';
                els.meetingFormError.hidden = false;
            }
        }
    }

    async function confirmCancelMeeting() {
        if (!state.myMeeting) return;
        try {
            await apiFetch(API.meetingCancel(state.myMeeting.id), { method: 'POST' });
            if (Number(state.activeMeetingId) === Number(state.myMeeting.id)) {
                closeChat();
            }
            state.myMeeting = null;
            updateMeetingSidebarButtons();
            closeMeetingOverlays();
            loadDialogs();
        } catch (err) {
            window.alert(err.message || 'Не вдалося скасувати зустріч.');
        }
    }

    async function leaveActiveMeeting() {
        if (!state.activeMeetingId) return;
        try {
            await apiFetch(API.meetingLeave(state.activeMeetingId), { method: 'POST' });
            closeChat();
            loadDialogs();
        } catch (err) {
            window.alert(err.message || 'Не вдалося вийти із зустрічі.');
        }
    }

    function setMode(mode, { silent } = {}) {
        state.mode = mode;
        els.modeSwitch.dataset.active = mode;
        els.modeButtons.forEach((btn) => {
            const active = btn.dataset.mode === mode;
            btn.setAttribute('aria-selected', active ? 'true' : 'false');
        });
        applyModeChrome(mode);
        closeChat();
        loadMatches();
        loadDialogs();
        loadNextCandidate();
        if (!silent) {
            history.replaceState(null, '', `?mode=${mode}`);
        }
    }

    els.modeButtons.forEach((btn) => {
        btn.addEventListener('click', () => {
            if (btn.dataset.mode !== state.mode) {
                setMode(btn.dataset.mode);
            }
        });
    });

    if (els.createMeetingBtn) {
        els.createMeetingBtn.addEventListener('click', () => openMeetingForm(null));
    }
    if (els.editMeetingBtn) {
        els.editMeetingBtn.addEventListener('click', () => {
            if (state.myMeeting) openMeetingForm(state.myMeeting);
        });
    }
    if (els.cancelMeetingBtn) {
        els.cancelMeetingBtn.addEventListener('click', () => {
            closeMeetingOverlays();
            if (els.meetingConfirmOverlay) {
                els.meetingConfirmOverlay.hidden = false;
                syncMeetingOpenClass();
            }
        });
    }
    if (els.meetingForm) {
        els.meetingForm.addEventListener('submit', submitMeetingForm);
    }
    if (els.meetingFormDayTrigger && els.meetingFormMonthTrigger) {
        initMeetingSelect('day');
        initMeetingSelect('month');
        document.addEventListener('click', (evt) => {
            if (!evt.target.closest('.meeting-form__select')) {
                closeMeetingSelectMenus();
            }
        });
    }
    if (els.meetingFormPhoto && els.meetingFormPhotoPreview) {
        els.meetingFormPhoto.addEventListener('change', () => {
            const file = els.meetingFormPhoto.files && els.meetingFormPhoto.files[0];
            if (!file) {
                clearMeetingPhotoPreview();
                return;
            }
            const url = URL.createObjectURL(file);
            els.meetingFormPhotoPreview.style.backgroundImage = `url("${url}")`;
            els.meetingFormPhotoPreview.classList.add('has-preview');
        });
    }
    if (els.meetingConfirmYes) {
        els.meetingConfirmYes.addEventListener('click', confirmCancelMeeting);
    }
    document.querySelectorAll('[data-meeting-close]').forEach((el) => {
        el.addEventListener('click', closeMeetingOverlays);
    });
    document.addEventListener('keydown', (evt) => {
        if (evt.key !== 'Escape') return;
        if (document.querySelector('.meeting-form__select.is-open')) {
            closeMeetingSelectMenus();
            return;
        }
        if (
            (els.meetingFormOverlay && !els.meetingFormOverlay.hidden)
            || (els.meetingViewOverlay && !els.meetingViewOverlay.hidden)
            || (els.meetingConfirmOverlay && !els.meetingConfirmOverlay.hidden)
        ) {
            closeMeetingOverlays();
        }
    });

    async function loadMatches() {
        try {
            const data = await apiFetch(API.matches(state.mode));
            renderMatches(data.matches || []);
        } catch (err) {
            console.error('Не вдалося завантажити метчі', err);
        }
    }

    function renderMatches(matches) {
        const grid = els.matchesGrid;
        grid.innerHTML = '';
        grid.classList.remove('is-expanded');
        if (els.matchesMore) {
            const visibleLimit = state.mode === 'bff' ? 4 : 8;
            els.matchesMore.hidden = matches.length <= visibleLimit;
            els.matchesMore.setAttribute('aria-expanded', 'false');
        }
        if (!matches.length) {
            const empty = document.createElement('p');
            empty.className = 'panel__empty';
            empty.textContent = 'У вас поки немає метчів';
            grid.appendChild(empty);
            return;
        }
        matches.forEach((match) => {
            const item = document.createElement('div');
            item.className = 'match-item';
            item.dataset.matchId = String(match.match_id);
            if (match.match_id === state.activeMatchId) {
                item.classList.add('is-active');
            }

            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'match-avatar';
            btn.title = `${match.display_name}${match.age ? ', ' + match.age : ''}`;
            btn.innerHTML = `
                <img class="match-avatar__img" src="${match.avatar_url || avatarPlaceholder()}" alt="${escapeHtml(match.display_name)}">
            `;
            btn.addEventListener('click', () => openConversationByMatch(match));

            const unmatchBtn = document.createElement('button');
            unmatchBtn.type = 'button';
            unmatchBtn.className = 'match-unmatch';
            unmatchBtn.setAttribute('aria-label', `Анметч ${match.display_name}`);
            unmatchBtn.innerHTML = '<span aria-hidden="true">×</span><span class="match-unmatch__tip" aria-hidden="true">Анметч</span>';
            unmatchBtn.addEventListener('click', (event) => {
                event.preventDefault();
                event.stopPropagation();
                unmatchPerson(match);
            });

            item.append(btn, unmatchBtn);
            grid.appendChild(item);
        });
    }

    /** Прибирає метч і діалог у обох; оновлює списки без зсуву сітки. */
    async function unmatchPerson(match) {
        if (!match || !match.match_id) {
            return;
        }
        try {
            await apiFetch(API.unmatch(match.match_id), { method: 'POST' });
        } catch (err) {
            console.error('Не вдалося анметчнути', err);
            return;
        }
        if (
            state.activeMatchId === match.match_id
            || Number(state.conversationId) === Number(match.conversation_id)
        ) {
            closeChat();
        }
        loadMatches();
        loadDialogs();
    }

    if (els.matchesMore) {
        els.matchesMore.addEventListener('click', () => {
            const expanded = els.matchesGrid.classList.toggle('is-expanded');
            els.matchesMore.setAttribute('aria-expanded', expanded ? 'true' : 'false');
        });
    }

    async function loadDialogs() {
        try {
            const data = await apiFetch(API.conversations(state.mode));
            renderDialogs(data.conversations || []);
        } catch (err) {
            console.error('Не вдалося завантажити діалоги', err);
        }
    }

    function renderDialogs(dialogs) {
        const list = els.dialogsList;
        list.innerHTML = '';
        if (!dialogs.length) {
            const empty = document.createElement('p');
            empty.className = 'panel__empty';
            empty.textContent = 'Екран готовий до довгих діалогів. Залишилося знайти взаємну симпатію та увімкнути цей чат на максимум';
            list.appendChild(empty);
            return;
        }
        dialogs.forEach((dialog) => {
            const item = document.createElement('button');
            item.type = 'button';
            item.className = 'dialog-item';
            item.dataset.conversationId = dialog.conversation_id;
            if (dialog.unread_count > 0) item.classList.add('has-unread');
            if (dialog.conversation_id === state.conversationId) item.classList.add('is-active');

            let metaRight = `<span class="dialog-item__time">${escapeHtml(dialog.last_message_time || '')}</span>`;
            if (dialog.unread_count > 0) {
                metaRight += `<span class="dialog-item__badge">${dialog.unread_count}</span>`;
            } else if (dialog.last_message_is_mine) {
                metaRight = `
                    <span class="dialog-item__meta-top">
                        <svg class="dialog-item__read" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                            <path d="M2 12l5 5L14 8" stroke="#8C8C8C" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
                            ${dialog.last_message_is_read ? '<path d="M9 12l5 5L22 8" stroke="#8C8C8C" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>' : ''}
                        </svg>
                        <span class="dialog-item__time">${escapeHtml(dialog.last_message_time || '')}</span>
                    </span>
                `;
            }

            item.innerHTML = `
                <img class="dialog-item__avatar" src="${dialog.avatar_url || avatarPlaceholder()}" alt="">
                <span class="dialog-item__name">${escapeHtml(dialog.other_display_name)}${dialog.other_age ? ' ' + dialog.other_age : ''}</span>
                ${metaRight}
                <span class="dialog-item__preview">${escapeHtml(dialog.last_message_preview) || 'Скажіть привіт!'}</span>
            `;
            item.addEventListener('click', () => {
                state.activeMatchId = dialog.match_id || null;
                state.activeMeetingId = dialog.meeting_id || null;
                openChat(dialog.conversation_id, {
                    displayName: dialog.other_display_name,
                    age: dialog.other_age,
                    avatarUrl: dialog.avatar_url,
                    kind: dialog.kind || 'match',
                    meetingId: dialog.meeting_id || null,
                });
            });
            list.appendChild(item);
        });
    }

    function bumpDialogPreview(conversationId, preview, timeLabel, senderId) {
        const cached = Array.from(els.dialogsList.querySelectorAll('.dialog-item'));
        const match = cached.find((el) => Number(el.dataset.conversationId) === Number(conversationId));
        const isMine = senderId === state.myUserId;
        const isOpenChat = state.conversationId === Number(conversationId);
        if (match) {
            const previewEl = match.querySelector('.dialog-item__preview');
            const timeEl = match.querySelector('.dialog-item__time');
            if (previewEl) previewEl.textContent = preview;
            if (timeEl) timeEl.textContent = timeLabel;
            if (!isMine && !isOpenChat) {
                match.classList.add('has-unread');
                let badge = match.querySelector('.dialog-item__badge');
                if (!badge) {
                    badge = document.createElement('span');
                    badge.className = 'dialog-item__badge';
                    badge.textContent = '1';
                    match.appendChild(badge);
                } else {
                    badge.textContent = String((parseInt(badge.textContent, 10) || 0) + 1);
                }
            }
            els.dialogsList.prepend(match);
        } else {
            loadDialogs();
        }
    }

    function resetCardTransform() {
        els.swipeCard.classList.remove('is-dragging', 'is-returning', 'is-leaving-like', 'is-leaving-dislike');
        els.swipeCard.style.transform = '';
        els.swipeCard.style.opacity = '';
    }

    function flyCardOut(isPositive) {
        return new Promise((resolve) => {
            els.swipeCard.classList.remove('is-dragging', 'is-returning');
            void els.swipeCard.offsetWidth; // reflow — щоб transition спрацював, навіть якщо драгу не було
            els.swipeCard.classList.add(isPositive ? 'is-leaving-like' : 'is-leaving-dislike');
            let settled = false;
            const finish = () => {
                if (settled) return;
                settled = true;
                els.swipeCard.removeEventListener('transitionend', finish);
                resolve();
            };
            els.swipeCard.addEventListener('transitionend', finish);
            setTimeout(finish, 360);
        });
    }

    async function triggerSwipe(isPositive) {
        if (state.animating || state.swipeLocked || !state.activeCandidateUserId) return;
        state.animating = true;
        await flyCardOut(isPositive);
        state.animating = false;
        swipe(isPositive);
    }

    const cardDrag = { dragging: false, pointerId: null, startX: 0, currentX: 0, moved: false };

    function onCardPointerDown(event) {
        if (!event.isPrimary || !state.activeCandidateUserId || state.animating || state.swipeLocked) return;
        cardDrag.dragging = true;
        cardDrag.moved = false;
        cardDrag.pointerId = event.pointerId;
        cardDrag.startX = event.clientX;
        cardDrag.currentX = 0;
        if (els.swipeCard.setPointerCapture) {
            try { els.swipeCard.setPointerCapture(event.pointerId); } catch (e) { /* курсор уже відпущено */ }
        }
    }

    function onCardPointerMove(event) {
        if (!cardDrag.dragging || event.pointerId !== cardDrag.pointerId) return;
        cardDrag.currentX = event.clientX - cardDrag.startX;
        if (Math.abs(cardDrag.currentX) < SWIPE_MOVE_DEADZONE) return;
        if (!cardDrag.moved) {
            cardDrag.moved = true;
            els.swipeCard.classList.add('is-dragging');
        }
        event.preventDefault();
        els.swipeCard.style.transform = `translate3d(${cardDrag.currentX}px, 0, 0) rotate(${cardDrag.currentX * 0.045}deg)`;
    }

    function onCardPointerUp(event) {
        if (!cardDrag.dragging || event.pointerId !== cardDrag.pointerId) return;
        cardDrag.dragging = false;
        cardDrag.pointerId = null;
        els.swipeCard.classList.remove('is-dragging');

        if (!cardDrag.moved) return;

        state.cardWasDragged = true;
        const draggedX = cardDrag.currentX;
        cardDrag.currentX = 0;

        if (Math.abs(draggedX) > SWIPE_DRAG_THRESHOLD) {
            triggerSwipe(draggedX > 0);
        } else {
            els.swipeCard.classList.add('is-returning');
            els.swipeCard.style.transform = '';
        }
    }

    els.swipeCard.addEventListener('pointerdown', onCardPointerDown);
    els.swipeCard.addEventListener('pointermove', onCardPointerMove);
    els.swipeCard.addEventListener('pointerup', onCardPointerUp);
    els.swipeCard.addEventListener('pointercancel', onCardPointerUp);

    async function loadNextCandidate() {
        state.swipeLocked = false;
        resetCardTransform();
        closeFullProfile();
        els.swipeCard.classList.remove('is-empty');
        els.swipeCard.innerHTML = '<div class="swipe-card__placeholder"><p>Завантаження…</p></div>';
        els.swipeActions.hidden = true;
        if (els.expandProfileBtn) els.expandProfileBtn.hidden = true;
        try {
            const data = await apiFetch(API.discover(state.mode));
            renderCandidate(data.candidate);
        } catch (err) {
            try {
                const data = await apiFetch(API.discover(state.mode));
                renderCandidate(data.candidate);
            } catch (retryErr) {
                els.swipeCard.classList.add('is-empty');
                els.swipeCard.innerHTML = `<div class="swipe-card__placeholder"><p>${escapeHtml(retryErr.message)}</p></div>`;
            }
        }
    }

    function renderCandidateTags(tags, limit) {
        if (!tags || !tags.length) return '';
        const visible = Number.isFinite(limit) ? tags.slice(0, limit) : tags;
        const chips = visible.map((tag) => {
            const label = tag.level ? `${tag.name} · ${tag.level}` : tag.name;
            const sharedClass = tag.is_shared ? ' swipe-card__tag--shared' : '';
            return `<span class="swipe-card__tag${sharedClass}">${escapeHtml(label)}</span>`;
        }).join('');
        return `<div class="swipe-card__tags">${chips}</div>`;
    }

    function renderCandidate(candidate) {
        closeFullProfile();
        if (!candidate) {
            state.activeCandidateUserId = null;
            state.activeCandidate = null;
            els.swipeActions.hidden = true;
            if (els.expandProfileBtn) els.expandProfileBtn.hidden = true;
            els.swipeCard.classList.add('is-empty');
            els.swipeCard.innerHTML = '<div class="swipe-card__placeholder"><p>Анкети закінчилися<br>Спробуйте пізніше</p></div>';
            return;
        }
        state.activeCandidateUserId = candidate.user_id;
        state.activeCandidate = candidate;
        els.swipeCard.classList.remove('is-empty');
        const photos = candidate.photos && candidate.photos.length ? candidate.photos : [avatarPlaceholder()];
        const dots = photos.map((_, idx) => `<span class="swipe-card__dot ${idx === 0 ? 'is-active' : ''}"></span>`).join('');

        els.swipeCard.innerHTML = `
            <img class="swipe-card__photo" src="${photos[0]}" alt="${escapeHtml(candidate.display_name)}">
            ${photos.length > 1 ? `<div class="swipe-card__dots">${dots}</div>` : ''}
            <div class="swipe-card__gradient"></div>
            <div class="swipe-card__info">
                <div class="swipe-card__header">
                    <h2 class="swipe-card__name">${escapeHtml(candidate.display_name)} ${candidate.age || ''}</h2>
                    <p class="swipe-card__bio">${escapeHtml(candidate.bio) || (candidate.city ? escapeHtml(candidate.city) : '')}</p>
                </div>
                ${renderCandidateTags(candidate.tags, 3)}
            </div>
            ${candidate.active_meeting_id ? '<button type="button" class="swipe-card__meeting-btn" id="candidate-meeting-btn">Зустріч</button>' : ''}
        `;

        if (photos.length > 1) {
            let current = 0;
            const img = els.swipeCard.querySelector('.swipe-card__photo');
            const dotEls = els.swipeCard.querySelectorAll('.swipe-card__dot');
            img.addEventListener('click', (evt) => {
                if (state.cardWasDragged) {
                    state.cardWasDragged = false;
                    return;
                }
                const rect = img.getBoundingClientRect();
                const isRight = (evt.clientX - rect.left) > rect.width / 2;
                current = isRight
                    ? (current + 1) % photos.length
                    : (current - 1 + photos.length) % photos.length;
                img.src = photos[current];
                dotEls.forEach((dot, idx) => dot.classList.toggle('is-active', idx === current));
            });
        }

        const meetingBtn = els.swipeCard.querySelector('#candidate-meeting-btn');
        if (meetingBtn) {
            meetingBtn.addEventListener('click', (evt) => {
                evt.stopPropagation();
                openMeetingById(candidate.active_meeting_id);
            });
        }

        els.swipeActions.hidden = false;
        if (els.expandProfileBtn) els.expandProfileBtn.hidden = false;
    }

    function openFullProfile() {
        if (!state.activeCandidate || !els.fullProfileOverlay) return;
        renderFullProfile(state.activeCandidate);
        els.fullProfileOverlay.hidden = false;
    }

    function closeFullProfile() {
        if (els.fullProfileOverlay) els.fullProfileOverlay.hidden = true;
    }

    function renderFullProfileChips(tags) {
        if (!tags || !tags.length) return '';
        return tags.map((tag) => {
            const wide = (tag.name || '').length > 14 ? ' full-profile__chip--wide' : '';
            const shared = tag.is_shared ? ' full-profile__chip--shared' : '';
            return `<span class="full-profile__chip${wide}${shared}">${escapeHtml(tag.name)}</span>`;
        }).join('');
    }

    function renderFullProfileSkills(tags) {
        if (!tags || !tags.length) return '';
        const withLevel = tags.filter((tag) => tag.level);
        if (!withLevel.length) return '';
        return withLevel.map((tag) => {
            const label = `${tag.name} — Рівень: ${tag.level}`;
            return `<span class="full-profile__skill">${escapeHtml(label)}</span>`;
        }).join('');
    }

    function formatMeetingDateLong(meeting) {
        if (!meeting || !meeting.starts_at) return meeting?.date || '';
        const date = new Date(meeting.starts_at);
        if (Number.isNaN(date.getTime())) return meeting.date || '';
        return date.toLocaleDateString('uk-UA', { day: 'numeric', month: 'long' });
    }

    function hideFullProfileMeeting() {
        if (!els.fullProfileMeeting) return;
        els.fullProfileMeeting.hidden = true;
        if (els.fullProfileJoinBtn) {
            els.fullProfileJoinBtn.onclick = null;
            els.fullProfileJoinBtn.disabled = false;
            els.fullProfileJoinBtn.textContent = 'Приєднатися до групи та взяти участь у зустрічі';
        }
    }

    async function renderFullProfileMeeting(candidate) {
        hideFullProfileMeeting();
        if (state.mode !== 'bff' || !candidate.active_meeting_id || !els.fullProfileMeeting) return;
        try {
            const data = await apiFetch(API.meetingDetail(candidate.active_meeting_id));
            const meeting = data.meeting;
            if (!meeting) return;
            els.fullProfileMeeting.hidden = false;
            if (els.fullProfileMeetingDate) {
                els.fullProfileMeetingDate.textContent = formatMeetingDateLong(meeting);
            }
            if (els.fullProfileMeetingDesc) {
                els.fullProfileMeetingDesc.textContent = meeting.description || '';
            }
            if (els.fullProfileJoinBtn) {
                if (meeting.can_join) {
                    els.fullProfileJoinBtn.disabled = false;
                    els.fullProfileJoinBtn.textContent = 'Приєднатися до групи та взяти участь у зустрічі';
                    els.fullProfileJoinBtn.onclick = () => {
                        closeFullProfile();
                        joinMeetingAndOpen(meeting.id);
                    };
                } else if (meeting.can_open_chat) {
                    els.fullProfileJoinBtn.disabled = false;
                    els.fullProfileJoinBtn.textContent = 'Відкрити чат зустрічі';
                    els.fullProfileJoinBtn.onclick = () => {
                        closeFullProfile();
                        openMeetingChat(meeting);
                    };
                } else {
                    els.fullProfileJoinBtn.disabled = true;
                    els.fullProfileJoinBtn.textContent = 'Зустріч недоступна';
                    els.fullProfileJoinBtn.onclick = null;
                }
            }
        } catch (err) {
            console.error('Не вдалося завантажити зустріч профілю', err);
            hideFullProfileMeeting();
        }
    }

    function renderFullProfile(candidate) {
        const photos = candidate.photos && candidate.photos.length ? candidate.photos : [avatarPlaceholder()];

        els.fullProfileMainPhoto.src = photos[0];
        els.fullProfileMainPhoto.alt = candidate.display_name || '';

        els.fullProfileThumbs.innerHTML = '';
        if (photos.length > 1) {
            photos.forEach((src, idx) => {
                const thumb = document.createElement('button');
                thumb.type = 'button';
                thumb.className = `full-profile__thumb${idx === 0 ? ' is-active' : ''}`;
                thumb.innerHTML = `<img src="${src}" alt="">`;
                thumb.addEventListener('click', () => {
                    els.fullProfileMainPhoto.src = src;
                    els.fullProfileThumbs.querySelectorAll('.full-profile__thumb').forEach((el, i) => {
                        el.classList.toggle('is-active', i === idx);
                    });
                });
                els.fullProfileThumbs.appendChild(thumb);
            });
        }

        const nameParts = ['Профіль', candidate.display_name || '', candidate.age || '']
            .filter((part) => part !== '' && part !== null && part !== undefined);
        els.fullProfileName.textContent = nameParts.join(' ');
        els.fullProfileCity.textContent = candidate.city || '';

        if (els.fullProfileMeta) {
            const meta = [];
            if (candidate.city) meta.push(candidate.city);
            els.fullProfileMeta.innerHTML = meta
                .map((label) => `<span class="full-profile__meta-chip">${escapeHtml(label)}</span>`)
                .join('');
        }

        els.fullProfileBio.textContent = candidate.bio || 'Користувач ще не додав опис профілю.';
        els.fullProfileTags.innerHTML = renderFullProfileChips(candidate.tags);

        if (els.fullProfileSkills) {
            if (state.mode === 'bff') {
                const skillsHtml = renderFullProfileSkills(candidate.tags);
                els.fullProfileSkills.innerHTML = skillsHtml;
                els.fullProfileSkills.hidden = !skillsHtml;
            } else {
                els.fullProfileSkills.innerHTML = '';
                els.fullProfileSkills.hidden = true;
            }
        }

        renderFullProfileMeeting(candidate);
    }

    if (els.expandProfileBtn) {
        els.expandProfileBtn.addEventListener('click', openFullProfile);
    }
    if (els.fullProfileClose) {
        els.fullProfileClose.addEventListener('click', closeFullProfile);
    }
    if (els.fullProfileBackdrop) {
        els.fullProfileBackdrop.addEventListener('click', closeFullProfile);
    }
    document.addEventListener('keydown', (evt) => {
        if (evt.key === 'Escape' && els.fullProfileOverlay && !els.fullProfileOverlay.hidden) {
            closeFullProfile();
        }
    });

    async function swipe(isPositive) {
        if (state.swipeLocked || !state.activeCandidateUserId) return;
        state.swipeLocked = true;
        const toUserId = state.activeCandidateUserId;
        try {
            const data = await apiFetch(API.like, {
                method: 'POST',
                body: JSON.stringify({ to_user_id: toUserId, mode: state.mode, is_positive: isPositive }),
            });
            if (data.match) {
                loadMatches();
                loadDialogs();
                showMatchToast();
            }
        } catch (err) {
            console.error('Не вдалося зберегти свайп', err);
        } finally {
            loadNextCandidate();
        }
    }

    els.likeBtn.addEventListener('click', () => triggerSwipe(true));
    els.dislikeBtn.addEventListener('click', () => triggerSwipe(false));

    function showMatchToast() {
        const toast = document.createElement('div');
        toast.textContent = "Це метч! 💜 Тепер ви можете написати одне одному";
        Object.assign(toast.style, {
            position: 'fixed', left: '50%', top: '24px', transform: 'translateX(-50%)',
            background: '#9747FF', color: '#fff', padding: '12px 22px', borderRadius: '999px',
            fontFamily: 'var(--font-body)', fontWeight: '700', zIndex: 999, boxShadow: '0 10px 30px rgba(151,71,255,.4)',
        });
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 3200);
    }

    async function openConversationByMatch(match) {
        state.activeMatchId = match.match_id;
        if (match.conversation_id) {
            openChat(match.conversation_id, {
                displayName: match.display_name,
                age: match.age,
                avatarUrl: match.avatar_url,
            });
            return;
        }
        try {
            const data = await apiFetch(API.conversationOpen, {
                method: 'POST',
                body: JSON.stringify({ match_id: match.match_id }),
            });
            openChat(data.conversation_id, {
                displayName: match.display_name,
                age: match.age,
                avatarUrl: match.avatar_url,
            });
        } catch (err) {
            console.error('Не вдалося відкрити чат', err);
        }
    }

    async function openChat(conversationId, hint) {
        closeWebSocket();
        state.conversationId = conversationId;
        state.chatKind = (hint && hint.kind) || 'match';
        if (hint && hint.meetingId) {
            state.activeMeetingId = hint.meetingId;
        }
        highlightActiveDialog(conversationId);

        body.classList.add('is-chat-open');
        els.discoverView.hidden = true;
        els.chatView.hidden = false;
        els.chatMessages.innerHTML = '<p class="chat-empty-state">Завантаження історії…</p>';
        if (hint) {
            els.chatPartnerName.textContent = `${hint.displayName || ''}${hint.age ? ' ' + hint.age : ''}`;
            if (hint.avatarUrl) {
                els.chatPartnerAvatar.src = hint.avatarUrl;
                els.chatPartnerAvatar.hidden = false;
            } else if (hint.kind === 'meeting') {
                els.chatPartnerAvatar.hidden = true;
            }
        }
        try {
            const data = await apiFetch(API.conversationMessages(conversationId));
            state.chatKind = data.kind || state.chatKind;
            state.activeMeetingId = data.meeting_id || state.activeMeetingId;
            state.activeMatchId = data.match_id || state.activeMatchId;
            els.chatPartnerName.textContent = `${data.other_user.display_name}${data.other_user.age ? ' ' + data.other_user.age : ''}`;
            if (data.kind === 'meeting') {
                els.chatPartnerAvatar.hidden = true;
                els.chatPartnerStatus.textContent = data.is_chat_open ? 'Груповий чат зустрічі' : 'Чат закрито';
            } else {
                els.chatPartnerAvatar.src = data.other_user.avatar_url || avatarPlaceholder();
                els.chatPartnerAvatar.hidden = false;
                els.chatPartnerStatus.textContent = state.mode === 'dating' ? 'Романтика' : 'Дружба';
            }
            if (els.chatUnmatchBtn) {
                els.chatUnmatchBtn.hidden = data.kind === 'meeting';
            }
            if (els.chatLeaveMeetingBtn) {
                els.chatLeaveMeetingBtn.hidden = !(data.kind === 'meeting' && !data.is_creator);
            }
            renderMessages(data.messages || []);
            connectWebSocket(conversationId);
            apiFetch(API.conversationRead(conversationId), { method: 'POST' }).then(loadDialogs).catch(() => {});
        } catch (err) {
            els.chatMessages.innerHTML = `<p class="chat-empty-state">${escapeHtml(err.message)}</p>`;
        }
    }

    function closeChat() {
        commitPendingDelete();
        closeWebSocket();
        closeLightbox();
        hideMsgMenu();
        hideChatMoreMenu();
        cancelEditMessage();
        clearPendingPhoto();
        state.conversationId = null;
        state.activeMatchId = null;
        state.activeMeetingId = null;
        state.chatKind = 'match';
        body.classList.remove('is-chat-open');
        els.chatView.hidden = true;
        els.discoverView.hidden = false;
        els.chatMessages.innerHTML = '';
        highlightActiveDialog(null);
        if (els.chatUnmatchBtn) els.chatUnmatchBtn.hidden = false;
        if (els.chatLeaveMeetingBtn) els.chatLeaveMeetingBtn.hidden = true;
    }

    els.chatBackBtn.addEventListener('click', closeChat);

    function highlightActiveDialog(conversationId) {
        els.dialogsList.querySelectorAll('.dialog-item').forEach((el) => {
            el.classList.toggle('is-active', Number(el.dataset.conversationId) === Number(conversationId));
        });
    }

    function messageDayKey(message) {
        if (!message.created_at) return 'today';
        const date = new Date(message.created_at);
        if (Number.isNaN(date.getTime())) return 'today';
        return `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;
    }

    function messageDayLabel(message) {
        if (!message.created_at) return 'Сьогодні';
        const date = new Date(message.created_at);
        if (Number.isNaN(date.getTime())) return 'Сьогодні';
        const today = new Date();
        const sameDay = (a, b) => (
            a.getFullYear() === b.getFullYear()
            && a.getMonth() === b.getMonth()
            && a.getDate() === b.getDate()
        );
        if (sameDay(date, today)) return 'Сьогодні';
        const yesterday = new Date(today);
        yesterday.setDate(today.getDate() - 1);
        if (sameDay(date, yesterday)) return 'Вчора';
        const day = String(date.getDate()).padStart(2, '0');
        const month = String(date.getMonth() + 1).padStart(2, '0');
        return `${day}.${month}.${date.getFullYear()}`;
    }

    function lastRenderedDayKey() {
        const chips = els.chatMessages.querySelectorAll('.msg-date-chip');
        return chips.length ? chips[chips.length - 1].dataset.dayKey : null;
    }

    function ensureDateChip(message) {
        const key = messageDayKey(message);
        if (lastRenderedDayKey() === key) return;
        const chip = document.createElement('div');
        chip.className = 'msg-date-chip';
        chip.dataset.dayKey = key;
        chip.textContent = messageDayLabel(message);
        els.chatMessages.appendChild(chip);
    }

    function renderMessages(messages) {
        els.chatMessages.innerHTML = '';
        if (!messages.length) {
            els.chatMessages.innerHTML = '<p class="chat-empty-state">Немає повідомлень. Напишіть перше!</p>';
            return;
        }
        messages.forEach(appendMessage);
        scrollMessagesToBottom();
    }

    function messagePreviewText(message) {
        const text = (message.text || '').trim();
        if (text) return text;
        if (message.image_url) return '📷 Фото';
        return '';
    }

    function fillMessageBubble(bubble, message) {
        const hasImage = Boolean(message.image_url);
        bubble.className = `msg ${message.is_mine ? 'msg--mine' : 'msg--theirs'}${hasImage ? ' msg--image' : ''}`;
        bubble.dataset.messageId = String(message.id);
        bubble.dataset.text = message.text || '';
        bubble.dataset.hasImage = hasImage ? '1' : '0';
        if (message.time_label) bubble.dataset.timeLabel = message.time_label;
        const checkStroke = '#E7D5FF';
        const checkIcon = message.is_mine
            ? `<svg width="17" height="17" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M2 12l5 5L14 8" stroke="${checkStroke}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>${message.is_read ? `<path d="M9 12l5 5L22 8" stroke="${checkStroke}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>` : ''}</svg>`
            : '';
        const editedHtml = message.is_edited ? '<span class="msg__edited">ред.</span>' : '';
        const imageHtml = hasImage
            ? `<button type="button" class="msg__image-btn" data-image-url="${escapeHtml(message.image_url)}"><img class="msg__image" src="${escapeHtml(message.image_url)}" alt="Фото"></button>`
            : '';
        const textHtml = (message.text || '').trim()
            ? `<span class="msg__text">${escapeHtml(message.text)}</span>`
            : '';
        bubble.innerHTML = `
            ${imageHtml}
            ${textHtml}
            <span class="msg__meta">${editedHtml}${escapeHtml(message.time_label || '')}${checkIcon}</span>
        `;
    }

    function appendMessage(message) {
        if (message.id && els.chatMessages.querySelector(`[data-message-id="${message.id}"]`)) {
            return;
        }
        if (els.chatMessages.querySelector('.chat-empty-state')) {
            els.chatMessages.innerHTML = '';
        }
        ensureDateChip(message);
        const bubble = document.createElement('div');
        fillMessageBubble(bubble, message);
        els.chatMessages.appendChild(bubble);
        scrollMessagesToBottom();
    }

    function updateMessageBubble(message) {
        const bubble = els.chatMessages.querySelector(`[data-message-id="${message.id}"]`);
        if (!bubble) return;
        fillMessageBubble(bubble, Object.assign({}, message, {
            time_label: message.time_label || bubble.dataset.timeLabel || '',
            is_mine: message.is_mine !== undefined ? message.is_mine : bubble.classList.contains('msg--mine'),
        }));
    }

    function removeMessageBubble(messageId) {
        const bubble = els.chatMessages.querySelector(`[data-message-id="${messageId}"]`);
        if (!bubble) return;
        const prev = bubble.previousElementSibling;
        bubble.remove();
        if (prev && prev.classList.contains('msg-date-chip')) {
            const next = prev.nextElementSibling;
            if (!next || next.classList.contains('msg-date-chip')) {
                prev.remove();
            }
        }
        if (!els.chatMessages.querySelector('.msg')) {
            els.chatMessages.innerHTML = '<p class="chat-empty-state">Немає повідомлень. Напишіть перше!</p>';
        }
    }

    function viewportToFramePoint(clientX, clientY) {
        const frame = document.querySelector('.crush-frame');
        if (!frame) return { x: clientX, y: clientY };
        const rect = frame.getBoundingClientRect();
        const frameW = parseFloat(frame.getAttribute('data-frame-w')) || 1920;
        const frameH = parseFloat(frame.getAttribute('data-frame-h')) || 1080;
        if (!rect.width || !rect.height) return { x: clientX, y: clientY };
        return {
            x: ((clientX - rect.left) / rect.width) * frameW,
            y: ((clientY - rect.top) / rect.height) * frameH,
        };
    }

    function hideMsgMenu() {
        if (!els.msgMenu) return;
        els.msgMenu.hidden = true;
        state.menuMessageId = null;
    }

    function hideChatMoreMenu() {
        if (els.chatMoreMenu) els.chatMoreMenu.hidden = true;
        if (els.chatMoreBtn) els.chatMoreBtn.setAttribute('aria-expanded', 'false');
    }

    function toggleChatMoreMenu() {
        if (!els.chatMoreMenu || !els.chatMoreBtn) return;
        hideMsgMenu();
        const willOpen = els.chatMoreMenu.hidden;
        els.chatMoreMenu.hidden = !willOpen;
        els.chatMoreBtn.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
    }

    function showMsgMenu(event, bubble) {
        if (!els.msgMenu) return;
        const hasText = Boolean((bubble.dataset.text || '').trim());
        const editBtn = els.msgMenu.querySelector('[data-action="edit"]');
        if (editBtn) editBtn.hidden = !hasText;
        state.menuMessageId = bubble.dataset.messageId;
        els.msgMenu.hidden = false;
        const point = viewportToFramePoint(event.clientX, event.clientY);
        const menuW = els.msgMenu.offsetWidth || 176;
        const menuH = els.msgMenu.offsetHeight || 88;
        const frameW = 1920;
        const frameH = 1080;
        let left = point.x;
        let top = point.y;
        if (left + menuW > frameW - 16) left = frameW - menuW - 16;
        if (top + menuH > frameH - 16) top = point.y - menuH;
        if (left < 16) left = 16;
        if (top < 16) top = 16;
        els.msgMenu.style.left = `${Math.round(left)}px`;
        els.msgMenu.style.top = `${Math.round(top)}px`;
    }

    function cancelEditMessage() {
        state.editingMessageId = null;
        if (els.chatEditBar) els.chatEditBar.hidden = true;
        if (els.chatEditPreview) els.chatEditPreview.textContent = '';
        if (els.chatForm) els.chatForm.classList.remove('is-editing');
        if (els.chatInput && !state.pendingPhoto) {
            els.chatInput.placeholder = 'Написати повідомлення..';
        }
    }

    function startEditMessage(bubble) {
        const text = bubble.dataset.text || '';
        if (!text.trim()) return;
        hideMsgMenu();
        if (Number(state.pendingDeleteMessageId) === Number(bubble.dataset.messageId)) {
            undoPendingDelete();
        }
        clearPendingPhoto();
        state.editingMessageId = bubble.dataset.messageId;
        if (els.chatEditPreview) els.chatEditPreview.textContent = text;
        if (els.chatEditBar) els.chatEditBar.hidden = false;
        if (els.chatForm) els.chatForm.classList.add('is-editing');
        if (els.chatInput) {
            els.chatInput.value = text;
            els.chatInput.placeholder = 'Змінити повідомлення..';
            els.chatInput.focus();
            els.chatInput.setSelectionRange(text.length, text.length);
        }
    }

    async function saveEditedMessage() {
        const messageId = state.editingMessageId;
        const text = els.chatInput.value.trim();
        if (!messageId || !text || !state.conversationId) return;
        try {
            const data = await apiFetch(
                API.conversationEditMessage(state.conversationId, messageId),
                { method: 'POST', body: JSON.stringify({ text }) },
            );
            if (data.message) updateMessageBubble(data.message);
            els.chatInput.value = '';
            cancelEditMessage();
        } catch (err) {
            alert(err.message);
        }
    }

    function updateUndoBar() {
        if (els.chatUndoSeconds) {
            els.chatUndoSeconds.textContent = String(Math.max(0, state.deleteSecondsLeft));
        }
    }

    function hideUndoBar() {
        if (els.chatUndoBar) els.chatUndoBar.hidden = true;
        if (els.chatForm) els.chatForm.classList.remove('is-undoing');
    }

    function clearDeleteTimer() {
        if (state.deleteTimerId) {
            clearTimeout(state.deleteTimerId);
            state.deleteTimerId = null;
        }
        if (state.deleteTickId) {
            clearInterval(state.deleteTickId);
            state.deleteTickId = null;
        }
    }

    function undoPendingDelete() {
        clearDeleteTimer();
        state.pendingDeleteMessageId = null;
        state.pendingDeleteConversationId = null;
        state.deleteSecondsLeft = 0;
        hideUndoBar();
    }

    function commitPendingDelete() {
        const messageId = state.pendingDeleteMessageId;
        const conversationId = state.pendingDeleteConversationId;
        clearDeleteTimer();
        hideUndoBar();
        state.pendingDeleteMessageId = null;
        state.pendingDeleteConversationId = null;
        state.deleteSecondsLeft = 0;
        if (!messageId || !conversationId) return;
        if (Number(state.editingMessageId) === Number(messageId)) {
            els.chatInput.value = '';
            cancelEditMessage();
        }
        apiFetch(
            API.conversationDeleteMessage(conversationId, messageId),
            { method: 'POST' },
        ).then(() => {
            if (Number(state.conversationId) === Number(conversationId)) {
                removeMessageBubble(messageId);
            }
            loadDialogs();
        }).catch((err) => {
            alert(err.message);
        });
    }

    function scheduleDelete(messageId) {
        if (!messageId || !state.conversationId) return;
        hideMsgMenu();
        if (
            state.pendingDeleteMessageId
            && Number(state.pendingDeleteMessageId) !== Number(messageId)
        ) {
            commitPendingDelete();
        }
        if (Number(state.editingMessageId) === Number(messageId)) {
            els.chatInput.value = '';
            cancelEditMessage();
        }
        state.pendingDeleteMessageId = messageId;
        state.pendingDeleteConversationId = state.conversationId;
        state.deleteSecondsLeft = 5;
        updateUndoBar();
        if (els.chatUndoBar) els.chatUndoBar.hidden = false;
        if (els.chatForm) els.chatForm.classList.add('is-undoing');
        clearDeleteTimer();
        state.deleteTickId = setInterval(() => {
            state.deleteSecondsLeft -= 1;
            updateUndoBar();
            if (state.deleteSecondsLeft <= 0) {
                clearInterval(state.deleteTickId);
                state.deleteTickId = null;
            }
        }, 1000);
        state.deleteTimerId = setTimeout(commitPendingDelete, 5000);
    }

    function scrollMessagesToBottom() {
        els.chatMessages.scrollTop = els.chatMessages.scrollHeight;
    }

    function connectWebSocket(conversationId) {
        const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
        const ws = new WebSocket(`${proto}://${window.location.host}/ws/chat/${conversationId}/`);
        state.ws = ws;

        ws.onopen = () => {
            state.wsReconnectAttempts = 0;
        };

        ws.onmessage = (event) => {
            let payload;
            try {
                payload = JSON.parse(event.data);
            } catch (e) {
                return;
            }
            handleWsEvent(payload);
        };

        ws.onclose = (event) => {
            if (state.ws !== ws) return;
            state.ws = null;
            if (event.code === 4001 || event.code === 4003) {
                els.chatPartnerStatus.textContent = 'Немає доступу до чату';
                return;
            }
            if (state.conversationId === conversationId && state.wsReconnectAttempts < 5) {
                state.wsReconnectAttempts += 1;
                setTimeout(() => {
                    if (state.conversationId === conversationId) connectWebSocket(conversationId);
                }, 1000 * state.wsReconnectAttempts);
            }
        };

        ws.onerror = () => {
            els.chatPartnerStatus.textContent = "Проблема зі з'єднанням…";
        };
    }

    function closeWebSocket() {
        if (state.ws) {
            const ws = state.ws;
            state.ws = null;
            ws.close(1000);
        }
    }

    function connectInboxSocket() {
        const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
        const ws = new WebSocket(`${proto}://${window.location.host}/ws/inbox/`);
        state.inboxWs = ws;

        ws.onopen = () => {
            state.inboxReconnectAttempts = 0;
        };

        ws.onmessage = (event) => {
            let payload;
            try {
                payload = JSON.parse(event.data);
            } catch (e) {
                return;
            }
            handleWsEvent(payload);
        };

        ws.onclose = (event) => {
            if (state.inboxWs !== ws) return;
            state.inboxWs = null;
            if (event.code === 4001) return;
            state.inboxReconnectAttempts += 1;
            const delay = Math.min(1000 * state.inboxReconnectAttempts, 10000);
            setTimeout(connectInboxSocket, delay);
        };

        ws.onerror = () => { /* onclose обробить реконект */ };
    }

    function handleWsEvent(payload) {
        switch (payload.type) {
            case 'message':
                if (Number(payload.message.conversation_id) === Number(state.conversationId)) {
                    appendMessage(payload.message);
                    if (!payload.message.is_mine && state.ws) {
                        state.ws.send(JSON.stringify({ type: 'read' }));
                    }
                }
                bumpDialogPreview(payload.message.conversation_id, messagePreviewText(payload.message), payload.message.time_label, payload.message.sender_id);
                break;
            case 'dialog_update':
                if (payload.mode === state.mode) {
                    bumpDialogPreview(payload.conversation_id, payload.preview, payload.time_label, payload.sender_id);
                }
                break;
            case 'message_edited':
                if (payload.message && Number(payload.message.conversation_id) === Number(state.conversationId)) {
                    updateMessageBubble(payload.message);
                }
                if (payload.message) {
                    bumpDialogPreview(
                        payload.message.conversation_id,
                        messagePreviewText(payload.message),
                        payload.message.time_label,
                        payload.message.sender_id,
                    );
                }
                break;
            case 'message_deleted':
                if (Number(payload.conversation_id) === Number(state.conversationId)) {
                    removeMessageBubble(payload.message_id);
                    if (Number(state.editingMessageId) === Number(payload.message_id)) {
                        els.chatInput.value = '';
                        cancelEditMessage();
                    }
                }
                loadDialogs();
                break;
            case 'match_removed':
                if (!payload.mode || payload.mode === state.mode) {
                    if (Number(payload.conversation_id) === Number(state.conversationId)) {
                        closeChat();
                    }
                    loadMatches();
                    loadDialogs();
                }
                break;
            case 'read':
                els.chatMessages.querySelectorAll('.msg--mine').forEach((el) => {
                    const meta = el.querySelector('.msg__meta');
                    if (meta && !meta.innerHTML.includes('22 8')) {
                        meta.innerHTML = meta.innerHTML.replace(
                            '</svg>',
                            '<path d="M9 12l5 5L22 8" stroke="#E7D5FF" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
                        );
                    }
                });
                break;
            case 'error':
                console.warn('Chat WS error:', payload.message);
                break;
            default:
                break;
        }
    }

    function prepareChatPhoto(file) {
        return new Promise((resolve, reject) => {
            const image = new Image();
            const url = URL.createObjectURL(file);
            image.onload = () => {
                const maxSide = 1600;
                let width = image.width;
                let height = image.height;
                if (width > maxSide || height > maxSide) {
                    const scale = maxSide / Math.max(width, height);
                    width = Math.max(1, Math.round(width * scale));
                    height = Math.max(1, Math.round(height * scale));
                }
                const canvas = document.createElement('canvas');
                canvas.width = width;
                canvas.height = height;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(image, 0, 0, width, height);
                canvas.toBlob((blob) => {
                    URL.revokeObjectURL(url);
                    if (!blob) {
                        reject(new Error('Не вдалося обробити фото.'));
                        return;
                    }
                    resolve(new File([blob], 'photo.jpg', { type: 'image/jpeg' }));
                }, 'image/jpeg', 0.88);
            };
            image.onerror = () => {
                URL.revokeObjectURL(url);
                reject(new Error('Не вдалося прочитати фото.'));
            };
            image.src = url;
        });
    }

    function clearPendingPhoto() {
        state.pendingPhoto = null;
        if (state.pendingPhotoUrl) {
            URL.revokeObjectURL(state.pendingPhotoUrl);
            state.pendingPhotoUrl = null;
        }
        if (els.chatPhotoPreview) els.chatPhotoPreview.hidden = true;
        if (els.chatPhotoPreviewImg) els.chatPhotoPreviewImg.removeAttribute('src');
        if (els.chatInput) els.chatInput.placeholder = 'Написати повідомлення..';
    }

    async function uploadChatPhoto(conversationId, file, text) {
        const form = new FormData();
        form.append('image', file, file.name || 'photo.jpg');
        if (text) form.append('text', text);
        const response = await fetch(API.conversationSendPhoto(conversationId), {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': csrfToken(),
            },
            body: form,
        });
        if (!response.ok) {
            let detail = '';
            try {
                detail = (await response.json()).error || '';
            } catch (e) { /* ignore */ }
            throw new Error(detail || `Помилка запиту (${response.status})`);
        }
        return response.json();
    }

    function sendChatPhoto(file, text) {
        if (!state.conversationId || state.sending) return;
        state.sending = true;
        els.chatForm.classList.add('is-sending');
        uploadChatPhoto(state.conversationId, file, text)
            .then((data) => {
                clearPendingPhoto();
                els.chatInput.value = '';
                if (!(state.ws && state.ws.readyState === WebSocket.OPEN)) {
                    appendMessage(data.message);
                    bumpDialogPreview(
                        data.message.conversation_id,
                        messagePreviewText(data.message),
                        data.message.time_label,
                        data.message.sender_id,
                    );
                }
            })
            .catch((err) => alert(err.message))
            .finally(() => {
                state.sending = false;
                els.chatForm.classList.remove('is-sending');
            });
    }

    function openLightbox(url) {
        if (!url || !els.chatLightbox) return;
        els.chatLightboxImage.src = url;
        els.chatLightbox.hidden = false;
    }

    function closeLightbox() {
        if (!els.chatLightbox) return;
        els.chatLightbox.hidden = true;
        els.chatLightboxImage.removeAttribute('src');
    }

    if (els.chatAttachBtn && els.chatPhotoInput) {
        els.chatAttachBtn.addEventListener('click', () => {
            if (state.sending) return;
            els.chatPhotoInput.click();
        });
        els.chatPhotoInput.addEventListener('change', async () => {
            const file = els.chatPhotoInput.files && els.chatPhotoInput.files[0];
            els.chatPhotoInput.value = '';
            if (!file) return;
            if (!ALLOWED_PHOTO_TYPES.includes(file.type)) {
                alert('Фото має бути JPEG, PNG або WebP.');
                return;
            }
            if (file.size > MAX_PHOTO_BYTES) {
                alert('Фото має бути не більше 5 МБ.');
                return;
            }
            try {
                const prepared = await prepareChatPhoto(file);
                clearPendingPhoto();
                state.pendingPhoto = prepared;
                state.pendingPhotoUrl = URL.createObjectURL(prepared);
                els.chatPhotoPreviewImg.src = state.pendingPhotoUrl;
                els.chatPhotoPreview.hidden = false;
                els.chatInput.placeholder = 'Підпис (необов\'язково)..';
                els.chatInput.focus();
            } catch (err) {
                alert(err.message);
            }
        });
    }

    if (els.chatPhotoPreviewRemove) {
        els.chatPhotoPreviewRemove.addEventListener('click', clearPendingPhoto);
    }

    if (els.chatMessages) {
        els.chatMessages.addEventListener('click', (evt) => {
            const btn = evt.target.closest('.msg__image-btn');
            if (!btn) return;
            openLightbox(btn.dataset.imageUrl);
        });
        els.chatMessages.addEventListener('contextmenu', (evt) => {
            const bubble = evt.target.closest('.msg--mine');
            if (!bubble) return;
            evt.preventDefault();
            hideChatMoreMenu();
            showMsgMenu(evt, bubble);
        });
    }

    if (els.msgMenu) {
        els.msgMenu.addEventListener('click', (evt) => {
            const actionBtn = evt.target.closest('[data-action]');
            if (!actionBtn) return;
            const bubble = els.chatMessages.querySelector(`[data-message-id="${state.menuMessageId}"]`);
            if (!bubble) {
                hideMsgMenu();
                return;
            }
            if (actionBtn.dataset.action === 'edit') {
                startEditMessage(bubble);
            } else if (actionBtn.dataset.action === 'delete') {
                scheduleDelete(bubble.dataset.messageId);
            }
        });
    }

    if (els.chatEditCancel) {
        els.chatEditCancel.addEventListener('click', () => {
            els.chatInput.value = '';
            cancelEditMessage();
        });
    }

    if (els.chatUndoBtn) {
        els.chatUndoBtn.addEventListener('click', undoPendingDelete);
    }

    if (els.chatMoreBtn) {
        els.chatMoreBtn.addEventListener('click', (evt) => {
            evt.stopPropagation();
            toggleChatMoreMenu();
        });
    }

    if (els.chatUnmatchBtn) {
        els.chatUnmatchBtn.addEventListener('click', () => {
            hideChatMoreMenu();
            unmatchPerson({
                match_id: state.activeMatchId,
                conversation_id: state.conversationId,
            });
        });
    }

    if (els.chatLeaveMeetingBtn) {
        els.chatLeaveMeetingBtn.addEventListener('click', () => {
            hideChatMoreMenu();
            leaveActiveMeeting();
        });
    }

    document.addEventListener('mousedown', (evt) => {
        if (els.chatMoreMenu && !els.chatMoreMenu.hidden) {
            if (!els.chatMoreMenu.contains(evt.target) && !els.chatMoreBtn.contains(evt.target)) {
                hideChatMoreMenu();
            }
        }
        if (!els.msgMenu || els.msgMenu.hidden) return;
        if (els.msgMenu.contains(evt.target)) return;
        hideMsgMenu();
    });
    window.addEventListener('resize', hideMsgMenu);
    if (els.chatMessages) {
        els.chatMessages.addEventListener('scroll', hideMsgMenu);
    }

    if (els.chatLightboxClose) {
        els.chatLightboxClose.addEventListener('click', closeLightbox);
    }
    if (els.chatLightbox) {
        els.chatLightbox.addEventListener('click', (evt) => {
            if (evt.target === els.chatLightbox) closeLightbox();
        });
    }
    document.addEventListener('keydown', (evt) => {
        if (evt.key !== 'Escape') return;
        if (els.chatLightbox && !els.chatLightbox.hidden) {
            closeLightbox();
            return;
        }
        if (els.msgMenu && !els.msgMenu.hidden) {
            hideMsgMenu();
            return;
        }
        if (els.chatMoreMenu && !els.chatMoreMenu.hidden) {
            hideChatMoreMenu();
            return;
        }
        if (state.pendingDeleteMessageId) {
            undoPendingDelete();
            return;
        }
        if (state.editingMessageId) {
            els.chatInput.value = '';
            cancelEditMessage();
        }
    });

    els.chatForm.addEventListener('submit', (evt) => {
        evt.preventDefault();
        if (state.sending) return;
        if (state.editingMessageId) {
            saveEditedMessage();
            return;
        }
        const text = els.chatInput.value.trim();
        if (state.pendingPhoto) {
            sendChatPhoto(state.pendingPhoto, text);
            return;
        }
        if (!text) return;
        if (state.ws && state.ws.readyState === WebSocket.OPEN) {
            state.ws.send(JSON.stringify({ type: 'message', text }));
            els.chatInput.value = '';
        } else {
            apiFetch(`/app/conversations/${state.conversationId}/send/`, {
                method: 'POST',
                body: JSON.stringify({ text }),
            }).then((data) => {
                appendMessage(data.message);
                els.chatInput.value = '';
            }).catch((err) => alert(err.message));
        }
    });

    setMode(state.mode, { silent: true });
    connectInboxSocket();
})();
