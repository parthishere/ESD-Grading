/**
 * Student Autocomplete Functionality
 */

class StudentAutocomplete {
    constructor(inputField, options = {}) {
        // Default options
        this.options = {
            minChars: 2,
            delay: 300,
            resultsContainerId: 'student-results',
            onSelect: null,
            placeholder: 'Search by name or ID...',
            noResultsText: 'No students found',
            loadingText: 'Searching...',
            searchEndpoint: '/api/student-name-search/',
            ...options
        };

        // DOM elements
        this.inputField = inputField;
        this.resultsContainer = document.getElementById(this.options.resultsContainerId);
        
        if (!this.resultsContainer) {
            // Create results container if it doesn't exist
            this.resultsContainer = document.createElement('div');
            this.resultsContainer.id = this.options.resultsContainerId;
            this.resultsContainer.className = 'student-results';
            this.inputField.parentNode.insertBefore(this.resultsContainer, this.inputField.nextSibling);
        }
        
        // Set placeholder
        this.inputField.setAttribute('placeholder', this.options.placeholder);
        
        // Style the results container
        this.styleResultsContainer();
        
        // State variables
        this.timer = null;
        this.lastQuery = '';
        this.selectedIndex = -1;
        this.results = [];
        
        // Bind events
        this.bindEvents();
    }
    
    styleResultsContainer() {
        // Apply styling to results container
        this.resultsContainer.style.position = 'absolute';
        this.resultsContainer.style.zIndex = '1000';
        this.resultsContainer.style.backgroundColor = 'white';
        this.resultsContainer.style.border = '1px solid #ced4da';
        this.resultsContainer.style.borderRadius = '0.25rem';
        this.resultsContainer.style.boxShadow = '0 2px 5px rgba(0,0,0,0.2)';
        this.resultsContainer.style.maxHeight = '300px';
        this.resultsContainer.style.overflowY = 'auto';
        this.resultsContainer.style.display = 'none';
        
        // Set width to match input field
        this.resultsContainer.style.width = `${this.inputField.offsetWidth}px`;
        
        // Position below input field
        const inputRect = this.inputField.getBoundingClientRect();
        this.resultsContainer.style.top = `${this.inputField.offsetHeight}px`;
        this.resultsContainer.style.left = '0';
    }
    
    bindEvents() {
        // Input field events
        this.inputField.addEventListener('input', this.onInput.bind(this));
        this.inputField.addEventListener('keydown', this.onKeyDown.bind(this));
        this.inputField.addEventListener('focus', this.onFocus.bind(this));
        
        // Close results when clicking outside
        document.addEventListener('click', (e) => {
            if (!this.inputField.contains(e.target) && !this.resultsContainer.contains(e.target)) {
                this.hideResults();
            }
        });
        
        // Window resize (to adjust position)
        window.addEventListener('resize', () => {
            this.styleResultsContainer();
        });
    }
    
    onInput(e) {
        const query = this.inputField.value.trim();
        
        // Clear previous timer
        if (this.timer) {
            clearTimeout(this.timer);
        }
        
        // Clear results if query is too short
        if (query.length < this.options.minChars) {
            this.hideResults();
            return;
        }
        
        // Skip if query is the same as last time
        if (query === this.lastQuery) {
            return;
        }
        
        this.lastQuery = query;
        
        // Show loading indicator
        this.showLoading();
        
        // Set timer to fetch results
        this.timer = setTimeout(() => {
            this.fetchResults(query);
        }, this.options.delay);
    }
    
    onKeyDown(e) {
        // Only handle key presses if results are visible
        if (this.resultsContainer.style.display !== 'block') {
            return;
        }
        
        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                this.selectNext();
                break;
                
            case 'ArrowUp':
                e.preventDefault();
                this.selectPrevious();
                break;
                
            case 'Enter':
                e.preventDefault();
                if (this.selectedIndex >= 0) {
                    this.selectResult(this.results[this.selectedIndex]);
                }
                break;
                
            case 'Escape':
                e.preventDefault();
                this.hideResults();
                break;
        }
    }
    
    onFocus(e) {
        const query = this.inputField.value.trim();
        if (query.length >= this.options.minChars) {
            this.fetchResults(query);
        }
    }
    
    fetchResults(query) {
        // Fetch data from API
        fetch(`${this.options.searchEndpoint}?query=${encodeURIComponent(query)}`)
            .then(response => response.json())
            .then(data => {
                this.results = data.students;
                this.renderResults();
            })
            .catch(error => {
                console.error('Error fetching student data:', error);
                this.renderError('Error loading results');
            });
    }
    
    renderResults() {
        this.resultsContainer.innerHTML = '';
        
        if (this.results.length === 0) {
            this.renderNoResults();
            return;
        }
        
        const ul = document.createElement('ul');
        ul.className = 'student-list';
        ul.style.listStyle = 'none';
        ul.style.padding = '0';
        ul.style.margin = '0';
        
        this.results.forEach((student, index) => {
            const li = document.createElement('li');
            li.className = 'student-item';
            li.style.padding = '8px 16px';
            li.style.cursor = 'pointer';
            li.style.borderBottom = '1px solid #eee';
            
            // Highlight on hover
            li.addEventListener('mouseover', () => {
                this.selectedIndex = index;
                this.highlightSelected();
            });
            
            // Select on click
            li.addEventListener('click', () => {
                this.selectResult(student);
            });
            
            const nameSpan = document.createElement('div');
            nameSpan.className = 'student-name';
            nameSpan.textContent = student.name;
            nameSpan.style.fontWeight = 'bold';
            
            const idSpan = document.createElement('div');
            idSpan.className = 'student-id';
            idSpan.textContent = `ID: ${student.student_id}`;
            idSpan.style.fontSize = '0.85em';
            idSpan.style.color = '#6c757d';
            
            li.appendChild(nameSpan);
            li.appendChild(idSpan);
            ul.appendChild(li);
        });
        
        this.resultsContainer.appendChild(ul);
        this.showResults();
        
        // Reset selection
        this.selectedIndex = -1;
    }
    
    renderNoResults() {
        const div = document.createElement('div');
        div.className = 'no-results';
        div.textContent = this.options.noResultsText;
        div.style.padding = '8px 16px';
        div.style.color = '#6c757d';
        div.style.textAlign = 'center';
        
        this.resultsContainer.appendChild(div);
        this.showResults();
    }
    
    renderError(message) {
        const div = document.createElement('div');
        div.className = 'error-message';
        div.textContent = message;
        div.style.padding = '8px 16px';
        div.style.color = '#dc3545';
        div.style.textAlign = 'center';
        
        this.resultsContainer.appendChild(div);
        this.showResults();
    }
    
    showLoading() {
        this.resultsContainer.innerHTML = '';
        
        const div = document.createElement('div');
        div.className = 'loading-message';
        div.textContent = this.options.loadingText;
        div.style.padding = '8px 16px';
        div.style.color = '#6c757d';
        div.style.textAlign = 'center';
        
        this.resultsContainer.appendChild(div);
        this.showResults();
    }
    
    showResults() {
        this.resultsContainer.style.display = 'block';
    }
    
    hideResults() {
        this.resultsContainer.style.display = 'none';
        this.selectedIndex = -1;
    }
    
    selectNext() {
        if (this.results.length === 0) return;
        
        this.selectedIndex = (this.selectedIndex + 1) % this.results.length;
        this.highlightSelected();
    }
    
    selectPrevious() {
        if (this.results.length === 0) return;
        
        this.selectedIndex = (this.selectedIndex - 1 + this.results.length) % this.results.length;
        this.highlightSelected();
    }
    
    highlightSelected() {
        const items = this.resultsContainer.querySelectorAll('.student-item');
        items.forEach((item, index) => {
            if (index === this.selectedIndex) {
                item.style.backgroundColor = '#e9ecef';
            } else {
                item.style.backgroundColor = '';
            }
        });
    }
    
    selectResult(student) {
        // Fill input with selected student name
        this.inputField.value = student.name;
        
        // Hide results
        this.hideResults();
        
        // Call onSelect callback if provided
        if (typeof this.options.onSelect === 'function') {
            this.options.onSelect(student);
        }
    }
}

// Usage:
document.addEventListener('DOMContentLoaded', function() {
    // Initialize student search in signoff form
    const studentNameInput = document.getElementById('student-name-input');
    if (studentNameInput) {
        const studentIdField = document.getElementById('student-id-field'); // Hidden field for ID
        const studentEmailDisplay = document.getElementById('student-email'); // Element to display email
        const studentInfoContainer = document.getElementById('student-info'); // Container to show/hide
        
        new StudentAutocomplete(studentNameInput, {
            resultsContainerId: 'student-search-results',
            onSelect: function(student) {
                // Store student ID in hidden field
                if (studentIdField) {
                    studentIdField.value = student.student_id;
                }
                
                // Show student info
                if (studentEmailDisplay) {
                    studentEmailDisplay.textContent = student.email || 'No email provided';
                }
                
                // Show student info container
                if (studentInfoContainer) {
                    studentInfoContainer.style.display = 'block';
                }
                
                // Trigger event to notify other components
                const event = new CustomEvent('studentSelected', { 
                    detail: { student } 
                });
                document.dispatchEvent(event);
            }
        });
    }
});