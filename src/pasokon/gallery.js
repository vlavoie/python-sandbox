() => {
    // ── Build lightbox DOM (once) ──────────────────────────────────────
    if (document.getElementById('pasokon-lightbox')) return;

    const overlay = document.createElement('div');
    overlay.id = 'pasokon-lightbox';
    overlay.innerHTML =
        '<div id="pasokon-lightbox-inner">' +
        '  <img id="pasokon-lightbox-img" />' +
        '</div>' +
        '<button id="pasokon-lightbox-close" title="Close (Esc)">✕</button>';
    document.body.appendChild(overlay);

    const img    = document.getElementById('pasokon-lightbox-img');
    const close  = () => { overlay.classList.remove('open'); img.src = ''; };
    const open   = (src) => { img.src = src; overlay.classList.add('open'); };

    document.getElementById('pasokon-lightbox-close').addEventListener('click', close);
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
