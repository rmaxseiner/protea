/**
 * Inventory Web UI - Application JavaScript
 * Minimal JS for mobile navigation, lightbox, and interactivity
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize browse tree if on browse page
    if (document.querySelector('[data-page="browse"]')) {
        initBrowseTree();
    }

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
var lightboxZoomed = false;

function initLightbox() {
    // Create lightbox elements if they don't exist
    if (!document.getElementById('lightbox')) {
        const lightbox = document.createElement('div');
        lightbox.id = 'lightbox';
        lightbox.className = 'fixed inset-0 z-[100] bg-black bg-opacity-95 hidden';
        lightbox.innerHTML = `
            <button id="lightbox-close" class="absolute top-4 right-4 text-white p-2 z-[101]" aria-label="Close">
                <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                </svg>
            </button>
            <div id="lightbox-zoom-hint" class="absolute bottom-4 left-1/2 transform -translate-x-1/2 text-white text-sm bg-black bg-opacity-50 px-3 py-1 rounded-full z-[101]">
                Tap image to zoom
            </div>
            <div id="lightbox-container" class="w-full h-full overflow-auto flex items-center justify-center p-4">
                <img id="lightbox-img" src="" alt="" class="cursor-zoom-in" style="max-width: 100%; max-height: 100%; object-fit: contain; touch-action: pinch-zoom pan-x pan-y;">
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

        // Click/touch on image to toggle zoom
        var lightboxImg = document.getElementById('lightbox-img');
        lightboxImg.addEventListener('click', function(e) {
            e.stopPropagation();
            toggleLightboxZoom();
        });
        lightboxImg.addEventListener('touchend', function(e) {
            if (e.changedTouches && e.changedTouches.length === 1) {
                e.preventDefault();
                e.stopPropagation();
                toggleLightboxZoom();
            }
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

    lightboxImages.forEach(function(img) {
        img.style.cursor = 'zoom-in';

        function handleImageTap(e) {
            e.preventDefault();
            e.stopPropagation();
            openLightbox(img.dataset.lightbox || img.src);
        }

        img.addEventListener('click', handleImageTap);
        img.addEventListener('touchend', function(e) {
            // Only handle single touch
            if (e.changedTouches && e.changedTouches.length === 1) {
                handleImageTap(e);
            }
        });
    });
}

function openLightbox(src) {
    const lightbox = document.getElementById('lightbox');
    const img = document.getElementById('lightbox-img');
    const hint = document.getElementById('lightbox-zoom-hint');
    if (!lightbox || !img) return;

    // Reset to fit-to-screen mode
    lightboxZoomed = false;
    img.style.maxWidth = '100%';
    img.style.maxHeight = '100%';
    img.style.width = 'auto';
    img.style.height = 'auto';
    img.className = 'cursor-zoom-in';
    if (hint) hint.textContent = 'Tap image to zoom';

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
    lightboxZoomed = false;
}

function toggleLightboxZoom() {
    const img = document.getElementById('lightbox-img');
    const hint = document.getElementById('lightbox-zoom-hint');
    const container = document.getElementById('lightbox-container');
    if (!img) return;

    lightboxZoomed = !lightboxZoomed;

    if (lightboxZoomed) {
        // Zoom to 100% (natural size)
        img.style.maxWidth = 'none';
        img.style.maxHeight = 'none';
        img.style.width = 'auto';
        img.style.height = 'auto';
        img.className = 'cursor-zoom-out';
        if (hint) hint.textContent = 'Tap to fit screen';
        // Scroll to center of image
        if (container) {
            setTimeout(function() {
                container.scrollLeft = (container.scrollWidth - container.clientWidth) / 2;
                container.scrollTop = (container.scrollHeight - container.clientHeight) / 2;
            }, 50);
        }
    } else {
        // Fit to screen
        img.style.maxWidth = '100%';
        img.style.maxHeight = '100%';
        img.style.width = 'auto';
        img.style.height = 'auto';
        img.className = 'cursor-zoom-in';
        if (hint) hint.textContent = 'Tap image to zoom';
        // Reset scroll position
        if (container) {
            container.scrollLeft = 0;
            container.scrollTop = 0;
        }
    }
}

// htmx extensions
document.body.addEventListener('htmx:afterSwap', function(event) {
    // Re-init lightbox for dynamically loaded content
    initLightbox();
});

// Helper to hide all item action forms
function hideAllItemForms() {
    var forms = ['edit-form', 'use-form', 'add-form', 'move-form'];
    forms.forEach(function(id) {
        var form = document.getElementById(id);
        if (form) form.classList.add('hidden');
    });
}

// Toggle edit form visibility on item detail page
function toggleEditForm() {
    var editForm = document.getElementById('edit-form');
    if (editForm) {
        var wasHidden = editForm.classList.contains('hidden');
        hideAllItemForms();
        if (wasHidden) {
            editForm.classList.remove('hidden');
            editForm.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }
}

// Toggle use item form visibility
function toggleUseForm() {
    var useForm = document.getElementById('use-form');
    if (useForm) {
        var wasHidden = useForm.classList.contains('hidden');
        hideAllItemForms();
        if (wasHidden) {
            useForm.classList.remove('hidden');
            useForm.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }
}

// Toggle add quantity form visibility
function toggleAddForm() {
    var addForm = document.getElementById('add-form');
    if (addForm) {
        var wasHidden = addForm.classList.contains('hidden');
        hideAllItemForms();
        if (wasHidden) {
            addForm.classList.remove('hidden');
            addForm.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }
}

// Toggle move item form visibility
function toggleMoveForm() {
    var moveForm = document.getElementById('move-form');
    if (moveForm) {
        var wasHidden = moveForm.classList.contains('hidden');
        hideAllItemForms();
        if (wasHidden) {
            moveForm.classList.remove('hidden');
            moveForm.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }
}

// ============================================
// Browse Tree Collapse/Expand Functions
// ============================================

// Toggle location expand/collapse
function toggleLocation(locationId) {
    var container = document.getElementById('location-bins-' + locationId);
    var chevron = document.querySelector('[data-location-toggle="' + locationId + '"]');
    if (!container) return;

    var isExpanded = !container.classList.contains('hidden');

    container.classList.toggle('hidden');
    if (chevron) {
        chevron.classList.toggle('rotate-90');
    }

    saveExpandState('location', locationId, !isExpanded);
}

// Toggle parent bin expand/collapse
function toggleBin(binId) {
    var container = document.getElementById('bin-children-' + binId);
    var chevron = document.querySelector('[data-bin-toggle="' + binId + '"]');
    if (!container) return;

    var isExpanded = !container.classList.contains('hidden');

    container.classList.toggle('hidden');
    if (chevron) {
        chevron.classList.toggle('rotate-90');
    }

    saveExpandState('bin', binId, !isExpanded);
}

// Save expand/collapse state to localStorage
function saveExpandState(type, id, isExpanded) {
    var key = 'browseTreeState';
    var state = {};
    try {
        state = JSON.parse(localStorage.getItem(key) || '{}');
    } catch (e) {
        state = {};
    }
    state[type + '-' + id] = isExpanded;
    try {
        localStorage.setItem(key, JSON.stringify(state));
    } catch (e) {
        // localStorage might be full or unavailable
    }
}

// Initialize browse tree from saved state
function initBrowseTree() {
    var state = {};
    try {
        state = JSON.parse(localStorage.getItem('browseTreeState') || '{}');
    } catch (e) {
        state = {};
    }

    // Restore expanded locations and bins
    Object.keys(state).forEach(function(key) {
        if (state[key]) {
            var parts = key.split('-');
            var type = parts[0];
            var id = parts.slice(1).join('-'); // Handle IDs with dashes
            if (type === 'location') {
                var container = document.getElementById('location-bins-' + id);
                var chevron = document.querySelector('[data-location-toggle="' + id + '"]');
                if (container) {
                    container.classList.remove('hidden');
                    if (chevron) {
                        chevron.classList.add('rotate-90');
                    }
                }
            } else if (type === 'bin') {
                var container = document.getElementById('bin-children-' + id);
                var chevron = document.querySelector('[data-bin-toggle="' + id + '"]');
                if (container) {
                    container.classList.remove('hidden');
                    if (chevron) {
                        chevron.classList.add('rotate-90');
                    }
                }
            }
        }
    });
}
