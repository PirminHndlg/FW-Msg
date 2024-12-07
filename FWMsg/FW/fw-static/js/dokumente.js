function addDokument(ordner_id) {
    console.log(ordner_id)
    let dialog = document.createElement('dialog');
    let form = document.createElement('form');
    form.id = 'form';
    form.method = 'post';
    form.enctype = 'multipart/form-data';
    form.action = '/dokumente/add/';
    form.style.display = 'flex';
    form.style.flexDirection = 'column';
    form.style.alignItems = 'center';

    form.innerHTML = document.getElementsByName('csrfmiddlewaretoken')[0].outerHTML;

    let ordner = document.createElement('input');
    ordner.type = 'hidden';
    ordner.name = 'ordner';
    ordner.value = ordner_id;

    let label = document.createElement('label');
    label.for = 'dokument';
    label.innerHTML = 'Dokument';

    let input_bschreibung = document.createElement('input');
    input_bschreibung.type = 'text';
    input_bschreibung.name = 'beschreibung';
    input_bschreibung.placeholder = 'Beschreibung';

    let input = document.createElement('input');
    input.type = 'file';
    input.name = 'dokument';
    input.id = 'dokument';

    let cancel = document.createElement('input');
    cancel.type = 'button';
    cancel.value = 'Cancel';
    cancel.onclick = function () {
        dialog.close();
        dialog.remove();
    }

    let submit = document.createElement('input');
    submit.type = 'submit';
    submit.value = 'Submit';

    form.appendChild(ordner);
    form.appendChild(label);
    form.appendChild(input_bschreibung)
    form.appendChild(input);
    form.appendChild(cancel);
    form.appendChild(submit);

    dialog.appendChild(form);

    document.body.appendChild(dialog);
    dialog.showModal();
}