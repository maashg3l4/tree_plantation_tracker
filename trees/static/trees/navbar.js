(() => {
    const closeMenus = (except = null) => {
        document.querySelectorAll('[data-menu-trigger][aria-expanded="true"]').forEach((trigger) => {
            if (trigger === except) return;
            trigger.setAttribute('aria-expanded', 'false');
            const menu = document.getElementById(trigger.getAttribute('aria-controls'));
            if (menu) menu.hidden = true;
        });
    };

    document.querySelectorAll('[data-menu-trigger]').forEach((trigger) => {
        trigger.addEventListener('click', (event) => {
            event.stopPropagation();
            const menu = document.getElementById(trigger.getAttribute('aria-controls'));
            if (!menu) return;
            const opening = trigger.getAttribute('aria-expanded') !== 'true';
            closeMenus(trigger);
            trigger.setAttribute('aria-expanded', String(opening));
            menu.hidden = !opening;
        });
    });

    document.addEventListener('click', (event) => {
        if (!event.target.closest('.canopy-menu')) closeMenus();
    });

    const drawerBackdrop = document.querySelector('[data-drawer-backdrop]');
    const drawerPanel = document.querySelector('[data-drawer-panel]');
    const drawerOpenButton = document.querySelector('[data-drawer-open]');
    const drawerCloseButton = document.querySelector('[data-drawer-close]');
    let drawerReturnFocus = null;
    let drawerPointerStart = null;

    const closeDrawer = () => {
        if (!drawerBackdrop || drawerBackdrop.hidden) return;
        drawerBackdrop.hidden = true;
        document.body.classList.remove('canopy-overlay-open');
        drawerOpenButton?.setAttribute('aria-expanded', 'false');
        drawerReturnFocus?.focus();
    };

    const openDrawer = () => {
        if (!drawerBackdrop) return;
        closeMenus();
        drawerReturnFocus = document.activeElement;
        drawerBackdrop.hidden = false;
        document.body.classList.add('canopy-overlay-open');
        drawerOpenButton?.setAttribute('aria-expanded', 'true');
        drawerPanel?.focus();
    };

    drawerOpenButton?.addEventListener('click', openDrawer);
    drawerCloseButton?.addEventListener('click', closeDrawer);
    drawerBackdrop?.addEventListener('click', (event) => {
        if (event.target === drawerBackdrop) closeDrawer();
    });
    drawerPanel?.addEventListener('pointerdown', (event) => {
        drawerPointerStart = { x: event.clientX, y: event.clientY };
    });
    drawerPanel?.addEventListener('pointerup', (event) => {
        if (!drawerPointerStart) return;
        const deltaX = event.clientX - drawerPointerStart.x;
        const deltaY = Math.abs(event.clientY - drawerPointerStart.y);
        if (deltaX > 75 && deltaY < 60) closeDrawer();
        drawerPointerStart = null;
    });

    const searchBackdrop = document.querySelector('[data-search-backdrop]');
    const searchInput = document.getElementById('canopy-search-input');
    const searchClose = document.querySelector('[data-search-close]');
    const searchOpenButtons = document.querySelectorAll('[data-search-open]');
    let searchReturnFocus = null;

    const closeSearch = () => {
        if (!searchBackdrop || searchBackdrop.hidden) return;
        searchBackdrop.hidden = true;
        document.body.classList.remove('canopy-overlay-open');
        searchReturnFocus?.focus();
    };

    const openSearch = () => {
        if (!searchBackdrop) return;
        closeMenus();
        searchReturnFocus = document.activeElement;
        searchBackdrop.hidden = false;
        document.body.classList.add('canopy-overlay-open');
        window.setTimeout(() => searchInput?.focus(), 0);
    };

    searchOpenButtons.forEach((button) => button.addEventListener('click', openSearch));
    searchClose?.addEventListener('click', closeSearch);
    searchBackdrop?.addEventListener('click', (event) => {
        if (event.target === searchBackdrop) closeSearch();
    });

    const postBackdrop = document.querySelector('[data-post-backdrop]');
    const postOpenButton = document.querySelector('[data-post-open]');
    const postCloseButtons = document.querySelectorAll('[data-post-close]');
    let postReturnFocus = null;

    const closePostSheet = () => {
        if (!postBackdrop || postBackdrop.hidden) return;
        postBackdrop.hidden = true;
        document.body.classList.remove('canopy-overlay-open');
        postReturnFocus?.focus();
    };

    const openPostSheet = () => {
        if (!postBackdrop) return;
        postReturnFocus = document.activeElement;
        postBackdrop.hidden = false;
        document.body.classList.add('canopy-overlay-open');
        postBackdrop.querySelector('a')?.focus();
    };

    postOpenButton?.addEventListener('click', openPostSheet);
    postCloseButtons.forEach((button) => button.addEventListener('click', closePostSheet));
    postBackdrop?.addEventListener('click', (event) => {
        if (event.target === postBackdrop) closePostSheet();
    });

    document.addEventListener('keydown', (event) => {
        if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
            event.preventDefault();
            openSearch();
            return;
        }

        if (event.key === 'Escape') {
            closeMenus();
            closeDrawer();
            closeSearch();
            closePostSheet();
        }

        const activeDialog = [drawerBackdrop, searchBackdrop, postBackdrop]
            .find((backdrop) => backdrop && !backdrop.hidden);
        if (event.key !== 'Tab' || !activeDialog) return;
        const focusable = [...activeDialog.querySelectorAll(
            'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])',
        )].filter((element) => element.offsetParent !== null);
        if (!focusable.length) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
        }
    });
})();
