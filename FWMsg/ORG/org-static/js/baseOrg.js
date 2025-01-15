function toggleDescription(link) {
    const parent = link.parentElement;
    const preview = parent.querySelector('.description-preview');
    const full = parent.querySelector('.description-full');
    const isExpanded = preview.style.display === 'none';
    
    preview.style.display = isExpanded ? 'inline' : 'none';
    full.style.display = isExpanded ? 'none' : 'inline';
    link.textContent = isExpanded ? 'mehr' : 'weniger';
}