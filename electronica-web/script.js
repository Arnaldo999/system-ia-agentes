document.addEventListener('DOMContentLoaded', () => {
    // Reveal Animations on Scroll
    const revealElements = document.querySelectorAll('.reveal-text, .reveal-up, .reveal-left, .reveal-right, .reveal-scale');

    // Initial hero reveal
    setTimeout(() => {
        document.querySelectorAll('.hero .reveal-text, .hero .reveal-scale').forEach(el => {
            el.classList.add('reveal-active');
        });
    }, 100);

    const revealOnScroll = () => {
        const windowHeight = window.innerHeight;
        revealElements.forEach(el => {
            const elementTop = el.getBoundingClientRect().top;
            if (elementTop < windowHeight - 100) {
                el.classList.add('reveal-active');
            }
        });
    };

    window.addEventListener('scroll', revealOnScroll);
    revealOnScroll(); // Trigger on load

    // Smooth Cursor Tracking Effect
    const cursorX = document.querySelector('.cursor-blob');
    const cursorY = document.querySelector('.cursor-blob.b2');

    document.addEventListener('mousemove', (e) => {
        if (cursorX && cursorY) {
            cursorX.style.transform = `translate(${e.clientX - 200}px, ${e.clientY - 200}px)`;

            // Second blob follows slowly
            setTimeout(() => {
                cursorY.style.transform = `translate(${e.clientX - 150}px, ${e.clientY - 150}px)`;
            }, 100);
        }
    });
});
