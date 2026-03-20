/**
 * initChat – bootstraps AJAX send and polling for a chat window.
 *
 * @param {number} chatId         - Database id of the current chat
 * @param {string} chatType       - 'direct' or 'group'
 * @param {number} currentUserId  - Logged-in user's id (used to style own bubbles)
 * @param {string} sendUrl        - URL for the send-message endpoint
 * @param {string} updatesUrl     - URL for the poll-updates endpoint
 */
function initChat(chatId, chatType, currentUserId, sendUrl, updatesUrl) {
    const window_ = document.getElementById('chat-window');
    const form = document.getElementById('chat-form');
    const input = form ? form.querySelector('input[name="message"]') : null;
    const csrfToken = form ? form.querySelector('[name=csrfmiddlewaretoken]').value : '';

    let lastId = 0;

    // Determine the highest message id already rendered on page load
    window_.querySelectorAll('[data-msg-id]').forEach(el => {
        const id = parseInt(el.dataset.msgId, 10);
        if (id > lastId) lastId = id;
    });

    scrollToBottom();

    // ── Send message ────────────────────────────────────────────────────────
    if (form) {
        form.addEventListener('submit', function (e) {
            e.preventDefault();
            const text = input.value.trim();
            if (!text) return;

            input.value = '';
            input.focus();

            fetch(sendUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                },
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
                    // Re-fill input on failure so the user doesn't lose the message
                    input.value = text;
                });
        });
    }

    // ── Poll for new messages every 3 seconds ───────────────────────────────
    setInterval(pollUpdates, 3000);

    function pollUpdates() {
        fetch(`${updatesUrl}?last_id=${lastId}`)
            .then(r => r.json())
            .then(data => {
                if (data.messages && data.messages.length) {
                    data.messages.forEach(msg => {
                        appendMessage(msg, msg.user_id === currentUserId);
                        if (msg.id > lastId) lastId = msg.id;
                    });
                }
            })
            .catch(() => { /* silently ignore network errors */ });
    }

    // ── DOM helpers ─────────────────────────────────────────────────────────
    function appendMessage(msg, isOwn) {
        // Remove the empty-state placeholder if present
        const placeholder = window_.querySelector('.text-center.text-muted');
        if (placeholder) placeholder.remove();

        const wrapper = document.createElement('div');
        wrapper.className = 'd-flex flex-column ' + (isOwn ? 'align-items-end' : 'align-items-start');
        wrapper.dataset.msgId = msg.id;

        let html = '';
        html += `<div class="bubble ${isOwn ? 'bubble-own' : 'bubble-other'}">`
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
}
