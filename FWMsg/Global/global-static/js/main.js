document.addEventListener('DOMContentLoaded', function () {
    const all_forms = document.querySelectorAll('form');
    for (const form of all_forms) {
        if (form.getAttribute('without_spinner')) continue;
        form.addEventListener('submit', function () {
            const submitBtn = form.querySelector('button[type="submit"]');
            const spinner = document.createElement('span');
            spinner.className = 'spinner-border spinner-border-sm text-white';
            spinner.role = 'status';
            spinner.ariaHidden = 'true';
            submitBtn.innerHTML = spinner.outerHTML + submitBtn.innerHTML;
            submitBtn.classList.add('disabled');
        });
    }
});