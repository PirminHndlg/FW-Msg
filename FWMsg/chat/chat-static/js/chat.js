/**
 * initChat – bootstraps a WebSocket connection for a chat window.
 *
 * Primary path  : WebSocket (real-time, no polling)
 * Fallback path : HTTP fetch polling every 3 s (used when WS is unavailable
 *                 or after an unexpected disconnect while waiting to reconnect)
 *
 * Tap / click chat images for fullscreen preview (setupChatImageLightbox).
 *
 * @param {number} chatId           - Database id of the current chat
 * @param {string} chatType         - 'direct' or 'group'
 * @param {number} currentUserId    - Logged-in user's id
 * @param {string} wsUrl            - WebSocket URL  (wss://…/ws/chat/direct/<id>/)
 * @param {string} fallbackSendUrl  - HTTP POST URL used when WS is not open
 * @param {string} fallbackPollUrl  - HTTP GET URL used to catch missed messages
 */

var _chatImageLightboxInst = null;

/** Singleton fullscreen overlay; binds each #chat-window once. */
function ensureChatImageLightboxDom() {
    if (_chatImageLightboxInst) return _chatImageLightboxInst;

    const lb = document.createElement('div');
    lb.id = 'chat-image-lightbox';
    lb.className = 'chat-image-lightbox';
    lb.setAttribute('role', 'dialog');
    lb.setAttribute('aria-modal', 'true');
    lb.setAttribute('aria-hidden', 'true');

    const closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.className = 'chat-image-lightbox-close';
    closeBtn.setAttribute('aria-label', 'Schließen');
    closeBtn.innerHTML = '&times;';

    const fullImg = document.createElement('img');
    fullImg.className = 'chat-image-lightbox-img';
    fullImg.alt = '';

    lb.appendChild(closeBtn);
    lb.appendChild(fullImg);
    document.body.appendChild(lb);

    function onDocKeyDown(e) {
        if (e.key === 'Escape') {
            closeLightbox();
        }
    }

    function closeLightbox() {
        lb.classList.remove('is-open');
        lb.setAttribute('aria-hidden', 'true');
        fullImg.removeAttribute('src');
        document.body.style.overflow = '';
        document.removeEventListener('keydown', onDocKeyDown);
    }

    function openLightbox(src) {
        if (!src) return;
        fullImg.src = src;
        lb.classList.add('is-open');
        lb.setAttribute('aria-hidden', 'false');
        document.body.style.overflow = 'hidden';
        document.addEventListener('keydown', onDocKeyDown);
        closeBtn.focus();
    }

    closeBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        closeLightbox();
    });

    lb.addEventListener('click', function (e) {
        if (e.target === lb) {
            closeLightbox();
        }
    });

    fullImg.addEventListener('click', function (e) {
        e.stopPropagation();
    });

    _chatImageLightboxInst = { openLightbox: openLightbox, closeLightbox: closeLightbox };
    return _chatImageLightboxInst;
}

function setupChatImageLightbox(chatWindow) {
    if (!chatWindow || chatWindow.dataset.chatImageLightboxBound === '1') return;
    chatWindow.dataset.chatImageLightboxBound = '1';

    const api = ensureChatImageLightboxDom();

    chatWindow.addEventListener('click', function (e) {
        const t = e.target;
        if (t && t.tagName === 'IMG' && t.classList.contains('chat-bubble-image')) {
            e.preventDefault();
            api.openLightbox(t.currentSrc || t.src);
        }
    });

    chatWindow.addEventListener('keydown', function (e) {
        if (e.key !== 'Enter' && e.key !== ' ') return;
        const t = e.target;
        if (t && t.tagName === 'IMG' && t.classList.contains('chat-bubble-image')) {
            e.preventDefault();
            api.openLightbox(t.currentSrc || t.src);
        }
    });
}

function initChat(chatId, chatType, currentUserId, wsUrl, fallbackSendUrl, fallbackPollUrl) {
    const window_ = document.getElementById('chat-window');
    if (!window_) {
        return;
    }
    const form    = document.getElementById('chat-form');
    const messageField = form ? form.querySelector('[name="message"]') : null;
    const csrf    = form ? form.querySelector('[name=csrfmiddlewaretoken]').value : '';
    const imageInput = document.getElementById('image-input');
    const imagePreview = document.getElementById('image-preview');
    const imageAttachBtn = document.getElementById('image-attach-btn');

    let previewObjectUrl = null;

    function revokePreviewUrl() {
        if (previewObjectUrl) {
            URL.revokeObjectURL(previewObjectUrl);
            previewObjectUrl = null;
        }
    }

    function clearImageSelection() {
        revokePreviewUrl();
        if (imageInput) imageInput.value = '';
        if (imagePreview) {
            imagePreview.innerHTML = '';
            imagePreview.style.display = 'none';
        }
    }

    function hasImageSelected() {
        return !!(imageInput && imageInput.files && imageInput.files.length > 0);
    }

    /** User deliberately scrolled up — stop fighting them during lazy image/layout shifts. */
    let userLeftChatBottom = false;

    function scrollToBottom() {
        window_.scrollTop = Math.max(0, window_.scrollHeight - window_.clientHeight);
    }

    function syncBottomIfPinned() {
        if (!userLeftChatBottom) {
            scrollToBottom();
        }
    }

    window_.addEventListener(
        'scroll',
        function () {
            const gap = window_.scrollHeight - window_.scrollTop - window_.clientHeight;
            if (gap > 120) {
                userLeftChatBottom = true;
            }
        },
        { passive: true }
    );

    /**
     * After refresh, bubble images load async and grow scrollHeight. Re-align to bottom
     * until the user scrolls away (ResizeObserver + load + delayed ticks).
     */
    function bindStickyBottomForLateMedia() {
        syncBottomIfPinned();
        requestAnimationFrame(syncBottomIfPinned);
        requestAnimationFrame(function () {
            requestAnimationFrame(syncBottomIfPinned);
        });

        window.addEventListener('load', syncBottomIfPinned);

        window_.querySelectorAll('img.chat-bubble-image').forEach(function (img) {
            img.addEventListener('load', syncBottomIfPinned, { passive: true });
            img.addEventListener('error', syncBottomIfPinned, { passive: true });
        });

        if (typeof ResizeObserver !== 'undefined') {
            var ro = new ResizeObserver(function () {
                syncBottomIfPinned();
            });
            ro.observe(window_);
        }

        [0, 50, 150, 400, 1000].forEach(function (ms) {
            setTimeout(syncBottomIfPinned, ms);
        });
    }

    // Track the highest message id already on the page so the HTTP fallback
    // can request only messages we haven't seen yet.
    let lastId = 0;
    window_.querySelectorAll('[data-msg-id]').forEach(el => {
        const id = parseInt(el.dataset.msgId, 10);
        if (id > lastId) lastId = id;
    });

    bindStickyBottomForLateMedia();

    setupChatImageLightbox(window_);

    const CHAT_MESSAGE_MAX_ROWS = 10;

    if (imageAttachBtn && imageInput) {
        imageAttachBtn.addEventListener('click', function () {
            imageInput.click();
        });
    }

    if (imageInput && imagePreview) {
        imageInput.addEventListener('change', function () {
            revokePreviewUrl();
            imagePreview.innerHTML = '';
            const f = imageInput.files && imageInput.files[0];
            if (!f) {
                imagePreview.style.display = 'none';
                return;
            }
            previewObjectUrl = URL.createObjectURL(f);
            const img = document.createElement('img');
            img.src = previewObjectUrl;
            img.alt = '';
            img.className = 'chat-image-preview-thumb';
            const removeBtn = document.createElement('button');
            removeBtn.type = 'button';
            removeBtn.className = 'btn btn-sm btn-outline-secondary ms-2 align-top';
            removeBtn.setAttribute('aria-label', 'Entfernen');
            removeBtn.textContent = '×';
            removeBtn.addEventListener('click', function () {
                clearImageSelection();
            });
            imagePreview.appendChild(img);
            imagePreview.appendChild(removeBtn);
            imagePreview.style.display = '';
        });
    }

    function autosizeChatMessageField(textarea) {
        if (!textarea) return;
        const style = window.getComputedStyle(textarea);
        const fontSize = parseFloat(style.fontSize) || 16;
        let lineHeight = parseFloat(style.lineHeight);
        if (Number.isNaN(lineHeight) || style.lineHeight === 'normal') {
            lineHeight = fontSize * 1.2;
        }
        const padY = (parseFloat(style.paddingTop) || 0) + (parseFloat(style.paddingBottom) || 0);
        const maxH = lineHeight * CHAT_MESSAGE_MAX_ROWS + padY;

        textarea.style.height = 'auto';
        const scrollH = textarea.scrollHeight;
        const nextH = Math.min(scrollH, maxH);
        textarea.style.height = `${nextH}px`;
        textarea.style.overflowY = scrollH > maxH ? 'auto' : 'hidden';
    }

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
    if (form && messageField) {
        messageField.addEventListener('input', function () {
            autosizeChatMessageField(messageField);
        });
        autosizeChatMessageField(messageField);

        messageField.addEventListener('keydown', function (e) {
            if (e.key !== 'Enter' || e.shiftKey) return;
            if (e.isComposing) return;
            e.preventDefault();
            form.requestSubmit();
        });

        form.addEventListener('submit', function (e) {
            e.preventDefault();
            const text = messageField.value.trim();
            const withImage = hasImageSelected();

            if (!text && !withImage) return;

            if (withImage) {
                const fd = new FormData();
                fd.append('csrfmiddlewaretoken', csrf);
                fd.append('message', text);
                fd.append('image', imageInput.files[0]);

                const savedText = text;
                messageField.value = '';
                autosizeChatMessageField(messageField);
                messageField.focus();

                fetch(fallbackSendUrl, {
                    method: 'POST',
                    headers: { 'X-CSRFToken': csrf },
                    body: fd,
                })
                    .then(function (r) { return r.json(); })
                    .then(function (data) {
                        if (data.error) {
                            messageField.value = savedText;
                            autosizeChatMessageField(messageField);
                            return;
                        }
                        clearImageSelection();
                        if (!wsReady && data.id) {
                            appendMessage(data, true);
                            lastId = data.id;
                        }
                    })
                    .catch(function () {
                        messageField.value = savedText;
                        autosizeChatMessageField(messageField);
                    });
                return;
            }

            messageField.value = '';
            autosizeChatMessageField(messageField);
            messageField.focus();

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
                    .then(function (r) { return r.json(); })
                    .then(function (data) {
                        if (data.id) {
                            appendMessage(data, true);
                            lastId = data.id;
                        }
                    })
                    .catch(function () {
                        // Re-fill input so the user doesn't lose the message.
                        messageField.value = text;
                        autosizeChatMessageField(messageField);
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
        if (msg.image_url) {
            html += `<img src="${escapeHtml(msg.image_url)}" alt="" class="chat-bubble-image" role="button" tabindex="0" aria-label="Bild vergrößern">`;
        }
        if (msg.message) {
            html += `<p>${formatMessageBody(msg.message)}</p>`;
        }
        html += '</div>';
        html += `<div class="bubble-meta ${isOwn ? 'text-end me-1' : 'ms-1'}">${escapeHtml(msg.created_at)}</div>`;

        wrapper.innerHTML = html;
        window_.appendChild(wrapper);
        userLeftChatBottom = false;
        scrollToBottom();
    }

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.appendChild(document.createTextNode(String(str)));
        return div.innerHTML;
    }

    /** Escape HTML, then convert newlines to <br> (matches Django linebreaksbr). */
    function formatMessageBody(str) {
        return escapeHtml(str).replace(/\r\n|\r|\n/g, '<br>');
    }

    // Start the WebSocket connection.
    openWebSocket();
}
