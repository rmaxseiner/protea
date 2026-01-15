/**
 * Inventory Web UI - Application JavaScript
 * Minimal JS for mobile navigation, lightbox, and interactivity
 */

document.addEventListener('DOMContentLoaded', function() {
    console.log('[Inventory] DOMContentLoaded fired');

    // Mobile menu toggle
    const menuBtn = document.getElementById('mobile-menu-btn');
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');

    console.log('[Inventory] Elements found:', {
        menuBtn: !!menuBtn,
        sidebar: !!sidebar,
        overlay: !!overlay
    });

    function openSidebar() {
        console.log('[Inventory] openSidebar called');
        if (!sidebar || !overlay) {
            console.log('[Inventory] Missing elements, aborting');
            return;
        }
        console.log('[Inventory] Sidebar classes before:', sidebar.className);
        sidebar.classList.add('open', 'translate-x-0');
        sidebar.classList.remove('-translate-x-full');
        overlay.classList.remove('hidden');
        overlay.classList.add('pointer-events-auto');
        document.body.style.overflow = 'hidden';
        console.log('[Inventory] Sidebar classes after:', sidebar.className);
    }

    function closeSidebar() {
        console.log('[Inventory] closeSidebar called');
        if (!sidebar || !overlay) return;
        sidebar.classList.remove('open', 'translate-x-0');
        sidebar.classList.add('-translate-x-full');
        overlay.classList.add('hidden');
        overlay.classList.remove('pointer-events-auto');
        document.body.style.overflow = '';
    }

    if (menuBtn) {
        console.log('[Inventory] Adding event listeners to menuBtn');
        menuBtn.addEventListener('click', function(e) {
            console.log('[Inventory] menuBtn click event fired');
            openSidebar();
        });
        menuBtn.addEventListener('touchend', function(e) {
            console.log('[Inventory] menuBtn touchend event fired');
            e.preventDefault();
            openSidebar();
        });
    } else {
        console.log('[Inventory] menuBtn not found!');
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

    // Nav links - just close sidebar, let browser handle navigation naturally
    if (sidebar) {
        var navLinks = sidebar.querySelectorAll('nav a');
        for (var i = 0; i < navLinks.length; i++) {
            (function(link) {
                link.addEventListener('click', function() {
                    // Close sidebar on mobile, navigation happens automatically
                    if (window.innerWidth < 1024) {
                        closeSidebar();
                    }
                });
            })(navLinks[i]);
        }
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
    console.log('[Inventory] initLightbox called');
    // Create lightbox elements if they don't exist
    if (!document.getElementById('lightbox')) {
        console.log('[Inventory] Creating lightbox element');
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

        // Close button - handle both click and touch
        var closeBtn = document.getElementById('lightbox-close');
        closeBtn.addEventListener('click', closeLightbox);
        closeBtn.addEventListener('touchend', function(e) {
            e.preventDefault();
            closeLightbox();
        });

        // Click/touch outside image to close
        var container = document.getElementById('lightbox-container');
        container.addEventListener('click', function(e) {
            if (e.target === this) {
                closeLightbox();
            }
        });
        container.addEventListener('touchend', function(e) {
            if (e.target === this) {
                e.preventDefault();
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

    // Add click/touch handlers to all lightbox-enabled images
    var lightboxImages = document.querySelectorAll('[data-lightbox]');
    console.log('[Inventory] Found ' + lightboxImages.length + ' lightbox images');

    lightboxImages.forEach(function(img) {
        img.style.cursor = 'zoom-in';

        function handleImageTap(e) {
            console.log('[Inventory] Image tap/click detected', img.dataset.lightbox || img.src);
            e.preventDefault();
            e.stopPropagation();
            openLightbox(img.dataset.lightbox || img.src);
        }

        img.addEventListener('click', handleImageTap);
        img.addEventListener('touchend', function(e) {
            console.log('[Inventory] Image touchend, touches:', e.changedTouches ? e.changedTouches.length : 0);
            // Only handle single touch
            if (e.changedTouches && e.changedTouches.length === 1) {
                handleImageTap(e);
            }
        });
    });
}

function openLightbox(src) {
    console.log('[Inventory] openLightbox called with src:', src);
    const lightbox = document.getElementById('lightbox');
    const img = document.getElementById('lightbox-img');
    if (!lightbox || !img) {
        console.log('[Inventory] Lightbox elements missing!');
        return;
    }

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
