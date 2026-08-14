() => {
    // ── Build lightbox DOM (once) ──────────────────────────────────────
    if (document.getElementById('pasokon-lightbox')) return;

    const overlay = document.createElement('div');
    overlay.id = 'pasokon-lightbox';

    const inner = document.createElement('div');
    inner.id = 'pasokon-lightbox-inner';

    const img = document.createElement('img');
    img.id = 'pasokon-lightbox-img';

    const closeBtn = document.createElement('button');
    closeBtn.id = 'pasokon-lightbox-close';
    closeBtn.title = 'Close (Esc)';
    closeBtn.innerHTML =
        '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">' +
        '<line x1="2" y1="2" x2="14" y2="14" stroke="white" stroke-width="2.5" stroke-linecap="round"/>' +
        '<line x1="14" y1="2" x2="2" y2="14" stroke="white" stroke-width="2.5" stroke-linecap="round"/>' +
        '</svg>';

    inner.appendChild(img);
    overlay.appendChild(inner);
    overlay.appendChild(closeBtn);
    document.body.appendChild(overlay);

    const open  = (src) => { img.src = src; overlay.classList.add('open'); };
    const close = ()    => { overlay.classList.remove('open'); img.src = ''; };

    closeBtn.addEventListener('click', close);
    overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') close(); });

    // ── Fix thumbnail container layout ────────────────────────────────
    // Walk from the first thumbnail img up to its grandparent (the grid container),
    // then override with flex so thumbnails pack left at natural size.
    const fixLayout = (gallery) => {
        const firstImg = gallery.querySelector('button img');
        if (!firstImg) return;
        const thumbBtn   = firstImg.closest('button');
        const thumbGrid  = thumbBtn?.parentElement;
        if (!thumbGrid || thumbGrid._pasokonFixed) return;
        thumbGrid._pasokonFixed = true;
        Object.assign(thumbGrid.style, {
            display: 'flex',
            flexWrap: 'wrap',
            justifyContent: 'flex-start',
            alignItems: 'flex-start',
            gap: '4px',
            overflowX: 'auto',
            overflowY: 'hidden',
        });
    };

    // ── Attach click → lightbox (capture phase) ───────────────────────
    const attach = (gallery) => {
        if (gallery._pasokonLb) return;
        gallery._pasokonLb = true;
        gallery.addEventListener('click', (e) => {
            const thumb = e.target.closest('img');
            if (!thumb) return;
            e.preventDefault();
            e.stopImmediatePropagation();
            open(thumb.src);
        }, true);
    };

    const scan = () => {
        document.querySelectorAll('.pasokon-gallery').forEach(g => {
            attach(g);
            fixLayout(g);
        });
    };

    new MutationObserver(scan).observe(document.body, { childList: true, subtree: true });
    scan();
}
