/**
 * initChat – bootstraps a WebSocket connection for a chat window.
 *
 * Primary path  : WebSocket (real-time, no polling)
 * Fallback path : HTTP fetch polling every 3 s (used when WS is unavailable
 *                 or after an unexpected disconnect while waiting to reconnect)
 *
 * @param {number} chatId           - Database id of the current chat
 * @param {string} chatType         - 'direct' or 'group'
 * @param {number} currentUserId    - Logged-in user's id
 * @param {string} wsUrl            - WebSocket URL  (wss://…/ws/chat/direct/<id>/)
 * @param {string} fallbackSendUrl  - HTTP POST URL used when WS is not open
 * @param {string} fallbackPollUrl  - HTTP GET URL used to catch missed messages
 */
function initChat(chatId, chatType, currentUserId, wsUrl, fallbackSendUrl, fallbackPollUrl) {
    const window_ = document.getElementById('chat-window');
    const form    = document.getElementById('chat-form');
    const input   = form ? form.querySelector('input[name="message"]') : null;
    const csrf    = form ? form.querySelector('[name=csrfmiddlewaretoken]').value : '';

    // Track the highest message id already on the page so the HTTP fallback
    // can request only messages we haven't seen yet.
    let lastId = 0;
    window_.querySelectorAll('[data-msg-id]').forEach(el => {
        const id = parseInt(el.dataset.msgId, 10);
        if (id > lastId) lastId = id;
    });

    scrollToBottom();

    // ── WebSocket ────────────────────────────────────────────────────────────
    let ws              = null;
    let wsReady         = false;   // true once the socket is open
    let reconnectDelay  = 1000;    // starts at 1 s, doubles on each failure
    let fallbackTimer   = null;    // HTTP poll interval, active only when WS is down

    function openWebSocket() {
        ws = new WebSocket(wsUrl);

        ws.onopen = function () {
            wsReady = true;
            reconnectDelay = 1000;   // reset back-off on successful connect
            stopFallbackPolling();
        };

        ws.onmessage = function (e) {
            const msg = JSON.parse(e.data);
            if (msg.id > lastId) {
                appendMessage(msg, msg.user_id === currentUserId);
                lastId = msg.id;
            }
        };

        ws.onclose = function (e) {
            wsReady = false;
            ws = null;

            if (e.code === 4001 || e.code === 4003) {
                // Auth or membership error – do not reconnect.
                console.warn('Chat WebSocket closed: auth/membership error', e.code);
                return;
            }

            // Unexpected close: start HTTP fallback and schedule reconnect.
            startFallbackPolling();
            setTimeout(openWebSocket, reconnectDelay);
            reconnectDelay = Math.min(reconnectDelay * 2, 30000);
        };

        ws.onerror = function () {
            // onclose fires right after onerror, so no extra handling needed.
        };
    }

    // ── HTTP fallback (used only when WS is down) ────────────────────────────
    function startFallbackPolling() {
        if (fallbackTimer) return;
        fallbackTimer = setInterval(pollFallback, 3000);
    }

    function stopFallbackPolling() {
        if (fallbackTimer) {
            clearInterval(fallbackTimer);
            fallbackTimer = null;
        }
    }

    function pollFallback() {
        fetch(`${fallbackPollUrl}?last_id=${lastId}`)
            .then(r => r.json())
            .then(data => {
                (data.messages || []).forEach(msg => {
                    if (msg.id > lastId) {
                        appendMessage(msg, msg.user_id === currentUserId);
                        lastId = msg.id;
                    }
                });
            })
            .catch(() => { /* silently ignore network errors */ });
    }

    // ── Send message ─────────────────────────────────────────────────────────
    if (form) {
        form.addEventListener('submit', function (e) {
            e.preventDefault();
            const text = input.value.trim();
            if (!text) return;
            input.value = '';
            input.focus();

            if (wsReady) {
                // Send via WebSocket; the server broadcasts it back to all
                // clients including the sender, so no local render needed here.
                ws.send(JSON.stringify({ message: text }));
            } else {
                // WebSocket not available – fall back to HTTP POST.
                fetch(fallbackSendUrl, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
                    body: JSON.stringify({ message: text }),
                })
                    .then(r => r.json())
                    .then(data => {
                        if (data.id) {
                            appendMessage(data, true);
                            lastId = data.id;
                        }
                    })
                    .catch(() => {
                        // Re-fill input so the user doesn't lose the message.
                        input.value = text;
                    });
            }
        });
    }

    // ── DOM helpers ───────────────────────────────────────────────────────────
    function appendMessage(msg, isOwn) {
        const placeholder = window_.querySelector('.text-center.text-muted');
        if (placeholder) placeholder.remove();

        const wrapper = document.createElement('div');
        wrapper.className = 'd-flex flex-column ' + (isOwn ? 'align-items-end' : 'align-items-start');
        if (msg.id) wrapper.dataset.msgId = msg.id;

        let html = `<div class="bubble ${isOwn ? 'bubble-own' : 'bubble-other'}">`;
        if (!isOwn && chatType === 'group') {
            html += `<small class="text-muted">${escapeHtml(msg.user)}</small><br>`;
        }
        html += `${escapeHtml(msg.message)}</div>`;
        html += `<div class="bubble-meta ${isOwn ? 'text-end me-1' : 'ms-1'}">${escapeHtml(msg.created_at)}</div>`;

        wrapper.innerHTML = html;
        window_.appendChild(wrapper);
        scrollToBottom();
    }

    function scrollToBottom() {
        window_.scrollTop = window_.scrollHeight;
    }

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.appendChild(document.createTextNode(String(str)));
        return div.innerHTML;
    }

    // Start the WebSocket connection.
    openWebSocket();
}
