/**
 * Updated Signoff Form JavaScript
 * Now with student name autocomplete support
 */

document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const studentNameInput = document.getElementById('student-name-input');
    const studentIdField = document.getElementById('student-id-field');
    const studentInfo = document.getElementById('student-info');
    const studentName = document.getElementById('student-name');
    const studentEmail = document.getElementById('student-email');
    const labSelect = document.getElementById('lab-select');
    const partsContainer = document.getElementById('parts-container');
    const partSelection = document.getElementById('part-selection');
    const initialMessage = document.getElementById('initial-message');
    const gradingForm = document.getElementById('grading-form');
    const criteriaContainer = document.getElementById('criteria-container');
    const gradingHeader = document.getElementById('grading-header');
    const labBadge = document.getElementById('lab-badge');
    const studentIdInput = document.getElementById('student-id-input');
    const partIdInput = document.getElementById('part-id-input');
    const signoffForm = document.getElementById('signoff-form');
    const resetFormBtn = document.getElementById('reset-form');
    const printBtn = document.getElementById('print-btn');
    const successModal = new bootstrap.Modal(document.getElementById('success-modal'));
    const newSignoffBtn = document.getElementById('new-signoff-btn');
    const historyCard = document.getElementById('history-card');
    const signoffHistory = document.getElementById('signoff-history');
    
    // State variables
    let currentStudent = null;
    let currentParts = [];
    let currentCriteria = [];
    
    // Event Listeners
    labSelect.addEventListener('change', loadParts);
    signoffForm.addEventListener('submit', submitSignoff);
    resetFormBtn.addEventListener('click', resetForm);
    printBtn.addEventListener('click', printSignoff);
    newSignoffBtn.addEventListener('click', newSignoff);
    
    // Listen for student selection from autocomplete
    document.addEventListener('studentSelected', function(e) {
        const student = e.detail.student;
        handleStudentSelection(student);
    });
    
    /**
     * Handle when a student is selected from autocomplete
     */
    function handleStudentSelection(student) {
        // Store student data
        currentStudent = {
            id: student.id,
            studentId: student.student_id,
            name: student.name,
            email: student.email || ''
        };
        
        // Update UI
        studentName.textContent = student.name;
        studentEmail.textContent = student.email || 'No email provided';
        studentInfo.style.display = 'block';
        studentIdInput.value = student.student_id;
        
        // Load parts if lab is already selected
        if (labSelect.value) {
            loadParts();
        }
    }
    
    /**
     * Load parts for the selected lab
     */
    function loadParts() {
        const labId = labSelect.value;
        if (!labId) {
            partSelection.style.display = 'none';
            return;
        }
        
        // Show loading indicator
        showSpinner();
        
        // AJAX call to get parts for the selected lab
        fetch(`/api/get-parts/?lab_id=${labId}`)
            .then(response => response.json())
            .then(data => {
                hideSpinner();
                
                currentParts = data;
                
                if (data.length > 0) {
                    // Render parts
                    renderParts(data);
                    partSelection.style.display = 'block';
                    
                    // If we have a student, check for existing signoffs
                    if (currentStudent) {
                        checkExistingSignoffs(labId);
                    }
                } else {
                    partsContainer.innerHTML = '<div class="alert alert-info">No parts found for this lab</div>';
                    partSelection.style.display = 'block';
                }
            })
            .catch(error => {
                hideSpinner();
                console.error('Error:', error);
                showAlert('Error loading parts', 'danger');
            });
    }
    
    /**
     * Render parts list
     * @param {Array} parts - Array of part objects
     */
    function renderParts(parts) {
        partsContainer.innerHTML = '';
        
        parts.forEach(part => {
            const item = document.createElement('a');
            item.href = '#';
            item.className = 'list-group-item list-group-item-action part-item';
            item.setAttribute('data-part-id', part.id);
            
            // Status badge (will be set later if there's an existing signoff)
            let statusBadge = '';
            
            // Create part item HTML
            item.innerHTML = `
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <strong>${part.name}</strong>
                    </div>
                    <span class="status-badge" id="status-${part.id}">${statusBadge}</span>
                </div>
            `;
            
            // Add click event to load criteria for the part
            item.addEventListener('click', function(e) {
                e.preventDefault();
                
                // Remove active class from all parts
                document.querySelectorAll('.part-item').forEach(el => {
                    el.classList.remove('active');
                });
                
                // Add active class to clicked part
                this.classList.add('active');
                
                // Load criteria for this part
                loadCriteria(part.id, part.name);
            });
            
            partsContainer.appendChild(item);
        });
    }
    
    /**
     * Check for existing signoffs for the current student and lab
     * @param {number} labId - ID of the selected lab
     */
    function checkExistingSignoffs(labId) {
        if (!currentStudent) return;
        
        fetch(`/api/get-signoffs/?student_id=${currentStudent.studentId}&lab_id=${labId}`)
            .then(response => response.json())
            .then(data => {
                // Update status badges for parts with existing signoffs
                data.forEach(signoff => {
                    const statusBadge = document.getElementById(`status-${signoff.part_id}`);
                    if (statusBadge) {
                        statusBadge.className = `status-badge ${signoff.status}`;
                        statusBadge.textContent = signoff.status.charAt(0).toUpperCase() + signoff.status.slice(1);
                    }
                });
            })
            .catch(error => {
                console.error('Error:', error);
            });
    }
    
    /**
     * Load criteria for the selected part
     * @param {number} partId - ID of the selected part
     * @param {string} partName - Name of the selected part
     */
    function loadCriteria