window.onload = function () {
    filterFW('None', 'None');

    document.querySelectorAll('details').forEach((details) => {
        details.addEventListener('toggle', saveDetailsState);
    });
}

window.addEventListener('DOMContentLoaded', loadDetailsState);


let chosenFW = null;
let chosenStelle = null;

function onFWClicked(div) {
    if (chosenFW != null) {
        document.getElementById(chosenFW).style.backgroundColor = 'var(--gray-color)';
    }

    if (chosenFW === div.id) {
        chosenFW = null
        changeLandCursor('pointer');
        return;
    }

    changeLandCursor('copy');
    div.style.backgroundColor = 'lightblue';
    chosenFW = div.id;

    if (chosenStelle != null) {
        assign()
    }
}

function changeImgCursor(cursonname) {
    let imgs = document.querySelectorAll('.laender_container_img_div img');
    for (let i = 0; i < imgs.length; i++) {
        imgs[i].style.cursor = cursonname;
    }
}

function changeFwCursor(cursonname) {
    let divs = document.querySelectorAll('.freiwilliger_div');
    for (let i = 0; i < divs.length; i++) {
        divs[i].style.cursor = cursonname;
    }
}

function changeLandCursor(cursonname) {
    let divs = document.querySelectorAll('tr');
    for (let i = 0; i < divs.length; i++) {
        divs[i].style.cursor = cursonname;
    }
}


function onLandClicked(div) {
    if (chosenStelle != null) {
        document.getElementById(chosenStelle).style.backgroundColor = 'transparent';
    }

    if (chosenStelle === div.id) {
        chosenStelle = null
        changeImgCursor('not-allowed');
        changeFwCursor('pointer');
        filterFW('None', 'None');
        return;
    }

    let land = div.parentElement.parentElement.parentElement.id.split('l')[1];

    changeImgCursor('copy');
    changeFwCursor('copy');
    filterFW(land, div.id.split('s')[1]);

    div.style.backgroundColor = 'lightblue';
    chosenStelle = div.id;

    if (chosenFW != null) {
        assign()
    }
}

function filterFW(land, stelle) {
    let divs = document.querySelectorAll('.freiwilliger_div');
    let zugeteilt_div = document.getElementById('zugeteilt_div');
    let offen_div = document.getElementById('offen_div');
    let andere_div = document.getElementById('andere_div');
    let nicht_div = document.getElementById('nicht_div');

    if (land === 'None' && stelle === 'None') {
        for (let i = 0; i < divs.length; i++) {
            let zuteilung = divs[i].getAttribute('data-zuteilung');
            if (zuteilung !== 'None') {
                zugeteilt_div.appendChild(divs[i]);
            } else {
                offen_div.appendChild(divs[i]);
            }

            let ps = divs[i].querySelectorAll('p');
            for (let j = 0; j < ps.length; j++) {
                ps[j].style.color = 'black';
            }

        }
        return;
    }

    for (let j = 0; j < divs.length; j++) {
        divs[j].style.display = 'block';
        let zuteilung = divs[j].getAttribute('data-zuteilung');

        let ps = divs[j].querySelectorAll('p');

        let allocate = 1;

        if (zuteilung !== 'None') {
            allocate = 3;
        } else {

            for (let i = 0; i < ps.length; i++) {
                let p = ps[i];
                let land_fw = p.getAttribute('data-land');
                let stelle_fw = p.getAttribute('data-stelle');

                if (land === land_fw || stelle === stelle_fw) {
                    let name = divs[i].querySelector('h3').innerHTML;

                    if (p.getAttribute('data-nicht') === 'True') {
                        if (allocate === 1) {
                            allocate = 2;
                        }
                        p.style.color = 'var(--red-color)';
                    } else {
                        allocate = 0;
                        p.style.color = 'var(--green-color)';
                    }
                } else {
                    p.style.color = 'black';
                }
            }
        }

        if (allocate === 0) {
            // console.log(divs[j], 'offen_div')
            offen_div.appendChild(divs[j]);
        } else if (allocate === 1) {
            // console.log(divs[j], 'andere_div')
            andere_div.appendChild(divs[j]);
        } else if (allocate === 2) {
            // console.log(divs[j], 'nicht_div')
            nicht_div.appendChild(divs[j]);
        } else {
            // console.log(divs[j], 'zugeteilt_div')
            zugeteilt_div.appendChild(divs[j]);
        }
    }
}

function removeAssignment(event, div) {
    event.stopPropagation()
    let fw = div.id.split('img')[1];
    // console.log(fw, chosenStelle)
    if (chosenStelle != null) {
        chosenFW = 'f' + fw;
        assign()
        return
    }
    window.location = zuteilung_url + '?fw=' + fw + '&land=None';
}

function assign() {
    if (chosenFW != null && chosenStelle != null) {
        let fw = chosenFW.split('f')[1];
        let land = chosenStelle.split('s')[1];
        window.location = zuteilung_url + '?fw=' + fw + '&land=' + land;
    }
}


function saveDetailsState() {
    document.querySelectorAll('details').forEach((details) => {
        // console.log(details.id, details.open);
        localStorage.setItem(details.id, details.open);
    });
}

function loadDetailsState() {
    document.querySelectorAll('details').forEach((details) => {
        if (localStorage.getItem(details.id) === null) {
            localStorage.setItem(details.id, 'true');
        }
        details.open = localStorage.getItem(details.id) === 'true';
    });
}