/**
 * Inventory Web UI - Application JavaScript
 * Minimal JS for mobile navigation and interactivity
 */

document.addEventListener('DOMContentLoaded', function() {
    // Mobile menu toggle
    const menuBtn = document.getElementById('mobile-menu-btn');
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');

    function openSidebar() {
        sidebar.classList.add('open');
        sidebar.classList.remove('-translate-x-full');
        overlay.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
    }

    function closeSidebar() {
        sidebar.classList.remove('open');
        sidebar.classList.add('-translate-x-full');
        overlay.classList.add('hidden');
        document.body.style.overflow = '';
    }

    if (menuBtn) {
        menuBtn.addEventListener('click', function(e) {
            e.preventDefault();
            if (sidebar.classList.contains('open')) {
                closeSidebar();
            } else {
                openSidebar();
            }
        });
    }

    if (overlay) {
        overlay.addEventListener('click', closeSidebar);
    }

    // Close sidebar on escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && sidebar && sidebar.classList.contains('open')) {
            closeSidebar();
        }
    });

    // Close sidebar when clicking a nav link (mobile)
    const navLinks = sidebar ? sidebar.querySelectorAll('a') : [];
    navLinks.forEach(function(link) {
        link.addEventListener('click', function() {
            if (window.innerWidth < 1024) {
                closeSidebar();
            }
        });
    });

    // Auto-focus search input on page load
    const searchInput = document.getElementById('search-input');
    if (searchInput && window.location.pathname === '/') {
        searchInput.focus();
    }
});

// htmx extensions
document.body.addEventListener('htmx:afterSwap', function(event) {
    // Scroll to top of results when search results update
    if (event.target.id === 'search-results') {
        event.target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
});
