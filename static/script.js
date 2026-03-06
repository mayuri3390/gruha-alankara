/* =======================================================
   Gruha Alankara — Global Script
   Drag-drop, nav toggle, utilities
   ======================================================= */

document.addEventListener('DOMContentLoaded', () => {

    // ── Mobile nav toggle ──
    const toggle = document.getElementById('navToggle');
    const links  = document.querySelector('.nav-links');
    if (toggle && links) {
        toggle.addEventListener('click', () => links.classList.toggle('open'));
        document.addEventListener('click', e => {
            if (!toggle.contains(e.target) && !links.contains(e.target)) {
                links.classList.remove('open');
            }
        });
    }

    // ── Drag-and-drop image upload (design page) ──
    const dropZone = document.getElementById('dropZone');
    const imgInput = document.getElementById('imageInput');
    const imgPrev  = document.getElementById('imagePreview');

    if (dropZone && imgInput) {
        dropZone.addEventListener('dragover',  e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
        dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
        dropZone.addEventListener('drop',      e => {
            e.preventDefault();
            dropZone.classList.remove('drag-over');
            const file = e.dataTransfer.files[0];
            if (file && file.type.startsWith('image/')) {
                showPreview(file);
                // Inject into the file input via DataTransfer
                const dt = new DataTransfer();
                dt.items.add(file);
                imgInput.files = dt.files;
            }
        });

        imgInput.addEventListener('change', () => {
            if (imgInput.files[0]) showPreview(imgInput.files[0]);
        });

        function showPreview(file) {
            const reader = new FileReader();
            reader.onload = e => {
                if (imgPrev) {
                    imgPrev.src = e.target.result;
                    imgPrev.style.display = 'block';
                }
            };
            reader.readAsDataURL(file);
        }
    }

    // ── Fade-in on scroll (feature cards, steps) ──
    const fadeEls = document.querySelectorAll('.feature-card, .step, .stat-item');
    if ('IntersectionObserver' in window && fadeEls.length) {
        const io = new IntersectionObserver((entries) => {
            entries.forEach((entry, i) => {
                if (entry.isIntersecting) {
                    entry.target.style.animation = `fade-up 0.5s ease ${i * 0.08}s both`;
                    io.unobserve(entry.target);
                }
            });
        }, { threshold: 0.12 });
        fadeEls.forEach(el => {
            el.style.opacity = '0';
            io.observe(el);
        });
    }

    // ── Active nav highlight via URL (redundant safety net) ──
    const path = window.location.pathname;
    document.querySelectorAll('.nav-link').forEach(link => {
        const href = link.getAttribute('href');
        if (href && path === href) link.classList.add('active');
    });
});
