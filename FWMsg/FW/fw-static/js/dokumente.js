document.addEventListener('DOMContentLoaded', function () {
    // Initialize all tooltips
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));

    // Initialize modals
    const dokumentModal = new bootstrap.Modal(document.getElementById('dokumentModal'));
    const ordnerModal = new bootstrap.Modal(document.getElementById('ordnerModal'));

    // Reset forms when modals are hidden
    document.getElementById('dokumentModal').addEventListener('hidden.bs.modal', function () {
        document.getElementById('dokumentForm').reset();
        document.getElementById('existingDocumentWarning').classList.add('d-none');
        document.getElementById('dokumentModalLabel').textContent = 'Neues Dokument hinzufügen';
    });

    document.getElementById('ordnerModal').addEventListener('hidden.bs.modal', function () {
        document.getElementById('ordnerForm').reset();
        document.getElementById('ordnerModalLabel').textContent = 'Neuer Ordner';
    });
});

function addOrdner() {
    document.getElementById('ordnerIdInput').value = '';
    document.getElementById('ordnerModalLabel').textContent = 'Neuer Ordner';
    new bootstrap.Modal(document.getElementById('ordnerModal')).show();
}

function editOrdner(ordner_id, ordner_name, typ_id=null) {
    document.getElementById('ordnerIdInput').value = ordner_id;
    document.getElementById('ordner_name').value = ordner_name;
    document.getElementById('ordnerModalLabel').textContent = 'Ordner bearbeiten';
    if (typ_id) {
        document.getElementById('typ').value = typ_id;
    } else {
        document.getElementById('typ').value = '';
    }
    new bootstrap.Modal(document.getElementById('ordnerModal')).show();
}

function addDokument(ordner_id) {
    const folderName = document.querySelector(`button[data-bs-target="#collapse${ordner_id}"] span:first-child`).textContent.trim();
    
    document.getElementById('ordnerInput').value = ordner_id;
    document.getElementById('dokumentIdInput').value = '';
    document.getElementById('modalFolderName').textContent = folderName;
    document.getElementById('dokumentModalLabel').textContent = 'Neues Dokument hinzufügen';
    
    const modal = new bootstrap.Modal(document.getElementById('dokumentModal'));
    modal.show();

    if (!is_org) {
        document.getElementById('fw_darf_bearbeiten_container').style.display = 'none';
    }
}

function editDokument(dokument_id) {
    const doc_div = document.getElementById(`dokument-${dokument_id}`);
    const doc_data = doc_div.dataset;
    
    // Set form values
    document.getElementById('ordnerInput').value = doc_data.folder_id;
    document.getElementById('dokumentIdInput').value = dokument_id;
    document.getElementById('modalFolderName').textContent = doc_data.folder_name;
    document.getElementById('titel').value = doc_data.titel;
    document.getElementById('beschreibung').value = doc_data.beschreibung;
    document.getElementById('link').value = doc_data.link;
    document.getElementById('fw_darf_bearbeiten').checked = doc_data.fw_darf_bearbeiten === 'True';
    
    // Show existing document warning if applicable
    if (doc_data.dokument) {
        document.getElementById('existingDocumentWarning').classList.remove('d-none');
        document.getElementById('existingDocumentName').textContent = doc_data.dokument;
    }

    document.getElementById('dokumentModalLabel').textContent = 'Dokument bearbeiten';
    
    const modal = new bootstrap.Modal(document.getElementById('dokumentModal'));
    modal.show();

    if (!is_org) {
        document.getElementById('fw_darf_bearbeiten_container').style.display = 'none';
    }
}

function removeDokument(dokument_id, dokument_name, url) {
    if (confirm(`Möchten Sie das Dokument "${dokument_name}" wirklich löschen?`)) {
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = url;

        const csrfToken = document.getElementsByName('csrfmiddlewaretoken')[0].value;
        const csrfInput = document.createElement('input');
        csrfInput.type = 'hidden';
        csrfInput.name = 'csrfmiddlewaretoken';
        csrfInput.value = csrfToken;
        form.appendChild(csrfInput);

        const idInput = document.createElement('input');
        idInput.type = 'hidden';
        idInput.name = 'dokument_id';
        idInput.value = dokument_id;
        form.appendChild(idInput);

        document.body.appendChild(form);
        form.submit();
    }
}

function removeOrdner(ordner_id, ordner_name) {
    if (confirm(`Möchten Sie den Ordner "${ordner_name}" wirklich löschen?`)) {
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = '/dokumente/remove_ordner/';

        const csrfToken = document.getElementsByName('csrfmiddlewaretoken')[0].value;
        const csrfInput = document.createElement('input');
        csrfInput.type = 'hidden';
        csrfInput.name = 'csrfmiddlewaretoken';
        csrfInput.value = csrfToken;
        form.appendChild(csrfInput);

        const idInput = document.createElement('input');
        idInput.type = 'hidden';
        idInput.name = 'ordner_id';
        idInput.value = ordner_id;
        form.appendChild(idInput);

        document.body.appendChild(form);
        form.submit();
    }
}