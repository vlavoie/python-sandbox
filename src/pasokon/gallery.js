() => {
    // Single-click gallery thumbnail → auto-click the Expand/fullscreen button
    const attach = (gallery) => {
        if (gallery._pasokonFs) return;
        gallery._pasokonFs = true;
        gallery.addEventListener('click', (e) => {
            const thumb = e.target.closest('button');
            if (!thumb || !thumb.querySelector('img')) return;
            let tries = 0;
            const go = () => {
                const btn =
                    gallery.querySelector('[aria-label="Expand"]') ||
                    gallery.querySelector('[aria-label="expand"]') ||
                    gallery.querySelector('[title="Expand"]') ||
                    gallery.querySelector('[title="expand"]') ||
                    [...gallery.querySelectorAll('button')]
                        .find(b => b !== thumb && b.querySelector('svg') && !b.querySelector('img'));
                if (btn) { btn.click(); return; }
                if (tries++ < 10) setTimeout(go, 80);
            };
            setTimeout(go, 80);
        });
    };
    const observer = new MutationObserver(() => {
        document.querySelectorAll('.pasokon-gallery').forEach(attach);
    });
    observer.observe(document.body, { childList: true, subtree: true });
    document.querySelectorAll('.pasokon-gallery').forEach(attach);
}
