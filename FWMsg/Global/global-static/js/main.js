document.addEventListener('DOMContentLoaded', function () {
    const all_forms = document.querySelectorAll('form');
    console.log(all_forms);
    for (const form of all_forms) {
        console.log(form);
        form.addEventListener('submit', function () {
            console.log('form submitted');
            const submitBtn = form.querySelector('button[type="submit"]');
            const spinner = document.createElement('span');
            spinner.className = 'spinner-border spinner-border-sm text-white';
            spinner.role = 'status';
            spinner.ariaHidden = 'true';
            submitBtn.innerHTML = spinner.outerHTML + submitBtn.innerHTML;
            submitBtn.setAttribute('disabled', 'disabled');
        });
    }
});