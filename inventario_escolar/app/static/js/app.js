document.addEventListener('DOMContentLoaded', function() {
    // ===== Theme Toggle =====
    const STORAGE_KEY = 'sgide-theme';
    const html = document.documentElement;
    
    function applyTheme(theme) {
        html.setAttribute('data-theme', theme);
        const icon = document.getElementById('themeIcon');
        const label = document.getElementById('themeLabel');
        if (icon) {
            icon.className = theme === 'dark' ? 'fa-solid fa-sun' : 'fa-solid fa-moon';
        }
        if (label) label.textContent = theme === 'dark' ? 'Modo Claro' : 'Modo Oscuro';
    }
    
// Load saved theme or default to dark
    const savedTheme = localStorage.getItem(STORAGE_KEY) || 'dark';
    applyTheme(savedTheme);
    
    const toggleBtn = document.getElementById('themeToggle');
    if (toggleBtn) {
        toggleBtn.addEventListener('click', () => {
            const current = html.getAttribute('data-theme');
            const next = current === 'dark' ? 'light' : 'dark';
            localStorage.setItem(STORAGE_KEY, next);
            applyTheme(next);
        });
    }
    
    // ===== Sidebar Toggle =====
    const sidebar = document.getElementById('sidebar');
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebarOverlay = document.getElementById('sidebarOverlay');
    
    if (sidebarToggle && sidebar) {
        sidebarToggle.addEventListener('click', (e) => {
            e.stopPropagation();
            sidebar.classList.toggle('active');
            if (sidebarOverlay) sidebarOverlay.classList.toggle('active');
        });
    }
    
    if (sidebarOverlay) {
        sidebarOverlay.addEventListener('click', () => {
            sidebar.classList.remove('active');
            sidebarOverlay.classList.remove('active');
        });
    }
    
    // ===== Delete Confirmation Modal =====
    // When clicking a delete button with data-delete-url, show confirmation modal
    document.querySelectorAll('[data-delete-url]').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const url = btn.getAttribute('data-delete-url');
            const name = btn.getAttribute('data-delete-name') || 'este registro';
            const modal = document.getElementById('deleteModal');
            const form = document.getElementById('deleteForm');
            const nameSpan = document.getElementById('deleteName');
            if (modal && form) {
                form.action = url;
                if (nameSpan) nameSpan.textContent = name;
                modal.classList.add('active');
            }
        });
    });
    
    // Close modal
    document.querySelectorAll('[data-modal-close]').forEach(btn => {
        btn.addEventListener('click', () => {
            btn.closest('.glass-modal-overlay').classList.remove('active');
        });
    });
    
    // ===== Toast Notifications =====
    // Auto-dismiss flash messages after 5 seconds
    document.querySelectorAll('.toast').forEach(toast => {
        setTimeout(() => {
            toast.classList.add('toast-exit');
            setTimeout(() => toast.remove(), 300);
        }, 5000);
        
        const closeBtn = toast.querySelector('.toast-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                toast.classList.add('toast-exit');
                setTimeout(() => toast.remove(), 300);
            });
        }
    });
    
    // ===== File Upload Drag & Drop =====
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    
    if (dropZone && fileInput) {
        dropZone.addEventListener('click', () => fileInput.click());
        
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('drag-over');
        });
        
        dropZone.addEventListener('dragleave', () => {
            dropZone.classList.remove('drag-over');
        });
        
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('drag-over');
            if (e.dataTransfer.files.length) {
                fileInput.files = e.dataTransfer.files;
                updateFileName(fileInput);
            }
        });
        
        fileInput.addEventListener('change', () => updateFileName(fileInput));
    }
    
    function updateFileName(input) {
        const label = document.getElementById('fileName');
        if (label && input.files.length) {
            label.textContent = input.files[0].name;
        }
    }
    
    // ===== Active Sidebar Link =====
    const currentPath = window.location.pathname;
    document.querySelectorAll('.sidebar-link').forEach(link => {
        if (link.getAttribute('href') === currentPath || currentPath.startsWith(link.getAttribute('href'))) {
            link.classList.add('active');
        }
    });
});
