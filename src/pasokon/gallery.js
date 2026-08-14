() => {
    // ── Build lightbox DOM (once) ──────────────────────────────────────
    if (document.getElementById('pasokon-lightbox')) return;

    const overlay = document.createElement('div');
    overlay.id = 'pasokon-lightbox';

    const inner = document.createElement('div');
    inner.id = 'pasokon-lightbox-inner';

    const img = document.createElement('img');
    img.id = 'pasokon-lightbox-img';

    // SVG close icon — no font dependency
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

    // ── Wire up galleries (run now + whenever DOM changes) ────────────
    const attach = (gallery) => {
        if (gallery._pasokonLb) return;
        gallery._pasokonLb = true;
        gallery.addEventListener('click', (e) => {
            const thumb = e.target.closest('img');
            if (!thumb) return;
            e.preventDefault();
            e.stopImmediatePropagation();
            open(thumb.src);
        }, true);   // capture phase — fires before Gradio / browser handlers
    };

    const scan = () => document.querySelectorAll('.pasokon-gallery').forEach(attach);
    new MutationObserver(scan).observe(document.body, { childList: true, subtree: true });
    scan();
}
