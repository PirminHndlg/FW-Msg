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

function showImgLarge(img) {
    let img_data = img.src
    let img_large_div = document.createElement('div');
    let img_large = document.createElement('img');
    img_large.src = img_data;
    img_large.style.width = 'auto';
    img_large.style.height = 'auto';
    img_large.style.maxWidth = '90%';
    img_large.style.maxHeight = '90%';
    img_large.style.objectFit = 'contain';

    img_large_div.appendChild(img_large);

    img_large_div.style.display = 'flex';
    img_large_div.style.justifyContent = 'center';
    img_large_div.style.alignItems = 'center';
    img_large_div.style.width = '100%';
    img_large_div.style.height = '100%';
    img_large_div.style.position = 'fixed';
    img_large_div.style.top = '0';
    img_large_div.style.left = '0';
    img_large_div.style.zIndex = '100';
    img_large_div.style.backgroundColor = 'rgba(0, 0, 0, 0.5)';
    img_large_div.style.cursor = 'pointer';
    img_large_div.onclick = function () {
        img_large_div.remove();
    }
    document.body.appendChild(img_large_div);
}

function toggleDescription(link) {
    const parent = link.parentElement;
    const preview = parent.querySelector('.description-preview');
    const full = parent.querySelector('.description-full');
    const isExpanded = preview.style.display === 'none';
    
    preview.style.display = isExpanded ? 'inline' : 'none';
    full.style.display = isExpanded ? 'none' : 'inline';
    link.textContent = isExpanded ? 'mehr' : 'weniger';
}