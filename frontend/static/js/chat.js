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
    };

    const body = document.body;
    const state = {
        mode: body.dataset.initialMode || 'dating',
        myUserId: parseInt(body.dataset.myUserId, 10) || null,
        conversationId: null,
        ws: null,
        wsReconnectAttempts: 0,
        activeMatchId: null,
        activeCandidateUserId: null,
        swipeLocked: false,
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
        chatView: document.getElementById('chat-view'),
        chatBackBtn: document.getElementById('chat-back-btn'),
        chatMessages: document.getElementById('chat-messages'),
        chatForm: document.getElementById('chat-form'),
        chatInput: document.getElementById('chat-input'),
        chatPartnerAvatar: document.getElementById('chat-partner-avatar'),
        chatPartnerName: document.getElementById('chat-partner-name'),
        chatPartnerStatus: document.getElementById('chat-partner-status'),
        sidebarToggle: document.getElementById('sidebar-toggle'),
        sidebar: document.getElementById('chat-sidebar'),
        matchesMore: document.getElementById('matches-more'),
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
        const response = await fetch(url, opts);
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

    /* ---------------- Режим (Романтика / Дружба) ---------------- */

    function setMode(mode, { silent } = {}) {
        state.mode = mode;
        els.modeSwitch.dataset.active = mode;
        els.modeButtons.forEach((btn) => {
            const active = btn.dataset.mode === mode;
            btn.setAttribute('aria-selected', active ? 'true' : 'false');
        });
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

    /* ---------------- Метчі ---------------- */

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
            els.matchesMore.hidden = matches.length <= 8;
            els.matchesMore.setAttribute('aria-expanded', 'false');
        }
        if (!matches.length) {
            const empty = document.createElement('p');
            empty.className = 'panel__empty';
            empty.textContent = 'Поки немає метчів у цьому режимі';
            grid.appendChild(empty);
            return;
        }
        matches.forEach((match) => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'match-avatar';
            btn.dataset.matchId = match.match_id;
            btn.title = `${match.display_name}${match.age ? ', ' + match.age : ''}`;
            if (match.match_id === state.activeMatchId) {
                btn.classList.add('is-active');
            }
            btn.innerHTML = `
                <img class="match-avatar__img" src="${match.avatar_url || avatarPlaceholder()}" alt="${escapeHtml(match.display_name)}">
            `;
            btn.addEventListener('click', () => openConversationByMatch(match));
            grid.appendChild(btn);
        });
    }

    if (els.matchesMore) {
        els.matchesMore.addEventListener('click', () => {
            const expanded = els.matchesGrid.classList.toggle('is-expanded');
            els.matchesMore.setAttribute('aria-expanded', expanded ? 'true' : 'false');
        });
    }

    /* ---------------- Діалоги ---------------- */

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
            empty.textContent = "Тут з'являться ваші діалоги";
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
            item.addEventListener('click', () => openChat(dialog.conversation_id, {
                displayName: dialog.other_display_name,
                age: dialog.other_age,
                avatarUrl: dialog.avatar_url,
            }));
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

    /* ---------------- Свайпи / картка ---------------- */

    async function loadNextCandidate() {
        state.swipeLocked = false;
        els.swipeCard.innerHTML = '<div class="swipe-card__placeholder"><p>Завантаження…</p></div>';
        els.swipeActions.hidden = true;
        try {
            const data = await apiFetch(API.discover(state.mode));
            renderCandidate(data.candidate);
        } catch (err) {
            els.swipeCard.innerHTML = `<div class="swipe-card__placeholder"><p>${escapeHtml(err.message)}</p></div>`;
        }
    }

    function renderCandidate(candidate) {
        if (!candidate) {
            state.activeCandidateUserId = null;
            els.swipeActions.hidden = true;
            els.swipeCard.innerHTML = '<div class="swipe-card__placeholder"><p>Анкети закінчились. Спробуйте пізніше 💜</p></div>';
            return;
        }
        state.activeCandidateUserId = candidate.user_id;
        const photos = candidate.photos && candidate.photos.length ? candidate.photos : [avatarPlaceholder()];
        const dots = photos.map((_, idx) => `<span class="swipe-card__dot ${idx === 0 ? 'is-active' : ''}"></span>`).join('');

        els.swipeCard.innerHTML = `
            <img class="swipe-card__photo" src="${photos[0]}" alt="${escapeHtml(candidate.display_name)}">
            ${photos.length > 1 ? `<div class="swipe-card__dots">${dots}</div>` : ''}
            <div class="swipe-card__gradient"></div>
            <div class="swipe-card__info">
                <h2 class="swipe-card__name">${escapeHtml(candidate.display_name)} ${candidate.age || ''}</h2>
                <p class="swipe-card__bio">${escapeHtml(candidate.bio) || (candidate.city ? escapeHtml(candidate.city) : '')}</p>
            </div>
        `;

        if (photos.length > 1) {
            let current = 0;
            const img = els.swipeCard.querySelector('.swipe-card__photo');
            const dotEls = els.swipeCard.querySelectorAll('.swipe-card__dot');
            img.addEventListener('click', (evt) => {
                const rect = img.getBoundingClientRect();
                const isRight = (evt.clientX - rect.left) > rect.width / 2;
                current = isRight
                    ? (current + 1) % photos.length
                    : (current - 1 + photos.length) % photos.length;
                img.src = photos[current];
                dotEls.forEach((dot, idx) => dot.classList.toggle('is-active', idx === current));
            });
        }

        els.swipeActions.hidden = false;
    }

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

    els.likeBtn.addEventListener('click', () => swipe(true));
    els.dislikeBtn.addEventListener('click', () => swipe(false));

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

    /* ---------------- Чат ---------------- */

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
        highlightActiveDialog(conversationId);

        els.discoverView.hidden = true;
        els.chatView.hidden = false;
        els.chatMessages.innerHTML = '<p class="chat-empty-state">Завантаження історії…</p>';
        if (hint) {
            els.chatPartnerName.textContent = `${hint.displayName || ''}${hint.age ? ', ' + hint.age : ''}`;
            if (hint.avatarUrl) {
                els.chatPartnerAvatar.src = hint.avatarUrl;
                els.chatPartnerAvatar.hidden = false;
            }
        }
        closeSidebarOnMobile();

        try {
            const data = await apiFetch(API.conversationMessages(conversationId));
            els.chatPartnerName.textContent = `${data.other_user.display_name}${data.other_user.age ? ', ' + data.other_user.age : ''}`;
            els.chatPartnerAvatar.src = data.other_user.avatar_url || avatarPlaceholder();
            els.chatPartnerAvatar.hidden = false;
            els.chatPartnerStatus.textContent = state.mode === 'dating' ? 'Романтика' : 'Дружба';
            renderMessages(data.messages || []);
            connectWebSocket(conversationId);
            apiFetch(API.conversationRead(conversationId), { method: 'POST' }).then(loadDialogs).catch(() => {});
        } catch (err) {
            els.chatMessages.innerHTML = `<p class="chat-empty-state">${escapeHtml(err.message)}</p>`;
        }
    }

    function closeChat() {
        closeWebSocket();
        state.conversationId = null;
        els.chatView.hidden = true;
        els.discoverView.hidden = false;
        els.chatMessages.innerHTML = '';
        highlightActiveDialog(null);
    }

    els.chatBackBtn.addEventListener('click', closeChat);

    function highlightActiveDialog(conversationId) {
        els.dialogsList.querySelectorAll('.dialog-item').forEach((el) => {
            el.classList.toggle('is-active', Number(el.dataset.conversationId) === Number(conversationId));
        });
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

    function appendMessage(message) {
        if (els.chatMessages.querySelector('.chat-empty-state')) {
            els.chatMessages.innerHTML = '';
        }
        const bubble = document.createElement('div');
        bubble.className = `msg ${message.is_mine ? 'msg--mine' : 'msg--theirs'}`;
        bubble.dataset.messageId = message.id;
        const checkIcon = message.is_mine
            ? `<svg width="12" height="12" viewBox="0 0 24 24" fill="none"><path d="M2 12l5 5L14 8" stroke="#fff" stroke-width="2" stroke-linecap="round"/>${message.is_read ? '<path d="M9 12l5 5L22 8" stroke="#fff" stroke-width="2" stroke-linecap="round"/>' : ''}</svg>`
            : '';
        bubble.innerHTML = `
            <span class="msg__text">${escapeHtml(message.text)}</span>
            <span class="msg__meta">${escapeHtml(message.time_label)} ${checkIcon}</span>
        `;
        els.chatMessages.appendChild(bubble);
        scrollMessagesToBottom();
    }

    function scrollMessagesToBottom() {
        els.chatMessages.scrollTop = els.chatMessages.scrollHeight;
    }

    /* ---------------- WebSocket ---------------- */

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

    function handleWsEvent(payload) {
        switch (payload.type) {
            case 'message':
                if (Number(payload.message.conversation_id) === Number(state.conversationId)) {
                    appendMessage(payload.message);
                    if (!payload.message.is_mine && state.ws) {
                        state.ws.send(JSON.stringify({ type: 'read' }));
                    }
                }
                bumpDialogPreview(payload.message.conversation_id, payload.message.text, payload.message.time_label, payload.message.sender_id);
                break;
            case 'dialog_update':
                if (payload.mode === state.mode) {
                    bumpDialogPreview(payload.conversation_id, payload.preview, payload.time_label, payload.sender_id);
                }
                break;
            case 'read':
                els.chatMessages.querySelectorAll('.msg--mine').forEach((el) => {
                    const meta = el.querySelector('.msg__meta');
                    if (meta && !meta.innerHTML.includes('22 8')) {
                        meta.innerHTML = meta.innerHTML.replace(
                            '</svg>',
                            '<path d="M9 12l5 5L22 8" stroke="#fff" stroke-width="2" stroke-linecap="round"/></svg>',
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

    els.chatForm.addEventListener('submit', (evt) => {
        evt.preventDefault();
        const text = els.chatInput.value.trim();
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

    /* ---------------- Мобільний drawer (якщо кнопка є) ---------------- */

    if (els.sidebarToggle && els.sidebar) {
        els.sidebarToggle.addEventListener('click', () => {
            const isOpen = els.sidebar.classList.toggle('is-open');
            els.sidebarToggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
        });
    }

    function closeSidebarOnMobile() {
        if (window.innerWidth <= 960 && els.sidebar && els.sidebarToggle) {
            els.sidebar.classList.remove('is-open');
            els.sidebarToggle.setAttribute('aria-expanded', 'false');
        }
    }

    document.addEventListener('click', (evt) => {
        if (
            els.sidebar
            && els.sidebarToggle
            && window.innerWidth <= 960
            && els.sidebar.classList.contains('is-open')
            && !els.sidebar.contains(evt.target)
            && evt.target !== els.sidebarToggle
            && !els.sidebarToggle.contains(evt.target)
        ) {
            els.sidebar.classList.remove('is-open');
            els.sidebarToggle.setAttribute('aria-expanded', 'false');
        }
    });

    /* ---------------- Ініціалізація ---------------- */

    setMode(state.mode, { silent: true });
})();
