(() => {
    const forms = [...document.querySelectorAll('[data-dirty-form]')];
    let submitting = false;

    const formIsDirty = (form) => [...form.elements].some((field) => {
        if (!(field instanceof HTMLInputElement || field instanceof HTMLTextAreaElement || field instanceof HTMLSelectElement)) {
            return false;
        }
        if (field.type === 'file') return field.files.length > 0;
        if (field.type === 'checkbox' || field.type === 'radio') return field.checked !== field.defaultChecked;
        return field.value !== field.defaultValue;
    });

    forms.forEach((form) => {
        const saveButton = form.querySelector('[data-save-button]');
        const updateDirtyState = () => {
            const dirty = formIsDirty(form);
            if (saveButton) saveButton.disabled = !dirty;
            form.dataset.dirty = String(dirty);
        };

        form.addEventListener('input', updateDirtyState);
        form.addEventListener('change', updateDirtyState);
        form.addEventListener('submit', () => {
            submitting = true;
            if (saveButton) {
                saveButton.disabled = true;
                saveButton.dataset.originalText = saveButton.textContent.trim();
                saveButton.textContent = 'Saving…';
            }
        });

        form.querySelectorAll('input[type="file"]').forEach((input) => {
            input.addEventListener('change', () => {
                const file = input.files[0];
                const preview = document.querySelector(`[data-image-preview="${input.id}"]`);
                if (!file || !preview || !file.type.startsWith('image/')) return;
                const reader = new FileReader();
                reader.addEventListener('load', () => {
                    if (!(preview instanceof HTMLImageElement)) {
                        const image = document.createElement('img');
                        image.className = preview.className;
                        image.alt = input.id === 'id_profile_picture' ? 'New profile photo preview' : 'New profile cover preview';
                        image.dataset.imagePreview = input.id;
                        preview.replaceWith(image);
                        image.src = String(reader.result);
                    } else {
                        preview.src = String(reader.result);
                        preview.alt = input.id === 'id_profile_picture' ? 'New profile photo preview' : 'New profile cover preview';
                    }
                });
                reader.readAsDataURL(file);
            });
        });

        updateDirtyState();
    });

    document.querySelectorAll('.settings-form textarea[maxlength]').forEach((textarea) => {
        const counter = document.createElement('span');
        counter.className = 'settings-character-count';
        counter.setAttribute('aria-live', 'polite');
        textarea.insertAdjacentElement('afterend', counter);
        const updateCounter = () => {
            const length = textarea.value.length;
            const maximum = Number(textarea.maxLength);
            counter.textContent = `${length} / ${maximum}`;
            counter.classList.toggle('is-near-limit', length >= maximum * 0.9 && length < maximum);
            counter.classList.toggle('is-at-limit', length >= maximum);
        };
        textarea.addEventListener('input', updateCounter);
        updateCounter();
    });

    const passwordForm = document.querySelector('[data-password-form]');
    const newPassword = passwordForm?.querySelector('#id_new_password1');
    const strengthBar = document.querySelector('[data-password-strength-bar]');
    const strengthLabel = document.querySelector('[data-password-strength-label]');
    if (newPassword && strengthBar && strengthLabel) {
        const updatePasswordStrength = () => {
            const value = newPassword.value;
            const checks = {
                length: value.length >= 8,
                number: /\d/.test(value),
                uppercase: /[A-Z]/.test(value),
            };
            const score = Object.values(checks).filter(Boolean).length;
            strengthBar.style.width = `${(score / 3) * 100}%`;
            strengthBar.dataset.strength = String(score);
            strengthLabel.textContent = !value ? 'Enter a new password' : ['Needs work', 'Getting stronger', 'Good', 'Strong'][score];
            Object.entries(checks).forEach(([rule, passed]) => {
                document.querySelector(`[data-password-rule="${rule}"]`)?.classList.toggle('is-met', passed);
            });
        };
        newPassword.addEventListener('input', updatePasswordStrength);
        updatePasswordStrength();
    }

    window.addEventListener('beforeunload', (event) => {
        if (submitting || !forms.some((form) => formIsDirty(form))) return;
        event.preventDefault();
        event.returnValue = '';
    });
})();
