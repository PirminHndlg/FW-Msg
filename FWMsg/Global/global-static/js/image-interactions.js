/**
 * Image Interactions Handler
 * Handles emoji reactions and comments for images in both gallery and fullscreen modes
 */

function interactionButtonPressed(button) {
    const emoji = button.getAttribute("data-emoji");
    const interactionUrl = button.getAttribute("data-interaction-url");
    
    // Build URL with emoji parameter
    const url = interactionUrl.replace('EMOJI_PLACEHOLDER', encodeURIComponent(emoji));
    
    // fetch to the URL (GET request)
    fetch(url)
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            location.reload();
        } else {
            console.error("Error:", data.error);
        }
    })
    .catch(error => {
        console.error("Error:", error);
    });
}

/**
 * Show the reactions modal and load reaction details
 */
function showReactionsModal(bildId) {
    if (!bildId) {
        console.error('Bild ID ist erforderlich');
        return;
    }

    // Show the modal
    const modal = new bootstrap.Modal(document.getElementById('reactionsModal'));
    modal.show();

    // Reset modal body to loading state
    const modalBody = document.getElementById('reactionsModalBody');
    modalBody.innerHTML = `
        <div class="text-center py-3">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Lädt...</span>
            </div>
        </div>
    `;

    // Fetch reaction details
    const url = `/bilder/${bildId}/reactions/`;
    
    fetch(url)
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            displayReactions(data.reactions);
        } else {
            displayError(data.error || 'Fehler beim Laden der Reaktionen');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        displayError('Netzwerkfehler beim Laden der Reaktionen');
    });
}

/**
 * Display reactions in the modal
 */
function displayReactions(reactions) {
    const modalBody = document.getElementById('reactionsModalBody');
    
    if (Object.keys(reactions).length === 0) {
        modalBody.innerHTML = `
            <div class="text-center text-muted py-5">
                <i class="bi bi-emoji-neutral fs-1 mb-3 d-block text-secondary"></i>
                <h6 class="mb-1">Keine Reaktionen vorhanden</h6>
                <p class="mb-0 small">Sei der Erste, der reagiert!</p>
            </div>
        `;
        return;
    }

    let html = '<div class="reactions-list">';
    
    // Sort emojis by count (descending)
    const sortedEmojis = Object.keys(reactions).sort((a, b) => reactions[b].length - reactions[a].length);
    
    sortedEmojis.forEach((emoji, index) => {
        const users = reactions[emoji];
        if (users.length > 0) {
            html += `
                <div class="reaction-group ${index > 0 ? 'border-top pt-3' : ''} mb-3">
                    <div class="d-flex align-items-center mb-3">
                        <div class="emoji-circle d-flex align-items-center justify-content-center me-3">
                            <span class="fs-3">${emoji}</span>
                        </div>
                        <div>
                            <h6 class="mb-0">${users.length} ${users.length === 1 ? 'Person' : 'Personen'}</h6>
                            <small class="text-muted">haben mit ${emoji} reagiert</small>
                        </div>
                    </div>
                    <div class="users-list ps-1">
            `;
            
            users.forEach((user, userIndex) => {
                html += `
                    <div class="user-item d-flex align-items-center py-2 ${userIndex > 0 ? 'border-top' : ''}">
                        <div class="user-avatar d-flex align-items-center justify-content-center me-3">
                            <i class="bi bi-person-circle fs-4 text-secondary"></i>
                        </div>
                        <div class="flex-grow-1">
                            <a href="/profil/${user.user_id}" class="text-decoration-none text-dark">
                                <span class="fw-medium">${user.user_name}</span>
                            </a>
                            <div class="small text-muted">
                                ${formatDate(user.date_created)}
                            </div>
                        </div>
                    </div>
                `;
            });
            
            html += `
                    </div>
                </div>
            `;
        }
    });
    
    html += '</div>';
    modalBody.innerHTML = html;
}

/**
 * Format date for display
 */
function formatDate(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diffTime = Math.abs(now - date);
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    
    if (diffDays === 1) {
        return 'vor 1 Tag';
    } else if (diffDays < 7) {
        return `vor ${diffDays} Tagen`;
    } else {
        return date.toLocaleDateString('de-DE', { 
            day: '2-digit', 
            month: '2-digit', 
            year: 'numeric' 
        });
    }
}

/**
 * Display error message in the modal
 */
function displayError(message) {
    const modalBody = document.getElementById('reactionsModalBody');
    modalBody.innerHTML = `
        <div class="text-center py-5">
            <i class="bi bi-exclamation-triangle fs-1 mb-3 d-block text-warning"></i>
            <h6 class="mb-2 text-danger">Fehler beim Laden</h6>
            <p class="mb-3 text-muted">${message}</p>
            <button type="button" class="btn btn-outline-primary btn-sm" onclick="location.reload()">
                <i class="bi bi-arrow-clockwise me-1"></i>Seite neu laden
            </button>
        </div>
    `;
}

