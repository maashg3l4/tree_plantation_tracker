(() => {
    const accordionQuery = window.matchMedia('(max-width: 1023px)');
    const accordions = [...document.querySelectorAll('[data-footer-accordion]')];

    const syncAccordions = () => {
        accordions.forEach((item) => {
            item.open = !accordionQuery.matches;
        });
    };

    accordions.forEach((item) => {
        item.addEventListener('toggle', () => {
            if (!accordionQuery.matches || !item.open) return;
            accordions.forEach((other) => {
                if (other !== item) other.open = false;
            });
        });
    });
    syncAccordions();
    accordionQuery.addEventListener?.('change', syncAccordions);

    document.querySelector('[data-language-select]')?.addEventListener('change', (event) => {
        event.currentTarget.form.requestSubmit();
    });

    const statusLabel = document.querySelector('[data-system-status-label]');
    const statusDot = document.querySelector('[data-system-status-dot]');
    if (statusLabel && statusDot) {
        fetch(statusLabel.closest('a').href, {
            headers: { Accept: 'application/json' },
            credentials: 'same-origin',
        })
            .then(async (response) => {
                const result = await response.json();
                if (result.status === 'operational' && response.ok) {
                    statusLabel.textContent = 'All systems operational';
                    statusDot.classList.add('is-operational');
                    return;
                }
                if (result.status === 'degraded') {
                    statusLabel.textContent = 'Service degraded';
                    statusDot.classList.add('is-degraded');
                    return;
                }
                throw new Error(result.error || 'Status endpoint returned an error.');
            })
            .catch((error) => {
                statusLabel.textContent = 'Status unavailable';
                statusDot.classList.add('is-unavailable');
                console.warn('System status could not be loaded.', error);
            });
    }

    const form = document.querySelector('[data-newsletter-form]');
    const message = document.querySelector('[data-newsletter-message]');
    const unsubscribeLink = document.querySelector('[data-newsletter-unsubscribe]');
    form?.addEventListener('submit', async (event) => {
        event.preventDefault();
        if (!form.reportValidity()) return;
        const submit = form.querySelector('button[type="submit"]');
        submit.disabled = true;
        message.textContent = '';
        message.classList.remove('is-error', 'is-success');
        try {
            const response = await fetch(form.action, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': form.querySelector('[name="csrfmiddlewaretoken"]').value,
                    'X-Requested-With': 'XMLHttpRequest',
                    Accept: 'application/json',
                },
                body: new FormData(form),
                credentials: 'same-origin',
            });
            const result = await response.json();
            if (!response.ok || !result.success) {
                throw new Error(result.error || 'We could not add you to the list. Please try again.');
            }
            message.textContent = result.message;
            message.classList.add('is-success');
            if (unsubscribeLink && result.unsubscribe_url) {
                unsubscribeLink.href = result.unsubscribe_url;
                unsubscribeLink.hidden = false;
            }
            form.reset();
        } catch (error) {
            message.textContent = error.message || 'Something went wrong. Please try again.';
            message.classList.add('is-error');
        } finally {
            submit.disabled = false;
        }
    });
})();
