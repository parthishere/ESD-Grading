/**
 * Main JavaScript for ESD Lab Grading System
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize all tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Initialize all popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function(popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
    
    // Auto-dismiss alerts after 5 seconds
    setTimeout(function() {
        const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
        alerts.forEach(function(alert) {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);
    
    // Toggle sidebar on mobile
    const sidebarToggle = document.getElementById('sidebarToggle');
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', function(e) {
            e.preventDefault();
            document.body.classList.toggle('sidebar-toggled');
            document.querySelector('.sidebar').classList.toggle('toggled');
        });
    }
    
    // Close sidebar on click outside on mobile
    document.addEventListener('click', function(event) {
        const sidebar = document.querySelector('.sidebar');
        const sidebarToggle = document.getElementById('sidebarToggle');
        
        if (sidebar && sidebar.classList.contains('toggled') && 
            !sidebar.contains(event.target) && 
            sidebarToggle !== event.target) {
            document.body.classList.remove('sidebar-toggled');
            sidebar.classList.remove('toggled');
        }
    });
    
    // Add active class to current nav item based on URL
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('.navbar-nav .nav-link');
    
    navLinks.forEach(function(link) {
        const href = link.getAttribute('href');
        if (href && currentPath.startsWith(href) && href !== '/') {
            link.classList.add('active');
            
            // If in a dropdown, also highlight the dropdown parent
            const dropdown = link.closest('.dropdown');
            if (dropdown) {
                dropdown.querySelector('.dropdown-toggle').classList.add('active');
            }
        } else if (href === '/' && currentPath === '/') {
            link.classList.add('active');
        }
    });
    
    // Handle confirmation modals
    const confirmButtons = document.querySelectorAll('[data-confirm]');
    confirmButtons.forEach(function(button) {
        button.addEventListener('click', function(e) {
            const message = this.getAttribute('data-confirm');
            if (!confirm(message)) {
                e.preventDefault();
            }
        });
    });
    
    // Handle table sorting
    const sortableHeaders = document.querySelectorAll('th[data-sort]');
    sortableHeaders.forEach(function(header) {
        header.addEventListener('click', function() {
            const sortBy = this.getAttribute('data-sort');
            const currentUrl = new URL(window.location.href);
            
            // Set sort parameter
            currentUrl.searchParams.set('sort', sortBy);
            
            // Toggle direction if already sorting by this column
            if (currentUrl.searchParams.get('dir') === 'asc' && 
                currentUrl.searchParams.get('sort') === sortBy) {
                currentUrl.searchParams.set('dir', 'desc');
            } else {
                currentUrl.searchParams.set('dir', 'asc');
            }
            
            window.location.href = currentUrl.toString();
        });
    });
    
    // Show current sorting direction on table headers
    const currentSort = new URLSearchParams(window.location.search).get('sort');
    const currentDir = new URLSearchParams(window.location.search).get('dir') || 'asc';
    
    if (currentSort) {
        const header = document.querySelector(`th[data-sort="${currentSort}"]`);
        if (header) {
            const icon = document.createElement('i');
            icon.className = `fas fa-sort-${currentDir === 'asc' ? 'up' : 'down'} ms-1`;
            header.appendChild(icon);
        }
    }
    
    // Handle dynamic form fields (add/remove)
    const addFieldButtons = document.querySelectorAll('[data-add-field]');
    addFieldButtons.forEach(function(button) {
        button.addEventListener('click', function() {
            const targetId = this.getAttribute('data-add-field');
            const target = document.getElementById(targetId);
            const template = document.getElementById(`${targetId}-template`);
            
            if (target && template) {
                const newField = template.content.cloneNode(true);
                const index = target.children.length;
                
                // Update form field names and ids with new index
                newField.querySelectorAll('[name], [id], [for]').forEach(function(el) {
                    ['name', 'id', 'for'].forEach(function(attr) {
                        if (el.hasAttribute(attr)) {
                            el.setAttribute(
                                attr, 
                                el.getAttribute(attr).replace('__prefix__', index)
                            );
                        }
                    });
                });
                
                target.appendChild(newField);
                
                // Update total forms count in management form
                const managementForm = document.getElementById(`id_${targetId}-TOTAL_FORMS`);
                if (managementForm) {
                    managementForm.value = index + 1;
                }
            }
        });
    });
    
    // Handle dynamic form field removal
    document.addEventListener('click', function(e) {
        if (e.target && e.target.classList.contains('remove-field')) {
            e.preventDefault();
            
            const row = e.target.closest('.dynamic-form-row');
            if (row) {
                const formsetId = row.closest('[id]').id;
                row.remove();
                
                // Update total forms count in management form
                const managementForm = document.getElementById(`id_${formsetId}-TOTAL_FORMS`);
                if (managementForm) {
                    managementForm.value = parseInt(managementForm.value) - 1;
                }
                
                // Re-number remaining forms
                const formRows = document.querySelectorAll(`#${formsetId} .dynamic-form-row`);
                formRows.forEach(function(formRow, index) {
                    formRow.querySelectorAll('[name], [id], [for]').forEach(function(el) {
                        ['name', 'id', 'for'].forEach(function(attr) {
                            if (el.hasAttribute(attr)) {
                                const currentValue = el.getAttribute(attr);
                                const newValue = currentValue.replace(/-\d+-/, `-${index}-`);
                                el.setAttribute(attr, newValue);
                            }
                        });
                    });
                });
            }
        }
    });
});