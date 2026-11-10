document.addEventListener('DOMContentLoaded', function () {
    const all_forms = document.querySelectorAll('form');
    for (const form of all_forms) {
        if (form.getAttribute('without_spinner')) continue;
        form.addEventListener('submit', function (e) {
            if (e.defaultPrevented) return;
            // Use the button that actually submitted the form; fall back to the first one (e.g. Enter key / requestSubmit())
            const submitBtn = e.submitter || form.querySelector('button[type="submit"]');
            if (!submitBtn || submitBtn.tagName !== 'BUTTON' || submitBtn.querySelector('.spinner-border')) return;
            const spinner = document.createElement('span');
            spinner.className = 'spinner-border spinner-border-sm text-white';
            spinner.role = 'status';
            spinner.ariaHidden = 'true';
            submitBtn.innerHTML = spinner.outerHTML + submitBtn.innerHTML;
            submitBtn.classList.add('disabled');
        });
    }
});