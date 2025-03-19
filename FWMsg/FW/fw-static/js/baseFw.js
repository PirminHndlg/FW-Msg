function onPlusClicked() {
    console.log('onPlusClicked');
    let action_view = document.getElementById('action_view');
    action_view.style.display = 'flex';

    let dark_bg = document.getElementById('dark_bg');
    dark_bg.style.display = 'block';
}

function onDarkBgClicked() {
    console.log('onDarkBgClicked');
    let action_view = document.getElementById('action_view');
    action_view.style.display = 'none';

    let dark_bg = document.getElementById('dark_bg');
    dark_bg.style.display = 'none';
}

