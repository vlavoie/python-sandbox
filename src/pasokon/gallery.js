() => {
    if (document.getElementById('psk-lightbox')) return;

    // ── Build lightbox DOM ─────────────────────────────────────────────
    const overlay  = document.createElement('div');
    overlay.id = 'psk-lightbox';

    const inner = document.createElement('div');
    inner.id = 'psk-lightbox-inner';

    const img = document.createElement('img');
    img.id = 'psk-lightbox-img';

    const closeBtn = document.createElement('button');
    closeBtn.id = 'psk-lightbox-close';
    closeBtn.title = 'Close (Esc)';
    closeBtn.innerHTML =
        '<svg width="16" height="16" viewBox="0 0 16 16" fill="none">' +
        '<line x1="2" y1="2" x2="14" y2="14" stroke="white" stroke-width="2.5" stroke-linecap="round"/>' +
        '<line x1="14" y1="2" x2="2"  y2="14" stroke="white" stroke-width="2.5" stroke-linecap="round"/>' +
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

    // ── Single listener for all .psk-thumb clicks, current and future ──
    document.addEventListener('click', (e) => {
        if (e.target.matches('.psk-thumb')) {
            e.preventDefault();
            e.stopImmediatePropagation();
            open(e.target.src);
        }
    }, true);
}
