document.addEventListener('DOMContentLoaded', function () {
    // Initialize all tooltips
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));
});

function getModalHtmlDokument(folderName, ordner_id, doc_data = {}) {
    return `
        <div class="modal fade" id="addDokumentModal" tabindex="-1" aria-labelledby="addDokumentModalLabel" aria-hidden="true">
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content rounded-4">
                    <div class="modal-header">
                        <div>
                            <h5 class="modal-title mb-1" id="addDokumentModalLabel">${doc_data.titel ? 'Dokument bearbeiten' : 'Neues Dokument hinzufügen'}</h5>
                            <small class="text-muted"><i class="bi bi-folder me-1"></i>${folderName}</small>
                        </div>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        <form id="dokumentForm" method="post" enctype="multipart/form-data" action="/dokumente/add/">
                            ${document.getElementsByName('csrfmiddlewaretoken')[0].outerHTML}
                            <input type="hidden" name="ordner" value="${ordner_id}">
                            <input type="hidden" name="dokument_id" value="${doc_data.id || ''}">
                        
                            <div class="mb-2 text-center d-flex justify-content-center align-items-center gap-1">
                                <i class="bi bi-info-circle me-1"></i>
                                <small class="text-muted">Alle Felder sind optional und können weggelassen werden.</small>
                            </div>

                            <div class="mb-3">
                                <label for="titel" class="form-label">Titel</label>
                                <input type="text" class="form-control rounded-4" id="titel" name="titel" placeholder="..." value="${doc_data.titel || ''}">
                            </div>
                            
                            <div class="mb-3">
                                <label for="beschreibung" class="form-label">Beschreibung</label>
                                <textarea class="form-control rounded-4" id="beschreibung" name="beschreibung" rows="3" placeholder="...">${doc_data.beschreibung || ''}</textarea>
                            </div>

                            <div class="mb-3">
                                <label for="link" class="form-label">Link</label>
                                <input type="text" class="form-control rounded-4" id="link" name="link" placeholder="https://www.example.com" value="${doc_data.link || ''}">
                            </div>

                            ${doc_data.dokument ? `<p class="text-danger">Das Dokument ${doc_data.dokument} wird gelöscht, wenn ein neues Dokument hochgeladen wird.</p>` : ''}

                            <div class="mb-3">
                                <label for="dokument" class="form-label">Dokument</label>
                                <input type="file" class="form-control rounded-4" id="dokument" name="dokument">
                            </div>

                            <div id="fw_darf_bearbeiten_container" class="mb-3">
                                <label for="fw_darf_bearbeiten" class="form-label">Freiwillige dürfen dieses Dokument bearbeiten/löschen</label>
                                <input type="checkbox" class="form-check-input" id="fw_darf_bearbeiten" name="fw_darf_bearbeiten" ${doc_data.fw_darf_bearbeiten == 'True' ? 'checked' : ''}>
                            </div>
                            
                            <div class="d-flex justify-content-end gap-2">
                                <button type="button" class="btn btn-outline-secondary rounded-4" data-bs-dismiss="modal">Abbrechen</button>
                                <button type="submit" class="btn btn-primary rounded-4">Speichern</button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    `;
}

function getModalHtmlOrdner(ordner_id = '', ordner_name = '') {
    return `
        <div class="modal fade" id="addOrdnerModal" tabindex="-1" aria-labelledby="addOrdnerModalLabel" aria-hidden="true">
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content rounded-4">
                    <div class="modal-header">
                        <h5 class="modal-title" id="addOrdnerModalLabel">${ordner_name ? 'Ordner bearbeiten' : 'Neuer Ordner'}</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        <form id="ordnerForm" method="post" action="/dokumente/add_ordner/">
                            ${document.getElementsByName('csrfmiddlewaretoken')[0].outerHTML}
                            
                            <input type="hidden" name="ordner_id" value="${ordner_id || ''}">
                            <div class="mb-3">
                                <label for="ordner_name" class="form-label">Ordnername</label>
                                <input type="text" class="form-control rounded-4" id="ordner_name" name="ordner_name" value="${ordner_name || ''}">
                            </div>

                            <div class="d-flex justify-content-end gap-2">
                                <button type="button" class="btn btn-outline-secondary rounded-4" data-bs-dismiss="modal">Abbrechen</button>
                                <button type="submit" class="btn btn-primary rounded-4">Speichern</button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    `;
}

function addOrdner() {
    // Create modal structure
    const modalHtml = getModalHtmlOrdner();

    // Add modal to body
    document.body.insertAdjacentHTML('beforeend', modalHtml);

    // Initialize and show modal
    const modal = new bootstrap.Modal(document.getElementById('addOrdnerModal'));
    modal.show();

    // Remove modal from DOM after it's hidden
    document.getElementById('addOrdnerModal').addEventListener('hidden.bs.modal', function () {
        this.remove();
    });
}

function editOrdner(ordner_id, ordner_name) {
    const modalHtml = getModalHtmlOrdner(ordner_id, ordner_name);
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    const modal = new bootstrap.Modal(document.getElementById('addOrdnerModal'));
    modal.show();
    document.getElementById('addOrdnerModal').addEventListener('hidden.bs.modal', function () {
        this.remove();
    });
}

function addDokument(ordner_id) {
    // Get folder name from the DOM
    const folderName = document.querySelector(`button[data-bs-target="#collapse${ordner_id}"] span:first-child`).textContent.trim();
    const modalHtml = getModalHtmlDokument(folderName, ordner_id);

    // Add modal to body
    document.body.insertAdjacentHTML('beforeend', modalHtml);

    // Initialize and show modal
    const modal = new bootstrap.Modal(document.getElementById('addDokumentModal'));
    modal.show();

    // Remove modal from DOM after it's hidden
    document.getElementById('addDokumentModal').addEventListener('hidden.bs.modal', function () {
        this.remove();
    });

    if (!is_org) {
        document.getElementById('fw_darf_bearbeiten_container').style.display = 'none';
    }
}

function removeDokument(dokument_id, dokument_name, url) {
    if (confirm(`Möchten Sie das Dokument "${dokument_name}" wirklich löschen?`)) {
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = url;

        // Add CSRF token
        const csrfToken = document.getElementsByName('csrfmiddlewaretoken')[0].value;
        const csrfInput = document.createElement('input');
        csrfInput.type = 'hidden';
        csrfInput.name = 'csrfmiddlewaretoken';
        csrfInput.value = csrfToken;
        form.appendChild(csrfInput);

        // Add document ID
        const idInput = document.createElement('input');
        idInput.type = 'hidden';
        idInput.name = 'dokument_id';
        idInput.value = dokument_id;
        form.appendChild(idInput);

        document.body.appendChild(form);
        form.submit();
    }
}

function editDokument(dokument_id) {
    const doc_div = document.getElementById(`dokument-${dokument_id}`);
    const doc_data = doc_div.dataset;
    const modalHtml = getModalHtmlDokument(doc_data.folder_name, doc_data.folder_id, doc_data);
    
    // Add modal to body
     document.body.insertAdjacentHTML('beforeend', modalHtml);

     // Initialize and show modal
     const modal = new bootstrap.Modal(document.getElementById('addDokumentModal'));
     modal.show();
 
     // Remove modal from DOM after it's hidden
     document.getElementById('addDokumentModal').addEventListener('hidden.bs.modal', function () {
         this.remove();
     });
 
     if (!is_org) {
         document.getElementById('fw_darf_bearbeiten_container').style.display = 'none';
     }
}

function removeOrdner(ordner_id, ordner_name) {
    if (confirm(`Möchten Sie den Ordner "${ordner_name}" wirklich löschen?`)) {
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = '/dokumente/remove_ordner/';

        // Add CSRF token
        const csrfToken = document.getElementsByName('csrfmiddlewaretoken')[0].value;
        const csrfInput = document.createElement('input');
        csrfInput.type = 'hidden';
        csrfInput.name = 'csrfmiddlewaretoken';
        csrfInput.value = csrfToken;
        form.appendChild(csrfInput);

        // Add folder ID
        const idInput = document.createElement('input');
        idInput.type = 'hidden';
        idInput.name = 'ordner_id';
        idInput.value = ordner_id;
        form.appendChild(idInput);

        document.body.appendChild(form);
        form.submit();
    }
}