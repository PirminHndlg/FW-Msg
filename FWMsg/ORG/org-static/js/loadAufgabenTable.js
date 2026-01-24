/**
 * Aufgaben Table Loader - JSON-based dynamic table builder
 * Builds the complete task table from JSON data for better performance
 */

// ========================================
// UTILITY FUNCTIONS
// ========================================

/**
 * Get CSRF token from cookies
 */
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

/**
 * Format date to German format (dd.mm.yy)
 */
function formatDate(dateString) {
    if (!dateString) return '';
    const date = new Date(dateString);
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const year = String(date.getFullYear()).slice(-2);
    return `${day}.${month}.${year}`;
}

/**
 * Format date to full German format (dd.mm.yyyy)
 */
function formatDateFull(dateString) {
    if (!dateString) return '';
    const date = new Date(dateString);
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const year = date.getFullYear();
    return `${day}.${month}.${year}`;
}

/**
 * Compare dates (returns true if date1 <= date2)
 */
function isDateBeforeOrEqual(dateString1, dateString2) {
    if (!dateString1 || !dateString2) return false;
    const date1 = new Date(dateString1);
    const date2 = new Date(dateString2);
    return date1 <= date2;
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Build URL from template with ID substitution
 */
function buildUrl(urlTemplate, id) {
    return urlTemplate.replace('{id}', id);
}

/**
 * Build URL with query parameters
 */
function buildUrlWithNext(urlTemplate, id, nextUrl) {
    const url = buildUrl(urlTemplate, id);
    return `${url}?next=${nextUrl}`;
}

// ========================================
// TABLE BUILDER FUNCTIONS
// ========================================

/**
 * Build the complete table HTML from JSON data
 */
function buildTableFromJSON(data) {
    const { users, aufgaben, user_aufgaben_assigned, user_aufgaben_eligible, today, current_person_cluster } = data;
    
    const tableHtml = `
        <div class="table-responsive">
            <table class="table mb-0 align-middle table-borderless">
                <thead>
                    ${buildTableHeader(aufgaben, current_person_cluster)}
                </thead>
                <tbody>
                    ${buildTableRows(users, aufgaben, user_aufgaben_assigned, user_aufgaben_eligible, today)}
                    <tr class="h-100"></tr>
                </tbody>
            </table>
        </div>
    `;
    
    return tableHtml;
}

/**
 * Build table header
 */
function buildTableHeader(aufgaben, person_cluster) {
    const aufgabenHeaders = aufgaben.map(aufgabe => `
        <th class="text-center bg-white p-1 sticky-top border-end" style="box-shadow: 2px 2px 0 0 #dee2e6;">
            <div class="d-flex gap-1 align-items-center justify-content-center">
            ${aufgabe.beschreibung || aufgabe.mitupload || aufgabe.wiederholung ? `
                <div class="d-flex gap-0 align-items-center flex-column">
                    ${aufgabe.beschreibung ? `
                        <a class="btn p-0" data-bs-toggle="tooltip" data-bs-title="Beschreibung: ${escapeHtml(aufgabe.beschreibung)}">
                            <i class="bi bi-info-circle"></i>
                        </a>
                    ` : ''}
                    ${aufgabe.mitupload ? `
                        <a class="btn p-0" data-bs-toggle="tooltip" data-bs-title="Diese Aufgabe erfordert eine Datei">
                            <i class="bi bi-file-earmark-arrow-up text-success"></i>
                        </a>
                    ` : ''}
                    ${aufgabe.wiederholung ? `
                        <a class="btn p-0" data-bs-toggle="tooltip" data-bs-title="Mit Wiederholung">
                            <i class="bi bi-repeat"></i>
                        </a>
                    ` : ''}
                </div>
                ` : ''}
                <div class="dropdown d-inline">
                    <button class="btn btn-sm dropdown-toggle p-0 d-flex align-items-center" type="button" data-bs-toggle="dropdown" aria-expanded="false">
                        <p class="text-wrap m-0">${escapeHtml(aufgabe.name)}</p>
                    </button>
                    <ul class="dropdown-menu z-1020">
                        <li>
                            <a href="${buildUrlWithNext(window.DJANGO_URLS.editAufgabe, aufgabe.id, window.DJANGO_URLS.listAufgabenTable)}" class="dropdown-item">
                                <i class="bi bi-pencil me-2"></i> Bearbeiten
                            </a>
                        </li>
                        <li>
                            <a class="dropdown-item" data-bs-toggle="modal" data-bs-target="#taskCountryModal" onclick="setTaskId(${aufgabe.id}, '${escapeHtml(aufgabe.name)}')">
                                <i class="bi bi-globe-americas me-2"></i> Einem Einsatzland zuweisen
                            </a>
                        </li>
                        <li>
                            <button type="button" class="dropdown-item" onclick="assignTaskToAll('${aufgabe.id}', '${person_cluster}')">
                                <i class="bi bi-people-fill me-2"></i> Allen zuweisen
                            </button>
                        </li>
                    </ul>
                </div>
            </div>
        </th>
    `).join('');
    
    return `
        <tr class="">
             <th class="sticky-right p-1 align-bottom z-1000" style="min-width:200px; position: sticky; left: 0; top: 0; box-shadow: 2px 2px 0 0 #dee2e6;">
                <div class="input-group gap-0 rounded-pill border shadow-sm bg-white align-items-center" style="min-width: 150px;">
                    <span class="input-group-text bg-transparent border-0 pe-0" style="font-size:1.1em;">
                        <i class="bi bi-search text-secondary"></i>
                    </span>
                    <input id="userSearch"
                        type="text"
                        class="form-control border-0 bg-white px-1"
                        style="min-width:80px; font-size: 1em; box-shadow: none;"
                        placeholder="Suchen..."
                        autocomplete="off"
                        oninput="searchHandler(this.value)"
                    >
                    <button class="btn btn-link text-decoration-none ps-0"
                        type="button"
                        tabindex="-1"
                        aria-label="Suche zurücksetzen"
                        onclick="document.getElementById('userSearch').value = ''; searchHandler('');">
                        <i class="bi bi-x-circle text-danger" style="font-size:1.2em;"></i>
                    </button>
                </div>
            </th>
            ${aufgabenHeaders}
            <th class="p-0 sticky-right with-border-before" style="box-shadow: 2px 2px 0 0 #dee2e6;">
                <div class="d-flex gap-1 align-items-center">
                    <a href="${window.DJANGO_URLS.addAufgabe}?next=${window.DJANGO_URLS.listAufgabenTable}" class="btn px-4" data-bs-toggle="tooltip" data-bs-title="Neue Aufgabe erstellen">
                        <i class="bi bi-plus-circle"></i>
                    </a>
                </div>
            </th>
        </tr>
        
        <style>
            @media (min-width: 768px) {
                .sticky-right {
                    position: sticky;
                    right: 0;
                    background-color: var(--bs-body-bg); 
                    z-index: 1;
                }
            }
            
            .sticky-top {
                position: sticky;
                top: 0;
                z-index: 1010;
            }
            
            .border-bottom {
                border-bottom-width: 1px !important;
                border-bottom-style: solid !important;
            }
            
            .border-end {
                border-right-width: 1px !important;
                border-right-style: solid !important;
            }
            
            th.with-border::after {
                content: '';
                position: absolute;
                top: 0;
                right: 1px;
                bottom: 0;
                width: 1px;
                background: linear-gradient(to right, rgba(0, 0, 0, 0.4), rgba(0, 0, 0, 0));
                color: rgba(var(--bs-dark-rgb), var(--bs-border-opacity));
            }
            
            th.with-border-before::before {
                content: '';
                position: absolute;
                top: 0;
                left: 1px;
                bottom: 0;
                width: 1px;
                background: linear-gradient(to right, rgba(0, 0, 0, 0.4), rgba(0, 0, 0, 0));
                color: rgba(var(--bs-dark-rgb), var(--bs-border-opacity));
            }
            
            .z-1000 {
                z-index: 1000;
            }

            .z-1020 {
                z-index: 1020;
            }
            
            .search-container {
                position: sticky;
                top: 0;
                z-index: 1021;
                background-color: var(--bs-body-bg);
            }
            
            .search-container .input-group {
                width: 100%;
            }
            
            .search-container .input-group-text {
                background-color: var(--bs-body-bg);
            }
        </style>
    `;
}

/**
 * Build table rows for all users
 */
function buildTableRows(users, aufgaben, user_aufgaben_assigned, user_aufgaben_eligible, today) {
    return users.map(user => {
        return buildTableRow(user, aufgaben, user_aufgaben_assigned, user_aufgaben_eligible, today);
    }).join('');
}

/**
 * Build a single table row for a user
 */
function buildTableRow(user, aufgaben, user_aufgaben_assigned, user_aufgaben_eligible, today) {
    const userAssigned = user_aufgaben_assigned[user.id] || {};
    const userEligible = user_aufgaben_eligible[user.id] || [];
    const eligibleSet = new Set(userEligible);
    
    const cells = aufgaben.map((aufgabe) => {
        // Check if user has this aufgabe assigned
        const userAufgabe = userAssigned[aufgabe.id];
        if (userAufgabe) {
            // User has this aufgabe assigned - pass the full object
            return buildTableCell(user, aufgabe, userAufgabe, today);
        } else if (eligibleSet.has(aufgabe.id)) {
            // User is eligible but aufgabe not assigned - pass aufgabe.id as number
            return buildTableCell(user, aufgabe, aufgabe.id, today);
        } else {
            // User is not eligible - pass null
            return buildTableCell(user, aufgabe, null, today);
        }
    }).join('');
    
    return `
        <tr class="border-bottom" data-search-term="${escapeHtml(user.first_name || '')} ${escapeHtml(user.last_name || user.username || '')}">
            <th class="p-0 ps-2" style="max-width: 30vw; height: 50px; box-shadow: 2px 2px 0 0 #dee2e6;">
                <div class="d-flex gap-1 align-items-center justify-content-between">
                    ${escapeHtml(user.first_name || '')} ${escapeHtml(user.last_name || user.username || '')}
                </div>
            </th>
            ${cells}
            <td class="text-center p-0 rounded-4"></td>
        </tr>
    `;
}

/**
 * Build a single table cell for a user-aufgabe combination
 */
function buildTableCell(user, aufgabe, userAufgabe, today) {
    // If userAufgabe is null, show nothing (not eligible)
    if (userAufgabe === null) {
        return `
            <td class="text-center p-0 rounded-4">
                <div class="p-0 m-0">
                    <a data-bs-toggle="tooltip" data-bs-title="Aufgabe nicht für diese Benutzergruppe" style="cursor: help;">
                        <i class="bi bi-x-lg text-danger"></i>
                    </a>
                </div>
            </td>
        `;
    }
    
    // If userAufgabe is a number (aufgabe.id), show assign button
    if (typeof userAufgabe === 'number') {
        return `
            <td class="text-center p-0 rounded-4">
                <div class="p-0 m-0">
                    <button type="button" class="btn btn-sm" 
                        onclick="assignTask('${user.id}', '${userAufgabe}')"
                        data-tooltip="Aufgabe zuweisen">
                        <i class="bi bi-plus-circle"></i>
                    </button>
                </div>
            </td>
        `;
    }
    
    // Otherwise, it's a user_aufgabe object
    const ua = userAufgabe.user_aufgabe;
    const zwischenschritteDoneOpen = userAufgabe.zwischenschritte_done_open;
    const zwischenschritteDone = userAufgabe.zwischenschritte_done;
    
    // Determine background color
    let bgClass = 'bg-dark bg-opacity-10';
    if (ua.erledigt) {
        bgClass = 'bg-success bg-opacity-25';
    } else if (ua.pending) {
        bgClass = 'bg-warning bg-opacity-25';
    } else if (isDateBeforeOrEqual(ua.faellig, today)) {
        bgClass = 'bg-danger bg-opacity-25';
    }
    
    return `
        <td class="text-center p-0 rounded-4 ${bgClass}"
            id="task-table-row-${ua.id}"
            data-task-id="${ua.id}">
            ${buildCompletedTemplate(ua, user)}
            ${buildPendingTemplate(ua, user, zwischenschritteDoneOpen, zwischenschritteDone)}
            ${buildUpcomingTemplate(ua, user, today)}
        </td>
    `;
}

/**
 * Build completed task template
 */
function buildCompletedTemplate(ua, user) {
    const downloadedBy = ua.file_downloaded_of_names ? 
        `Heruntergeladen von ${ua.file_downloaded_of_names}` : 
        'Noch nicht heruntergeladen';
    
    return `
        <div id="completed-task-template-${ua.id}" class="${!ua.erledigt ? 'd-none' : ''}">
            ${ua.file ? `
                <a href="${buildUrl(window.DJANGO_URLS.downloadAufgabe, ua.id)}" 
                    class="btn btn-sm btn-outline-primary download-btn mt-1"
                    target="_blank"
                    data-bs-toggle="tooltip"
                    data-bs-placement="top"
                    title="${escapeHtml(downloadedBy)}">
                    <i class="bi bi-download"></i>
                </a>
            ` : ''}
            <div class="dropdown d-inline">
                <button class="btn btn-sm dropdown-toggle" type="button" data-bs-toggle="dropdown" aria-expanded="false">
                    <span data-tooltip="Erledigt am ${formatDateFull(ua.erledigt_am)}"
                    class="badge bg-success">Erledigt</span>
                </button>
                <ul class="dropdown-menu">
                    <li>
                        <a class="dropdown-item" href="${buildUrlWithNext(window.DJANGO_URLS.editUserAufgaben, ua.id, window.DJANGO_URLS.listAufgabenTable)}">
                            <i class="bi bi-pencil me-2"></i>Bearbeiten
                        </a>
                    </li>
                    <li>
                        <button type="button" class="dropdown-item text-danger" onclick="updateTaskStatus('${ua.id}', false, false)">
                            <i class="bi bi-x-lg me-2"></i>Als nicht erledigt markieren
                        </button>
                    </li>
                    <li>
                        <button type="button" class="dropdown-item text-warning" onclick="updateTaskStatus('${ua.id}', true, false)">
                            <i class="bi bi-arrow-counterclockwise me-2"></i>Als pending markieren
                        </button>
                    </li>
                    ${ua.file ? `
                        <li>
                            <button type="button" class="dropdown-item text-danger" onclick="showDeleteTaskModal('${ua.id}', '${escapeHtml(ua.aufgabe_name)}', '${escapeHtml(ua.file_name)}', '${escapeHtml(user.first_name)} ${escapeHtml(user.last_name)}')">
                                <i class="bi bi-trash me-2"></i>Datei löschen
                            </button>
                        </li>
                    ` : ''}
                </ul>
            </div>
        </div>
    `;
}

/**
 * Build pending task template
 */
function buildPendingTemplate(ua, user, zwischenschritteDoneOpen, zwischenschritteDone) {
    return `
        <div id="pending-task-template-${ua.id}" class="${!ua.pending || ua.erledigt ? 'd-none' : ''}">
            ${ua.file ? `
                <a href="${buildUrl(window.DJANGO_URLS.downloadAufgabe, ua.id)}"
                    class="btn btn-sm btn-outline-primary download-btn" 
                    target="_blank"
                    data-bs-toggle="tooltip"
                    data-bs-placement="top"
                    title="${escapeHtml(ua.file_downloaded_of_names ? `Heruntergeladen von ${ua.file_downloaded_of_names}` : 'Noch nicht heruntergeladen')}">
                    <i class="bi bi-download"></i>
                </a>
            ` : ''}
            <div class="dropdown d-inline task-status-buttons">
                <button class="btn btn-sm dropdown-toggle btn-pending btn-zwischenschritte" 
                    type="button" 
                    data-bs-toggle="dropdown" 
                    data-user-aufgabe-id="${ua.id}"
                    data-loaded="false"
                    aria-expanded="false">
                    <span id="pending-badge-${ua.id}" class="badge ${zwischenschritteDone ? 'bg-warning border border-2 border-success' : 'bg-warning'}">
                        Pending ${zwischenschritteDoneOpen || ''}
                    </span>
                </button>
                <ul class="dropdown-menu">
                    <li>
                        <a class="dropdown-item" href="${buildUrlWithNext(window.DJANGO_URLS.editUserAufgaben, ua.id, window.DJANGO_URLS.listAufgabenTable)}">
                            <i class="bi bi-pencil me-2"></i>Bearbeiten
                        </a>
                    </li>
                    <li>
                        <button type="button" class="dropdown-item" data-bs-toggle="modal" data-bs-target="#taskZwischenschritteModal" onclick="loadZwischenschritte('${ua.id}')">
                            <i class="bi bi-list me-2"></i>Zwischenschritte anzeigen
                        </button>
                    </li>
                    <li>
                        <button type="button" class="dropdown-item text-danger" onclick="updateTaskStatus('${ua.id}', false, false)">
                            <i class="bi bi-x-lg me-2"></i>Als nicht erledigt markieren
                        </button>
                    </li>
                    <li>
                        <button type="button" class="dropdown-item text-success" onclick="updateTaskStatus('${ua.id}', false, true)">
                            <i class="bi bi-check-lg me-2"></i>Als erledigt markieren
                        </button>
                    </li>
                </ul>
            </div>
        </div>
    `;
}

/**
 * Build upcoming task template
 */
function buildUpcomingTemplate(ua, user, today) {
    const isDanger = isDateBeforeOrEqual(ua.faellig, today);
    const badgeClass = isDanger ? 'bg-danger' : 'bg-dark';
    
    return `
        <div id="upcoming-task-template-${ua.id}" class="${ua.erledigt || ua.pending ? 'd-none' : ''}">
            <div class="dropdown d-inline task-status-buttons">
                <button class="btn btn-sm dropdown-toggle" type="button" data-bs-toggle="dropdown" aria-expanded="false">
                    <span data-tooltip="Fällig am ${formatDateFull(ua.faellig)}"
                    class="badge ${badgeClass}">${formatDate(ua.faellig)}</span>
                </button>
                <ul class="dropdown-menu">
                    <li>
                        <a class="dropdown-item" href="${buildUrlWithNext(window.DJANGO_URLS.editUserAufgaben, ua.id, window.DJANGO_URLS.listAufgabenTable)}">
                            <i class="bi bi-pencil me-2"></i>Bearbeiten
                        </a>
                    </li>
                    <li>
                        <button type="button" class="dropdown-item btn-reminder ${!ua.mail_notifications ? 'disabled' : ''}" 
                            ${ua.currently_sending ? 'disabled' : ''} 
                            onclick="${ua.mail_notifications && !ua.currently_sending ? `sendTaskReminder(this, '${ua.id}')` : ''}">
                            ${ua.mail_notifications ? `
                                <i class="bi bi-bell-fill me-2"></i>Erinnern
                                ${ua.last_reminder ? `<small class="text-muted last-reminder-date">(Zuletzt ${formatDate(ua.last_reminder)})</small>` : ''}
                            ` : `
                                <i class="bi bi-bell-slash-fill me-2"></i>${escapeHtml(user.first_name)} hat E-Mail-Benachrichtigungen deaktiviert
                            `}
                        </button>
                    </li>
                    <li>
                        <button type="button" class="dropdown-item text-warning btn-pending" onclick="updateTaskStatus('${ua.id}', true, false)">
                            <i class="bi bi-arrow-counterclockwise me-2"></i>Als pending markieren
                        </button>
                    </li>
                    <li>
                        <button type="button" class="dropdown-item text-success btn-done" onclick="updateTaskStatus('${ua.id}', false, true)">
                            <i class="bi bi-check-lg me-2"></i>Als erledigt markieren
                        </button>
                    </li>   
                </ul>
            </div>
        </div>
    `;
}

// ========================================
// ZWISCHENSCHRITTE FUNCTIONS
// ========================================

/**
 * Lazy loading of zwischenschritte data
 */
function loadZwischenschritte(taskId) {
    const btn = document.querySelector(`.btn-zwischenschritte[data-user-aufgabe-id="${taskId}"]`);
    if (btn && btn.dataset.loaded === 'false') {
        // Set loading state
        document.getElementById('zwischenschritteModalContent').innerHTML = `
            <div class="d-flex justify-content-center p-5">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
            </div>
        `;
        
        // Fetch data
        fetch(`${window.DJANGO_URLS.getAufgabenZwischenschritte}?taskId=${taskId}`)
            .then(response => response.json())
            .then(data => {
                // Update modal content
                let content = `
                    <h5>${escapeHtml(data.task_name)} - ${escapeHtml(data.user_name)}</h5>
                    <ul class="list-group">
                `;
                
                if (data.zwischenschritte.length === 0) {
                    content += `<li class="list-group-item">Keine Zwischenschritte definiert</li>`;
                } else {
                    data.zwischenschritte.forEach(zs => {
                        content += `
                            <li class="list-group-item d-flex justify-content-between align-items-center">
                                <div>
                                    <strong>${escapeHtml(zs.name)}</strong>
                                    ${zs.beschreibung ? `<p class="mb-0 small text-muted">${escapeHtml(zs.beschreibung)}</p>` : ''}
                                </div>
                                <div class="form-check form-switch">
                                    <input class="form-check-input" type="checkbox" 
                                        onchange="toggleZwischenschritt(${taskId}, ${zs.id}, this.checked)"
                                        ${zs.erledigt ? 'checked' : ''}
                                    >
                                </div>
                            </li>
                        `;
                    });
                }
                
                content += `</ul>`;
                document.getElementById('zwischenschritteModalContent').innerHTML = content;
                
                // Mark as loaded
                btn.dataset.loaded = 'true';
            })
            .catch(error => {
                console.error('Error loading zwischenschritte:', error);
                document.getElementById('zwischenschritteModalContent').innerHTML = `
                    <div class="alert alert-danger">
                        Fehler beim Laden der Zwischenschritte
                    </div>
                `;
            });
    }
}

/**
 * Toggle zwischenschritt status
 */
function toggleZwischenschritt(taskId, zwischenschrittId, status) {
    fetch(window.DJANGO_URLS.toggleZwischenschrittStatus, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({
            taskId: taskId,
            zwischenschrittId: zwischenschrittId,
            status: status
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Update the UI if needed
            const btn = document.querySelector(`.btn-zwischenschritte[data-user-aufgabe-id="${taskId}"]`);
            if (btn && data.zwischenschritte_done_open) {
                const badge = btn.querySelector('.badge');
                if (badge) {
                    // Update badge text
                    badge.innerHTML = `Pending ${data.zwischenschritte_done_open}`;
                    
                    // Update badge styling based on completion
                    if (data.zwischenschritte_done) {
                        badge.classList.add('border', 'border-2', 'border-success');
                    } else {
                        badge.classList.remove('border', 'border-2', 'border-success');
                    }
                }
            }
            
            // Update cell class if all zwischenschritte are done
            if (data.zwischenschritte_done) {
                btn.closest('td').classList.add('table-success');
            } else {
                btn.closest('td').classList.remove('table-success');
            }
        }
    })
    .catch(error => console.error('Error toggling zwischenschritt:', error));
}

// Make functions globally available
window.loadZwischenschritte = loadZwischenschritte;
window.toggleZwischenschritt = toggleZwischenschritt;
window.buildTableFromJSON = buildTableFromJSON;

