() => {
    if (document.getElementById('psk-lightbox')) return;

    // ── Build lightbox DOM ─────────────────────────────────────────────
    const overlay = document.createElement('div');
    overlay.id = 'psk-lightbox';

    const closeBtn = document.createElement('button');
    closeBtn.id = 'psk-lightbox-close';
    closeBtn.title = 'Close (Esc)';
    closeBtn.innerHTML =
        '<svg width="16" height="16" viewBox="0 0 16 16" fill="none">' +
        '<line x1="2" y1="2" x2="14" y2="14" stroke="white" stroke-width="2.5" stroke-linecap="round"/>' +
        '<line x1="14" y1="2" x2="2"  y2="14" stroke="white" stroke-width="2.5" stroke-linecap="round"/>' +
        '</svg>';

    const stage = document.createElement('div');
    stage.id = 'psk-lightbox-stage';

    const prevBtn = document.createElement('button');
    prevBtn.id = 'psk-lightbox-prev';
    prevBtn.title = 'Previous (<-)';
    prevBtn.innerHTML =
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none">' +
        '<polyline points="15 18 9 12 15 6" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>' +
        '</svg>';

    const mainImg = document.createElement('img');
    mainImg.id = 'psk-lightbox-img';

    const nextBtn = document.createElement('button');
    nextBtn.id = 'psk-lightbox-next';
    nextBtn.title = 'Next (->)';
    nextBtn.innerHTML =
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none">' +
        '<polyline points="9 18 15 12 9 6" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>' +
        '</svg>';

    const filmstrip = document.createElement('div');
    filmstrip.id = 'psk-lightbox-filmstrip';

    stage.appendChild(prevBtn);
    stage.appendChild(mainImg);
    stage.appendChild(nextBtn);
    overlay.appendChild(closeBtn);
    overlay.appendChild(stage);
    overlay.appendChild(filmstrip);
    document.body.appendChild(overlay);

    // ── State ──────────────────────────────────────────────────────────
    let images = [];   // array of src strings for the current gallery
    let idx    = 0;

    const show = (i) => {
        idx = (i + images.length) % images.length;
        mainImg.src = images[idx];

        // Update filmstrip highlights and scroll active into view
        [...filmstrip.children].forEach((t, j) => {
            t.classList.toggle('active', j === idx);
        });
        filmstrip.children[idx]?.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });

        // Hide arrows when only one image
        const single = images.length <= 1;
        prevBtn.classList.toggle('hidden', single);
        nextBtn.classList.toggle('hidden', single);
    };

    const open = (srcs, startIdx) => {
        images = srcs;

        // Rebuild filmstrip
        filmstrip.innerHTML = '';
        srcs.forEach((src, i) => {
            const t = document.createElement('img');
            t.src = src;
            t.addEventListener('click', (e) => { e.stopPropagation(); show(i); });
            filmstrip.appendChild(t);
        });

        overlay.classList.add('open');
        show(startIdx);
    };

    const close = () => {
        overlay.classList.remove('open');
        mainImg.src = '';
        filmstrip.innerHTML = '';
        images = [];
    };

    // ── Event wiring ───────────────────────────────────────────────────
    closeBtn.addEventListener('click', close);
    prevBtn.addEventListener('click', (e) => { e.stopPropagation(); show(idx - 1); });
    nextBtn.addEventListener('click', (e) => { e.stopPropagation(); show(idx + 1); });

    // Click backdrop (not stage contents) to close
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay || e.target === stage) close();
    });

    document.addEventListener('keydown', (e) => {
        if (!overlay.classList.contains('open')) return;
        if (e.key === 'Escape')     close();
        if (e.key === 'ArrowLeft')  show(idx - 1);
        if (e.key === 'ArrowRight') show(idx + 1);
    });

    // ── Review input: Shift+Enter inserts newline, Enter submits ──────────
    document.addEventListener('keydown', (e) => {
        if (e.key !== 'Enter') return;
        const textarea = e.target.closest('#review-input textarea');
        if (!textarea) return;
        if (!e.shiftKey) return; // plain Enter: let Gradio's submit handler fire
        // Shift+Enter: insert newline at cursor
        e.preventDefault();
        e.stopImmediatePropagation();
        const s = textarea.selectionStart, end = textarea.selectionEnd;
        textarea.value = textarea.value.slice(0, s) + '\n' + textarea.value.slice(end);
        textarea.selectionStart = textarea.selectionEnd = s + 1;
        textarea.dispatchEvent(new Event('input', { bubbles: true }));
    }, true);

    // ── Extract-prompt button → bridge textbox → Gradio handler ──────────
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.psk-extract-btn');
        if (!btn) return;
        e.preventDefault();
        e.stopImmediatePropagation();
        const prompt = btn.dataset.prompt;
        const panelId = btn.dataset.panel;
        const bridge = document.querySelector(`#psk-bridge-${panelId} textarea`);
        if (!bridge) return;
        bridge.value = prompt;
        bridge.dispatchEvent(new Event('input', { bubbles: true }));
    }, true);

    // ── Thumbnail click → lightbox ─────────────────────────────────────
    document.addEventListener('click', (e) => {
        if (!e.target.matches('.psk-thumb')) return;
        e.preventDefault();
        e.stopImmediatePropagation();

        const gallery = e.target.closest('.psk-gallery');
        const thumbs  = gallery ? [...gallery.querySelectorAll('.psk-thumb')] : [e.target];
        open(thumbs.map(t => t.src), thumbs.indexOf(e.target));
    }, true);
}
