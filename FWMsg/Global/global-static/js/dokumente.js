document.addEventListener('DOMContentLoaded', function () {
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

function editOrdner(ordner_id, ordner_name, typ_id=null, color_id=null) {
    document.getElementById('ordnerIdInput').value = ordner_id;
    document.getElementById('ordner_name').value = ordner_name;
    document.getElementById('ordnerModalLabel').textContent = 'Ordner bearbeiten';

    let person_cluster_ids = typ_id.split(',');

    for (const person_cluster_id of person_cluster_ids) {
        let checkbox = document.getElementById('ordner_person_cluster_' + person_cluster_id);
        if (checkbox) {
            checkbox.checked = true;
        }
    }

    if (color_id) {
        document.getElementById('color').value = color_id;
    } else {
        document.getElementById('color').value = '';
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
        document.getElementById('darf_bearbeiten_container').style.display = 'none';
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

    let darf_bearbeiten_inputs = doc_div.querySelectorAll('input[name="darf_bearbeiten"]');
    for (const darf_bearbeiten_input of darf_bearbeiten_inputs) {
        let darf_bearbeiten_id = darf_bearbeiten_input.value;
        let checkbox = document.getElementById(`person_cluster_${darf_bearbeiten_id}`);
        if (checkbox) {
            checkbox.checked = true;
        }
    }
    
    // Show existing document warning if applicable
    if (doc_data.dokument) {
        document.getElementById('existingDocumentWarning').classList.remove('d-none');
        document.getElementById('existingDocumentName').textContent = doc_data.dokument;
    }

    document.getElementById('dokumentModalLabel').textContent = 'Dokument bearbeiten';

    const modal = new bootstrap.Modal(document.getElementById('dokumentModal'));
    modal.show();

    if (!is_org) {
        document.getElementById('darf_bearbeiten_container').style.display = 'none';
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

async function copyFolderLink(relativeUrl, linkElement) {
    try {
        // Build the absolute URL from the relative URL
        const absoluteUrl = window.location.origin + relativeUrl;
        
        // Modern browsers - use Clipboard API
        if (navigator.clipboard && window.isSecureContext) {
            await navigator.clipboard.writeText(absoluteUrl);
        } else {
            // Fallback for older browsers
            const textArea = document.createElement('textarea');
            textArea.value = absoluteUrl;
            textArea.style.position = 'fixed';
            textArea.style.left = '-999999px';
            textArea.style.top = '-999999px';
            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();
            document.execCommand('copy');
            textArea.remove();
        }
        
        // Find the dropdown button to show feedback
        const dropdownButton = linkElement.closest('.dropdown').querySelector('[data-bs-toggle="dropdown"]');
        if (dropdownButton) {
            const icon = dropdownButton.querySelector('i');
            const originalClass = icon.className;
            
            // Change icon to checkmark temporarily
            icon.className = 'bi bi-check';
            
            // Close the dropdown
            const dropdown = bootstrap.Dropdown.getInstance(dropdownButton);
            if (dropdown) {
                dropdown.hide();
            }
            
            // Reset icon after 2 seconds
            setTimeout(() => {
                icon.className = originalClass;
            }, 2000);
        }
        
        // Optional: Show a toast or temporary message
        console.log('Link kopiert:', absoluteUrl);
        
    } catch (err) {
        console.error('Failed to copy link: ', err);
        alert('Fehler beim Kopieren des Links. Bitte versuchen Sie es erneut.');
    }
}

async function copyPublicFolderLink(fetch_url, linkElement) {
    try {
        const response = await fetch(fetch_url);
        if (!response.ok) {
            throw new Error('Failed to fetch public link');
        }
        const data = await response.json();
        if (data.error) {
            throw new Error(data.error);
        }
        const relativeUrl = data.link;
        // Build the absolute URL from the relative URL
        const absoluteUrl = window.location.origin + relativeUrl;
        
        // Modern browsers - use Clipboard API
        if (navigator.clipboard && window.isSecureContext) {
            await navigator.clipboard.writeText(absoluteUrl);
        } else {
            // Fallback for older browsers
            const textArea = document.createElement('textarea');
            textArea.value = absoluteUrl;
            textArea.style.position = 'fixed';
            textArea.style.left = '-999999px';
            textArea.style.top = '-999999px';
            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();
            document.execCommand('copy');
            textArea.remove();
        }
        
        // Find the dropdown button to show feedback
        const dropdownButton = linkElement.closest('.dropdown').querySelector('[data-bs-toggle="dropdown"]');
        if (dropdownButton) {
            const icon = dropdownButton.querySelector('i');
            const originalClass = icon.className;
            
            // Change icon to checkmark temporarily
            icon.className = 'bi bi-check';
            
            // Close the dropdown
            const dropdown = bootstrap.Dropdown.getInstance(dropdownButton);
            if (dropdown) {
                dropdown.hide();
            }
            
            // Reset icon after 2 seconds
            setTimeout(() => {
                icon.className = originalClass;
            }, 2000);
        }
        
        // Optional: Show a toast or temporary message
        console.log('Öffentlicher Link kopiert:', absoluteUrl);
        
    } catch (err) {
        console.error('Failed to copy public link: ', err);
        alert('Fehler beim Kopieren des öffentlichen Links. Bitte versuchen Sie es erneut.');
    }
}

function showImgLarge(img) {
    const modal = document.createElement('div');
    modal.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.9);z-index:9999;display:flex;align-items:center;justify-content:center;';
    modal.onclick = () => modal.remove();
    
    const largeImg = document.createElement('img');
    largeImg.src = img.src;
    largeImg.style.cssText = 'max-width:90%;max-height:90%;object-fit:contain;';
    modal.appendChild(largeImg);
    document.body.appendChild(modal);

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            modal.click();
        }
    });
}