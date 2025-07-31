/**
 * Image Interactions Handler
 * Handles emoji reactions and comments for images in both gallery and fullscreen modes
 */

class ImageInteractions {
    constructor() {
        this.csrfToken = null;
        this.init();
    }

    init() {
        this.getCsrfToken();
        this.bindEvents();
        this.initializeExistingInteractions();
    }

    getCsrfToken() {
        const tokenElement = document.querySelector('[name=csrfmiddlewaretoken]');
        this.csrfToken = tokenElement ? tokenElement.value : '';
    }

    bindEvents() {
        // Use event delegation for dynamically added content
        document.addEventListener('click', this.handleClick.bind(this));
        document.addEventListener('keypress', this.handleKeypress.bind(this));
    }

    handleClick(e) {
        // Emoji reaction buttons
        if (e.target.classList.contains('emoji-btn')) {
            e.preventDefault();
            this.handleEmojiClick(e.target);
        }
        
        // Comment submission
        if (e.target.classList.contains('submit-comment-btn')) {
            e.preventDefault();
            this.handleCommentSubmit(e.target);
        }
        
        // Comment deletion
        if (e.target.closest('.delete-comment-btn')) {
            e.preventDefault();
            this.handleCommentDelete(e.target.closest('.delete-comment-btn'));
        }
        
        // Load more comments
        if (e.target.classList.contains('load-more-comments')) {
            e.preventDefault();
            this.handleLoadMoreComments(e.target);
        }
        
        // Comments toggle (for masonry refresh)
        if (e.target.closest('.comments-toggle')) {
            setTimeout(() => this.refreshMasonryLayout(), 350);
        }
    }

    handleKeypress(e) {
        if (e.key === 'Enter' && e.target.classList.contains('comment-input')) {
            e.preventDefault();
            const submitBtn = e.target.parentElement.querySelector('.submit-comment-btn');
            if (submitBtn) {
                this.handleCommentSubmit(submitBtn);
            }
        }
    }

    handleEmojiClick(button) {
        const emoji = button.dataset.emoji;
        const bildId = this.getBildIdFromButton(button);
        
        if (!bildId || !this.csrfToken) {
            console.error('Missing bild ID or CSRF token');
            return;
        }

        this.toggleReaction(bildId, emoji, button);
    }

    getBildIdFromButton(button) {
        // Try to get bildId from the closest interaction container
        const container = button.closest('[data-bild-id]');
        if (container) {
            return container.dataset.bildId;
        }
        
        // Fallback for fullscreen - look for fullscreen reactions container
        const fullscreenContainer = document.getElementById('fullscreenReactions');
        if (fullscreenContainer && button.closest('.modal')) {
            return fullscreenContainer.dataset.currentBildId;
        }
        
        return null;
    }

    async toggleReaction(bildId, emoji, button) {
        try {
            const response = await fetch(`/bild/${bildId}/reaction/toggle/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-CSRFToken': this.csrfToken
                },
                body: `emoji=${encodeURIComponent(emoji)}`
            });

            const data = await response.json();
            
            if (data.success) {
                console.log('Reaction response:', data);
                this.updateReactionStates(bildId, data);
            } else {
                console.error('Reaction error:', data.error);
            }
        } catch (error) {
            console.error('Network error:', error);
        }
    }

    updateReactionStates(bildId, data) {
        // Update all emoji buttons for this image (both gallery and fullscreen)
        const containers = [
            document.querySelector(`[data-bild-id="${bildId}"]`),
            document.querySelector('.modal.show') // Fullscreen modal if active
        ].filter(Boolean);

        containers.forEach(container => {
            this.updateEmojiButtons(container, data.user_reaction);
            this.updateReactionSummary(container, data.reaction_summary);
        });

        this.refreshMasonryLayout();
    }

    updateEmojiButtons(container, userReaction) {
        const emojiButtons = container.querySelectorAll('.emoji-btn');
        
        // Determine if we're in fullscreen context
        const isFullscreen = container.closest('.modal') !== null;
        
        emojiButtons.forEach(btn => {
            const isActive = userReaction && userReaction === btn.dataset.emoji;
            
            if (isFullscreen) {
                // Fullscreen uses light/outline-light classes
                if (isActive) {
                    btn.classList.remove('btn-outline-light');
                    btn.classList.add('btn-light');
                } else {
                    btn.classList.remove('btn-light');
                    btn.classList.add('btn-outline-light');
                }
            } else {
                // Gallery uses secondary/outline-secondary classes
                if (isActive) {
                    btn.classList.remove('btn-outline-secondary');
                    btn.classList.add('btn-secondary');
                } else {
                    btn.classList.remove('btn-secondary');
                    btn.classList.add('btn-outline-secondary');
                }
            }
        });
    }

    updateReactionSummary(container, reactionSummary) {
        const summaryContainer = container.querySelector('.reaction-summary');
        if (!summaryContainer) return;

        summaryContainer.innerHTML = '';
        reactionSummary.forEach(reaction => {
            const badge = document.createElement('span');
            badge.className = 'badge bg-light text-dark border';
            badge.textContent = `${reaction.emoji} ${reaction.count}`;
            summaryContainer.appendChild(badge);
        });
    }

    handleCommentSubmit(button) {
        const inputGroup = button.parentElement;
        const commentInput = inputGroup.querySelector('.comment-input');
        const comment = commentInput.value.trim();
        const bildId = this.getBildIdFromButton(button);

        if (!comment || !bildId || !this.csrfToken) {
            if (!comment) alert('Kommentar darf nicht leer sein');
            return;
        }

        this.submitComment(bildId, comment, commentInput);
    }

    async submitComment(bildId, comment, inputElement) {
        try {
            const response = await fetch(`/bild/${bildId}/comment/add/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-CSRFToken': this.csrfToken
                },
                body: `comment=${encodeURIComponent(comment)}`
            });

            const data = await response.json();
            
            if (data.success) {
                this.addCommentToList(bildId, data.comment);
                inputElement.value = '';
                this.updateCommentCount(bildId, data.comment_count);
            } else {
                alert(data.error);
            }
        } catch (error) {
            console.error('Comment submission error:', error);
        }
    }

    addCommentToList(bildId, comment, prepend = true) {
        const container = document.querySelector(`[data-bild-id="${bildId}"]`);
        if (!container) return;

        const commentsList = container.querySelector('.comments-list');
        if (!commentsList) return;

        const commentHtml = `
            <div class="comment-item border-bottom pb-2 mb-2" data-comment-id="${comment.id}">
                <div class="d-flex justify-content-between align-items-start">
                    <div class="flex-grow-1">
                        <small class="fw-bold">${comment.user_name}</small>
                        <small class="text-muted ms-2">${comment.date_created}</small>
                        <div class="mt-1">${comment.comment}</div>
                    </div>
                    ${comment.can_delete ? `
                        <button type="button" class="btn btn-sm btn-outline-danger delete-comment-btn" data-comment-id="${comment.id}" title="Löschen">
                            <i class="bi bi-trash"></i>
                        </button>
                    ` : ''}
                </div>
            </div>
        `;

        if (prepend) {
            commentsList.insertAdjacentHTML('afterbegin', commentHtml);
        } else {
            commentsList.insertAdjacentHTML('beforeend', commentHtml);
        }

        this.refreshMasonryLayout();
    }

    handleCommentDelete(button) {
        if (!confirm('Kommentar wirklich löschen?')) return;

        const commentId = button.dataset.commentId;
        const commentElement = button.closest('.comment-item');
        
        this.deleteComment(commentId, commentElement);
    }

    async deleteComment(commentId, commentElement) {
        try {
            const response = await fetch(`/bild/comment/${commentId}/remove/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.csrfToken
                }
            });

            const data = await response.json();
            
            if (data.success) {
                commentElement.remove();
                const bildId = this.getBildIdFromButton(commentElement);
                this.updateCommentCount(bildId, data.comment_count);
            } else {
                alert(data.error);
            }
        } catch (error) {
            console.error('Comment deletion error:', error);
        }
    }

    handleLoadMoreComments(button) {
        const bildId = this.getBildIdFromButton(button);
        const page = parseInt(button.dataset.page);
        
        this.loadMoreComments(bildId, page, button);
    }

    async loadMoreComments(bildId, page, button) {
        try {
            const response = await fetch(`/bild/${bildId}/interactions/?page=${page}`);
            const data = await response.json();
            
            if (data.success) {
                data.comments.forEach(comment => this.addCommentToList(bildId, comment, false));
                button.dataset.page = page + 1;
                if (!data.has_more_comments) {
                    button.style.display = 'none';
                }
            }
        } catch (error) {
            console.error('Load more comments error:', error);
        }
    }

    updateCommentCount(bildId, count) {
        const container = document.querySelector(`[data-bild-id="${bildId}"]`);
        if (!container) return;

        const commentCountEl = container.querySelector('.comment-count');
        if (commentCountEl) {
            commentCountEl.textContent = count;
        }

        this.refreshMasonryLayout();
    }

    initializeExistingInteractions() {
        // Load initial states for all visible interactions
        document.querySelectorAll('[data-bild-id]').forEach(container => {
            const bildId = container.dataset.bildId;
            this.loadUserReaction(bildId);
        });
    }

    async loadUserReaction(bildId) {
        try {
            const response = await fetch(`/bild/${bildId}/interactions/`);
            const data = await response.json();
            
            if (data.success) {
                const container = document.querySelector(`[data-bild-id="${bildId}"]`);
                if (container) {
                    this.updateEmojiButtons(container, data.user_reaction);
                    this.updateReactionSummary(container, data.reaction_summary);
                }
            }
        } catch (error) {
            console.error('Error loading user reaction:', error);
        }
    }

    refreshMasonryLayout() {
        // Dispatch custom event for masonry refresh
        window.dispatchEvent(new CustomEvent('refreshMasonry'));
        
        // Also directly try to refresh if masonry instance exists
        if (window.msnry && typeof window.msnry.layout === 'function') {
            setTimeout(() => window.msnry.layout(), 100);
        }
    }

    // Method to set fullscreen image context
    setFullscreenContext(bildId) {
        const fullscreenContainer = document.getElementById('fullscreenReactions');
        if (fullscreenContainer) {
            fullscreenContainer.dataset.currentBildId = bildId;
        }
        
        // Load reactions for fullscreen
        if (bildId) {
            this.loadUserReaction(bildId);
        }
    }
}

// Initialize when DOM is ready or immediately if already ready
function initializeImageInteractions() {
    if (!window.imageInteractions) {
        window.imageInteractions = new ImageInteractions();
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeImageInteractions);
} else {
    // DOM is already ready
    initializeImageInteractions();
}

// Export for use in other scripts
window.ImageInteractions = ImageInteractions; 