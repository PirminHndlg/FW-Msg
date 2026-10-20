window.onload = function () {

    document.getElementById('form').addEventListener('submit', function (e) {
        // Gesendet werden die lokal gespeicherten Eingaben (seminar_store.js)
        e.preventDefault()

        let buttons = document.querySelectorAll('div.tab-container button')
        if (buttons.length < 2) {
            submit_all();
            return;
        }

        let dialog = document.createElement('dialog');
        dialog.classList.add('dialog');

        let btn = document.getElementById(chosen);
        let freiwillier_name = btn.innerHTML;

        dialog.innerHTML = `Möchtest du alle Antworten oder nur von ${freiwillier_name} abschicken?`;
        dialog.innerHTML += '<br>';
        let div = document.createElement('div');
        div.classList.add('center_div');
        div.innerHTML += '<button id="no" class="dialog_button_cancel">Abbrechen</button>';
        div.innerHTML += '<button id="all" class="dialog_button">Alle</button>';
        div.innerHTML += `<button id="one" class="dialog_button">Nur ${freiwillier_name}</button>`;
        dialog.appendChild(div);
        document.body.appendChild(dialog);
        dialog.showModal();

        document.getElementById('all').addEventListener('click', function () {
            dialog.close();
            dialog.remove();
            submit_all();
        });

        document.getElementById('one').addEventListener('click', function () {
            dialog.close();

            let input = document.createElement('input');
            input.type = 'hidden';
            input.name = 'only';
            input.value = chosen;
            document.getElementById('question_div_' + chosen).appendChild(input);

            on_form_submit()

            confirmed = false;
            e.preventDefault()

            input.remove()
            document.getElementById('question_div_' + chosen).remove()
            document.getElementById(chosen).remove()

            let buttons = document.querySelectorAll('div.tab-container button')
            if (buttons.length > 0) {
                buttons[0].click()
            }

            dialog.remove();
        });

        document.getElementById('no').addEventListener('click', function () {
            dialog.close();
            confirmed = false;
            e.preventDefault();
            dialog.remove();
        });

    });


    window.addEventListener('pageshow', function (event) {
        if (event.persisted) {
            // This means the page was loaded from the back/forward cache
            confirmed = false;
            // console.log("Page loaded through back/forward history navigation");
        }
    });

    // Noch nicht gesendete Einträge (localStorage, früher Cookies) über die Serverwerte legen
    SeminarStore.start();
    restore_pending_entries();
    SeminarStore.onChange(update_sync_status);

    /*
let divs = document.querySelectorAll('div.question_checkbox_div');
divs.forEach((div) => {
    let checkboxes = div.querySelectorAll('input[type="checkbox"]');
    let name = checkboxes[0].id.split('v')[0];

    let cookie = get_cookies(name);
    if (cookie) {

        checkboxes.forEach((checkbox) => {
            if (checkbox.value === cookie) {
                checkbox.checked = true;
            }
        })
    }
});*/
}

function restore_pending_entries() {
    let entries = SeminarStore.pending();
    let this_einheit = new RegExp('r' + einheit + 'u' + user + '(c\\d+)?(n\\d)?$');

    Object.keys(entries).forEach(function (name) {
        if (!this_einheit.test(name)) {
            return;
        }

        if (name.startsWith('comment')) {
            // id ist der Name ohne n0/n1 (Namen bei Präsentation anzeigen)
            let textarea = document.getElementById(name.slice(0, -2));
            if (textarea) {
                textarea.value = entries[name];
                textarea.name = name;
                let nameCheckbox = textarea.parentElement.querySelector('label input[type="checkbox"]');
                if (nameCheckbox) {
                    nameCheckbox.checked = name.endsWith('n1');
                }
            }
            return;
        }

        let fid = name.slice(1).split('r')[0];
        let data;
        try {
            data = JSON.parse(entries[name]) || {};
        } catch (e) {
            return;
        }
        Object.keys(data).forEach(function (q) {
            let checkbox = document.getElementById('f' + fid + 'q' + q + 'v' + data[q]);
            if (!checkbox) {
                return;
            }
            checkbox.parentElement.querySelectorAll('input[type="checkbox"]:checked').forEach(function (cb) {
                cb.checked = false;
            });
            checkbox.checked = true;
        });
    });
}

function submit_all() {
    let button = document.querySelector('#form button[type="submit"]');
    button.disabled = true;

    SeminarStore.sync({manual: true})
        .then(function () {
            window.location.href = seminar_home_url;
        })
        .catch(function () {
            button.disabled = false;
            show_offline_dialog();
        });
}

function show_offline_dialog() {
    let dialog = document.createElement('dialog');
    dialog.classList.add('dialog');
    dialog.innerHTML = 'Keine Verbindung zum Server. Deine Eingaben bleiben auf diesem Gerät gespeichert. '
        + 'Versuche es später erneut mit „Abschicken“ oder „Refresh“ auf der Startseite.';
    dialog.innerHTML += '<br>';
    let div = document.createElement('div');
    div.classList.add('center_div');
    div.innerHTML += '<button id="ok" class="dialog_button">OK</button>';
    dialog.appendChild(div);
    document.body.appendChild(dialog);
    dialog.showModal();

    document.getElementById('ok').addEventListener('click', function () {
        dialog.close();
        dialog.remove();
    });
}

function update_sync_status(count) {
    let status = document.getElementById('sync_status');
    if (!status) {
        return;
    }
    if (count > 0) {
        status.textContent = count + (count === 1 ? ' Eintrag ist' : ' Einträge sind')
            + ' noch nicht abgeschickt und auf diesem Gerät gespeichert.';
        status.className = 'sync_status sync_status_pending';
    } else {
        status.textContent = 'Alle Eingaben sind gespeichert.';
        status.className = 'sync_status sync_status_saved';
    }
}

function download(filename, text) {
    var element = document.createElement('a');
    element.setAttribute('href', 'data:text/plain;charset=utf-8,' + encodeURIComponent(text));
    element.setAttribute('download', filename);

    element.style.display = 'none';
    document.body.appendChild(element);

    element.click();

    document.body.removeChild(element);
}

function groupData() {
    let checked_checkboxes = document.querySelectorAll('input[type="checkbox"]:checked');
    let data = {};

    checked_checkboxes.forEach((checkbox) => {
        let question = checkbox.name;
        let value = checkbox.value;
        data[question] = value;
    })

    return data
}

function download_all_ansewers() {
    let data = groupData();

    download('answers.json', JSON.stringify(data));
}


function on_checkbox_change(checkbox) {
    //remove_cookies(checkbox.name);
    /*if (checkbox.checked) {
        save_cookies(checkbox.name, checkbox.value, 3);
    } else {
        console.log('this remove cookie')
        remove_cookies(checkbox.name);
    }*/

    // console.log(checkbox.id)
    let id = checkbox.id;
    let f = id.split('f')[1].split('q');
    let q = id.split('q')[1].split('v')[0];

    let name = 'f' + f[0] + 'r' + einheit + 'u' + user
    let data = {};
    try {
        data = JSON.parse(SeminarStore.get(name)) || {};
    } catch (e) {
        data = {};
    }

    if (checkbox.checked) {
        data[q] = checkbox.value;
    } else if (data[q] === checkbox.value) {
        delete data[q];
    }

    if (Object.keys(data).length) {
        SeminarStore.set(name, JSON.stringify(data));
    } else {
        SeminarStore.remove(name);
    }

}

function deselect_other_checkboxes(checkbox) {
    let div = checkbox.parentElement;
    let checkboxes = div.querySelectorAll('input[type="checkbox"]');
    checkboxes.forEach(function (cb) {
        if (cb !== checkbox) {
            cb.checked = false;
        }
    });

    on_checkbox_change(checkbox)
}

function onTextChange(textarea) {
    let name = textarea.name;
    // Nur eine Variante (n0/n1) desselben Kommentars behalten
    let other = name.slice(0, -1) + (name.endsWith('1') ? '0' : '1');
    if (SeminarStore.get(other) !== null) {
        SeminarStore.remove(other);
    }
    SeminarStore.set(name, textarea.value);
}

function onCommentNameChange(checkbox) {
    let textarea = checkbox.parentElement.parentElement.querySelector('textarea');
    textarea.name = textarea.name.slice(0, -1) + (checkbox.checked ? '1' : '0');
    if (textarea.value || SeminarStore.get(textarea.name.slice(0, -1) + (checkbox.checked ? '0' : '1')) !== null) {
        onTextChange(textarea);
    }
}

function onButtonClick(id) {
    // console.log('button clicked');
    // console.log(id)
    let freiwilliger_id = id;
    chosen = freiwilliger_id;
    let divs = document.querySelectorAll('div.questions_div');
    divs.forEach(function (div) {
        div.style.display = 'none';
    });
    document.getElementById('question_div_' + freiwilliger_id).style.display = 'block';

    let btn = document.getElementById(id);
    // console.log(btn);
    btn.style.backgroundColor = 'lightblue';

    let tab_container = document.querySelector('.tab-container');
    let btns = tab_container.querySelectorAll('button');

    btns.forEach(function (b) {
        if (b !== btn) {
            b.style.backgroundColor = 'white';
        }
    });

    let img = document.getElementById('img' + id);
    img.style.display = 'block';

    let imgs = document.querySelectorAll('img');
    imgs.forEach(function (i) {
        if (i.id === "delete") {
            return;
        }
        if (i !== img) {
            i.style.display = 'none';
        }
    });
}

function background_clicked() {
    // console.log('background clicked');
    let img = document.querySelector('.profil_img_clicked');
    img.classList.remove('profil_img_clicked');
    img.classList.add('profil_img');
    document.getElementById('dark_background').style.display = 'none';

    let btns = document.querySelectorAll('div.tab-container button');
    btns.forEach(function (btn) {
        btn.disabled = false;
    });
}

function on_img_click(img) {
    // console.log('img clicked');
    // console.log(img.classList)
    if (!img.classList.contains('profil_img_clicked')) {
        img.classList.remove('profil_img');
        img.classList.add('profil_img_clicked');
        document.getElementById('dark_background').style.display = 'block';

        let btns = document.querySelectorAll('div.tab-container button');
        btns.forEach(function (btn) {
            btn.disabled = true;
        });
    } else {
        background_clicked()
    }
}


function on_form_submit() {
    // Bei einem Fehler bleiben die Einträge gespeichert und können später abgeschickt werden
    SeminarStore.sync().catch(show_offline_dialog);

    document.getElementById('form').action = post_url
}


function backButtonClicked() {
    let dialog = document.createElement('dialog');
    dialog.classList.add('dialog');

    dialog.innerHTML = 'Möchtest du wirklich zurück gehen? Nicht abgeschickte Eingaben bleiben auf diesem Gerät gespeichert und können später mit Refresh gesendet werden.';
    dialog.innerHTML += '<br>';
    let div = document.createElement('div');
    div.classList.add('center_div');
    div.innerHTML += '<button id="no" class="dialog_button_cancel">Abbrechen</button>';
    div.innerHTML += '<button id="yes" class="dialog_button">Ja</button>';
    dialog.appendChild(div);

    document.body.appendChild(dialog);

    dialog.showModal();

    document.getElementById('yes').addEventListener('click', function () {
        dialog.close();
        window.location.href = seminar_home_url;
        dialog.remove()
    })

    document.getElementById('no').addEventListener('click', function () {
        dialog.close();
        dialog.remove()
    })
}

function deleteButtonClicked() {
    let dialog = document.createElement('dialog');
    dialog.classList.add('dialog');


    let name = document.getElementById(chosen).innerHTML;

    dialog.innerHTML = `Möchtest du wirklich die Einträge von ${name} löschen?<br><br>Bereits abgeschickte Antworten werden nicht gelöscht.`;
    dialog.innerHTML += '<br>';
    let div = document.createElement('div');
    div.classList.add('center_div');
    div.innerHTML += '<button id="no" class="dialog_button_cancel">Abbrechen</button>';
    div.innerHTML += '<button id="yes" class="dialog_button">Ja</button>';
    dialog.appendChild(div);

    document.body.appendChild(dialog);

    dialog.showModal();

    document.getElementById('yes').addEventListener('click', function () {
        dialog.close();
        dialog.remove();

        let div = document.getElementById('question_div_' + chosen);
        let checkboxes = div.querySelectorAll('input[type="checkbox"].own_checkbox:checked');
        let textareas = div.querySelectorAll('textarea');

        checkboxes.forEach((checkbox) => {
            if (checkbox.style.display === 'none') {
                return;
            }
            checkbox.checked = false;
            deselect_other_checkboxes(checkbox);
        })

        textareas.forEach((textarea) => {
            textarea.value = '';
            onTextChange(textarea);
        })
    })

    document.getElementById('no').addEventListener('click', function () {
        dialog.close();
        dialog.remove()
    })
}