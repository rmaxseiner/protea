/**
 * Inventory Web UI - Application JavaScript
 * Minimal JS for mobile navigation, lightbox, and interactivity
 */

document.addEventListener('DOMContentLoaded', function() {
    // Mobile menu toggle
    const menuBtn = document.getElementById('mobile-menu-btn');
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');

    function openSidebar() {
        if (!sidebar || !overlay) return;
        sidebar.classList.add('open', 'translate-x-0');
        sidebar.classList.remove('-translate-x-full');
        overlay.classList.remove('hidden');
        overlay.classList.add('pointer-events-auto');
        document.body.style.overflow = 'hidden';
    }

    function closeSidebar() {
        if (!sidebar || !overlay) return;
        sidebar.classList.remove('open', 'translate-x-0');
        sidebar.classList.add('-translate-x-full');
        overlay.classList.add('hidden');
        overlay.classList.remove('pointer-events-auto');
        document.body.style.overflow = '';
    }

    if (menuBtn) {
        menuBtn.addEventListener('click', openSidebar);
        menuBtn.addEventListener('touchend', function(e) {
            e.preventDefault();
            openSidebar();
        });
    }

    if (overlay) {
        overlay.addEventListener('click', closeSidebar);
        overlay.addEventListener('touchend', function(e) {
            e.preventDefault();
            closeSidebar();
        });
    }

    // Close sidebar on escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && sidebar && sidebar.classList.contains('open')) {
            closeSidebar();
        }
    });

    // Make nav links work properly on mobile
    if (sidebar) {
        const navLinks = sidebar.querySelectorAll('nav a');
        navLinks.forEach(function(link) {
            // Handle touch events for better mobile responsiveness
            link.addEventListener('touchend', function(e) {
                // Close sidebar after a brief delay to allow navigation
                if (window.innerWidth < 1024 && sidebar.classList.contains('open')) {
                    setTimeout(closeSidebar, 50);
                }
                // Let the default navigation behavior happen
            });
            link.addEventListener('click', function(e) {
                // For non-touch devices, close sidebar on click
                if (window.innerWidth < 1024 && sidebar.classList.contains('open')) {
                    setTimeout(closeSidebar, 50);
                }
                // Let the default navigation behavior happen
            });
        });
    }

    // Auto-focus search input on page load
    const searchInput = document.getElementById('search-input');
    if (searchInput && window.location.pathname === '/') {
        searchInput.focus();
    }

    // Image lightbox functionality
    initLightbox();
});

// Lightbox for images
function initLightbox() {
    // Create lightbox elements if they don't exist
    if (!document.getElementById('lightbox')) {
        const lightbox = document.createElement('div');
        lightbox.id = 'lightbox';
        lightbox.className = 'fixed inset-0 z-[100] bg-black bg-opacity-95 hidden flex items-center justify-center';
        lightbox.innerHTML = `
            <button id="lightbox-close" class="absolute top-4 right-4 text-white p-2 z-[101]" aria-label="Close">
                <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                </svg>
            </button>
            <div id="lightbox-container" class="w-full h-full overflow-auto flex items-center justify-center p-4">
                <img id="lightbox-img" src="" alt="" class="max-w-none" style="touch-action: pinch-zoom pan-x pan-y;">
            </div>
        `;
        document.body.appendChild(lightbox);

        // Close button
        document.getElementById('lightbox-close').addEventListener('click', closeLightbox);

        // Click outside image to close
        document.getElementById('lightbox-container').addEventListener('click', function(e) {
            if (e.target === this) {
                closeLightbox();
            }
        });

        // Escape key to close
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && !document.getElementById('lightbox').classList.contains('hidden')) {
                closeLightbox();
            }
        });
    }

    // Add click handlers to all lightbox-enabled images
    document.querySelectorAll('[data-lightbox]').forEach(function(img) {
        img.style.cursor = 'zoom-in';
        img.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            openLightbox(this.dataset.lightbox || this.src);
        });
    });
}

function openLightbox(src) {
    const lightbox = document.getElementById('lightbox');
    const img = document.getElementById('lightbox-img');
    if (!lightbox || !img) return;

    img.src = src;
    lightbox.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
}

function closeLightbox() {
    const lightbox = document.getElementById('lightbox');
    if (!lightbox) return;

    lightbox.classList.add('hidden');
    document.body.style.overflow = '';
    document.getElementById('lightbox-img').src = '';
}

// htmx extensions
document.body.addEventListener('htmx:afterSwap', function(event) {
    // Scroll to top of results when search results update
    if (event.target.id === 'search-results') {
        event.target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    // Re-init lightbox for dynamically loaded content
    initLightbox();
});
