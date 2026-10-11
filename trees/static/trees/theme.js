(() => {
    const root = document.documentElement;
    const toggle = document.getElementById('canopy-theme-toggle');
    const popover = document.getElementById('canopy-theme-popover');
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    let pressTimer = null;
    let longPressTriggered = false;

    const getPreference = () => {
        try {
            return localStorage.getItem('theme');
        } catch (error) {
            console.warn('Theme preference could not be read.', error);
            return null;
        }
    };

    const setPreference = (preference) => {
        try {
            localStorage.setItem('theme', preference);
        } catch (error) {
            console.warn('Theme preference could not be saved.', error);
        }
        applyTheme(preference, true);
    };

    function applyTheme(preference = getPreference(), animate = false) {
        const dark = preference === 'dark' || ((preference === 'system' || !preference) && media.matches);
        if (animate) {
            root.classList.add('canopy-theme-transition');
            window.setTimeout(() => root.classList.remove('canopy-theme-transition'), 320);
        }
        root.classList.toggle('dark', dark);
        if (toggle) {
            toggle.setAttribute('aria-pressed', String(dark));
            toggle.setAttribute('aria-label', dark ? 'Switch to light mode' : 'Switch to dark mode');
        }
        document.querySelectorAll('[data-theme-choice]').forEach((button) => {
            button.setAttribute('aria-pressed', String(button.dataset.themeChoice === (preference || 'system')));
        });
    }

    const closePopover = () => {
        if (!popover) return;
        popover.hidden = true;
        toggle?.setAttribute('aria-expanded', 'false');
    };

    const openPopover = () => {
        if (!popover) return;
        popover.hidden = false;
        toggle?.setAttribute('aria-expanded', 'true');
    };

    toggle?.addEventListener('pointerdown', (event) => {
        if (event.button !== undefined && event.button !== 0) return;
        longPressTriggered = false;
        window.clearTimeout(pressTimer);
        pressTimer = window.setTimeout(() => {
            longPressTriggered = true;
            openPopover();
        }, 700);
    });

    ['pointerup', 'pointercancel', 'pointerleave'].forEach((eventName) => {
        toggle?.addEventListener(eventName, () => window.clearTimeout(pressTimer));
    });

    toggle?.addEventListener('click', () => {
        if (longPressTriggered) {
            longPressTriggered = false;
            return;
        }
        const next = root.classList.contains('dark') ? 'light' : 'dark';
        setPreference(next);
    });

    document.querySelectorAll('[data-theme-choice]').forEach((button) => {
        button.addEventListener('click', () => {
            setPreference(button.dataset.themeChoice);
            closePopover();
        });
    });

    document.addEventListener('click', (event) => {
        if (!event.target.closest('.canopy-theme-fab-wrap')) closePopover();
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') closePopover();
    });

    media.addEventListener?.('change', () => {
        if (!getPreference() || getPreference() === 'system') applyTheme('system');
    });

    applyTheme();
})();
