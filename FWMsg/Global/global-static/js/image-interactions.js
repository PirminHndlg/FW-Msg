/**
 * Image Interactions Handler
 * Handles emoji reactions and comments for images in both gallery and fullscreen modes
 */

function interactionButtonPressed(button) {
    const emoji = button.getAttribute("data-emoji");
    const interactionUrl = button.parentElement.getAttribute("data-interaction-url");
    
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

