window.onload = function () {

    document.getElementById('form').addEventListener('submit', function (e) {
        if (confirmed) {
            let dialog = document.querySelector('dialog');
            dialog.remove();
            return
        }

        let buttons = document.querySelectorAll('div.tab-container button')
        if (buttons.length < 2) {
            return;
        }

        e.preventDefault()

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
            confirmed = true;
            document.getElementById('form').submit();
            dialog.remove()
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

    let bnts = document.querySelectorAll('div.tab-container button');

    bnts.forEach(function (btn) {
        let cookie_name = 'f' + btn.id + 'r' + einheit + 'u' + user
        let cookie = get_cookies(cookie_name);

        if (cookie) {
            let data = JSON.parse(cookie);
            let keys = Object.keys(data);

            for (let i = 0; i < keys.length; i++) {
                let key = keys[i];
                let value = data[key];
                let checkbox = document.getElementById('f' + btn.id + 'q' + key + 'v' + value);

                let parentDiv = checkbox.parentElement;
                let chosenCheckboxes = parentDiv.querySelectorAll('input[type="checkbox"]:checked');

                for (let j = 0; j < chosenCheckboxes.length; j++) {
                    chosenCheckboxes[j].checked = false;
                }

                checkbox.checked = true;
            }
        }
    })

    let cookies = get_cookies()
    let keys = Object.keys(cookies)

    for (let i = 0; i < keys.length; i++) {
        let key = keys[i]
        let cookie = cookies[key]
        if (cookie !== undefined && key.trim().startsWith('comment')) {
            let value = cookie
            let textareas = document.getElementsByName(key.trim())
            for (let j = 0; j < textareas.length; j++) {
                textareas[j].value = value
            }
        }
    }

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

    let cookie_name = 'f' + f[0] + 'r' + einheit + 'u' + user
    let cookie = get_cookies(cookie_name);
    // console.log(cookie)

    if (cookie) {
        let data = JSON.parse(cookie);
        if (data[q]) {
            delete data[q];
        } else {
            data[q] = checkbox.value;
        }
        save_cookies(cookie_name, JSON.stringify(data), 3);
    } else {
        let data = {};
        data[q] = checkbox.value;
        save_cookies(cookie_name, JSON.stringify(data), 3);
    }
    // console.log(get_cookies(cookie_name))

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
    let id = textarea.name;
    let value = textarea.value;
    console.log(id, value)

    save_cookies(id, value, 3);
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
    // console.log('form submitted')

    const formData = new FormData(document.getElementById('form'));

    fetch(refresh_url, {
        method: 'POST',
        body: formData
    })
        .then(response => response.json())
        .then(data => {
            // Handle the response
            console.log(data)
        })
        .catch(error => {
            // Handle errors
            console.log(error)
            console.log('error')
        });

    document.getElementById('form').action = post_url
}


function backButtonClicked() {
    let dialog = document.createElement('dialog');
    dialog.classList.add('dialog');

    dialog.innerHTML = 'Möchtest du wirklich zurück gehen? Die Antworten werden nach einem Refresh gespeichert.';
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