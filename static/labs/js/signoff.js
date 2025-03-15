/**
 * Updated Signoff Form JavaScript
 * Enhanced with student name autocomplete support and criteria handling
 */

document.addEventListener("DOMContentLoaded", function () {
  // DOM Elements
  const studentNameInput = document.getElementById("student-name-input");
  const studentIdField = document.getElementById("student-id-field");
  const studentInfo = document.getElementById("student-info");
  const studentName = document.getElementById("student-name");
  const studentEmail = document.getElementById("student-email");
  const labSelect = document.getElementById("lab-select");
  const partsContainer = document.getElementById("parts-container");
  const partSelection = document.getElementById("part-selection");
  const initialMessage = document.getElementById("initial-message");
  const gradingForm = document.getElementById("grading-form");
  const criteriaContainer = document.getElementById("criteria-container");
  const gradingHeader = document.getElementById("grading-header");
  const labBadge = document.getElementById("lab-badge");
  const studentIdInput = document.getElementById("student-id-input");
  const partIdInput = document.getElementById("part-id-input");
  const signoffForm = document.getElementById("signoff-form");
  const resetFormBtn = document.getElementById("reset-form");
  const printBtn = document.getElementById("print-btn");
  const successModal = new bootstrap.Modal(
    document.getElementById("success-modal")
  );
  const newSignoffBtn = document.getElementById("new-signoff-btn");
  const historyCard = document.getElementById("history-card");
  const signoffHistory = document.getElementById("signoff-history");

  // State variables
  let currentStudent = null;
  let currentParts = [];
  let currentCriteria = [];

  // Event Listeners
  labSelect.addEventListener("change", loadParts);
  signoffForm.addEventListener("submit", submitSignoff);
  resetFormBtn.addEventListener("click", resetForm);
  printBtn.addEventListener("click", printSignoff);
  newSignoffBtn.addEventListener("click", newSignoff);

  // Listen for student selection from autocomplete
  document.addEventListener("studentSelected", function (e) {
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
      email: student.email || "",
    };

    // Update UI
    studentName.textContent = student.name;
    studentEmail.textContent = student.email || "No email provided";
    studentInfo.style.display = "block";
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
      partSelection.style.display = "none";
      return;
    }

    // Show loading indicator
    showSpinner();

    // AJAX call to get parts for the selected lab
    fetch(`/api/get-parts/?lab_id=${labId}`)
      .then((response) => response.json())
      .then((data) => {
        hideSpinner();

        currentParts = data;

        if (data.length > 0) {
          // Render parts
          renderParts(data);
          partSelection.style.display = "block";

          // If we have a student, check for existing signoffs
          if (currentStudent) {
            checkExistingSignoffs(labId);
          }
        } else {
          partsContainer.innerHTML =
            '<div class="alert alert-info">No parts found for this lab</div>';
          partSelection.style.display = "block";
        }
      })
      .catch((error) => {
        hideSpinner();
        console.error("Error:", error);
        showAlert("Error loading parts", "danger");
      });
  }

  /**
   * Render parts list
   * @param {Array} parts - Array of part objects
   */
  function renderParts(parts) {
    partsContainer.innerHTML = "";

    parts.forEach((part) => {
      const item = document.createElement("a");
      item.href = "#";
      item.className = "list-group-item list-group-item-action part-item";
      item.setAttribute("data-part-id", part.id);

      // Status badge (will be set later if there's an existing signoff)
      let statusBadge = "";

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
      item.addEventListener("click", function (e) {
        e.preventDefault();

        // Remove active class from all parts
        document.querySelectorAll(".part-item").forEach((el) => {
          el.classList.remove("active");
        });

        // Add active class to clicked part
        this.classList.add("active");

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

    fetch(
      `/api/get-signoffs/?student_id=${currentStudent.studentId}&lab_id=${labId}`
    )
      .then((response) => response.json())
      .then((data) => {
        // Update status badges for parts with existing signoffs
        data.forEach((signoff) => {
          const statusBadge = document.getElementById(
            `status-${signoff.part_id}`
          );
          if (statusBadge) {
            statusBadge.className = `status-badge ${signoff.status}`;
            statusBadge.textContent =
              signoff.status.charAt(0).toUpperCase() + signoff.status.slice(1);
          }
        });
      })
      .catch((error) => {
        console.error("Error:", error);
      });
  }

  /**
   * Load criteria for the selected part
   * @param {number} partId - ID of the selected part
   * @param {string} partName - Name of the selected part
   */
  function loadCriteria(partId, partName) {
    // Show loading indicator
    showSpinner();

    // AJAX call to get criteria for the selected part
    fetch(`/api/get-criteria/?part_id=${partId}`)
      .then((response) => response.json())
      .then((data) => {
        hideSpinner();

        currentCriteria = data;

        if (data.length > 0) {
          // Render criteria
          renderCriteria(data);

          // Update form headers
          const selectedLab = labSelect.options[labSelect.selectedIndex].text;
          gradingHeader.textContent = partName;
          labBadge.textContent = selectedLab;

          // Set part ID in form
          partIdInput.value = partId;

          // Show the grading form, hide initial message
          initialMessage.style.display = "none";
          gradingForm.style.display = "block";

          // Check for existing signoff for this student and part
          if (currentStudent) {
            checkExistingSignoff(partId);
          }
        } else {
          showAlert("No grading criteria found for this part", "warning");
        }
      })
      .catch((error) => {
        hideSpinner();
        console.error("Error:", error);
        showAlert("Error loading criteria", "danger");
      });
  }

  /**
   * Render criteria list as radio buttons
   * @param {Array} criteria - Array of criteria objects
   */
  function renderCriteria(criteria) {
    criteriaContainer.innerHTML = "";

    // Define the standard quality levels
    const qualityLevels = [
      { value: 0, label: "Not Applicable" },
      { value: 1, label: "Poor/Not Complete" },
      { value: 2, label: "Meets Requirements" },
      { value: 3, label: "Exceeds Requirements" },
      { value: 4, label: "Outstanding" },
    ];

    // Use the provided criteria or default criteria if none provided
    const criteriaToDraw =
      criteria.length > 0
        ? criteria
        : [
            { id: "default_1", name: "SPLD code", max_points: 10 },
            {
              id: "default_2",
              name: "Assembly Language Code Style",
              max_points: 10,
            },
            {
              id: "default_3",
              name: "Required Elements functionality",
              max_points: 10,
            },
            {
              id: "default_4",
              name: "Sign-off done without excessive retries",
              max_points: 10,
            },
            {
              id: "default_5",
              name: "Student understanding and skills",
              max_points: 10,
            },
          ];

    // Draw a header row with criteria title
    const headerRow = document.createElement("tr");
    const headerCell = document.createElement("th");
    headerCell.setAttribute("colspan", "6");
    headerCell.classList.add("bg-light", "pt-3");
    headerCell.innerHTML = "<h5>Quality Criteria</h5>";
    headerRow.appendChild(headerCell);
    criteriaContainer.appendChild(headerRow);

    // Draw a row for each criterion
    criteriaToDraw.forEach((criterion) => {
      const row = document.createElement("tr");

      // Create cell for criterion name
      const nameCell = document.createElement("td");
      nameCell.textContent = criterion.name;
      row.appendChild(nameCell);

      // Create cells for each quality level
      qualityLevels.forEach((level) => {
        const cell = document.createElement("td");
        cell.className = "text-center";

        const input = document.createElement("input");
        input.type = "radio";
        input.name = `criteria_${criterion.id}`;
        input.value = level.value;

        // Set "Meets Requirements" as default
        if (level.value === 2) {
          input.checked = true;
        }

        cell.appendChild(input);
        row.appendChild(cell);
      });

      criteriaContainer.appendChild(row);
    });
    
    // Add the evaluation sheet criteria
    renderEvaluationSheet();
  }
  
  /**
   * Render evaluation sheet form
   */
  function renderEvaluationSheet() {
    // Define evaluation criteria with their default max marks
    const evaluationCriteria = [
      { id: "cleanliness", name: "Cleanliness", max_marks: 5.0 },
      { id: "hardware", name: "Hardware", max_marks: 10.0 },
      { id: "timeliness", name: "Timeliness", max_marks: 5.0 },
      { id: "student_preparation", name: "Student Preparation", max_marks: 10.0 },
      { id: "code_implementation", name: "Code Implementation", max_marks: 15.0 },
      { id: "commenting", name: "Commenting", max_marks: 5.0 },
      { id: "schematic", name: "Schematic", max_marks: 10.0 },
      { id: "course_participation", name: "Course Participation", max_marks: 5.0 },
    ];

    // Define status options
    const statusOptions = [
      { value: "ER", label: "Exceeds Requirements" },
      { value: "MR", label: "Meets Requirements" },
      { value: "MM", label: "Minimally Meets" },
      { value: "IR", label: "Improvement Required" },
      { value: "ND", label: "Not Demonstrated" },
    ];

    // Add a separator row
    const separatorRow = document.createElement("tr");
    const separatorCell = document.createElement("td");
    separatorCell.setAttribute("colspan", "6");
    separatorCell.className = "pt-4";
    separatorRow.appendChild(separatorCell);
    criteriaContainer.appendChild(separatorRow);

    // Add a header row for the evaluation sheet
    const headerRow = document.createElement("tr");
    const headerCell = document.createElement("th");
    headerCell.setAttribute("colspan", "6");
    headerCell.classList.add("bg-light");
    headerCell.innerHTML = "<h5>Evaluation Sheet</h5>";
    headerRow.appendChild(headerCell);
    criteriaContainer.appendChild(headerRow);

    // Add column headers
    const columnHeaderRow = document.createElement("tr");
    const criterionHeaderCell = document.createElement("th");
    criterionHeaderCell.textContent = "Criterion";
    columnHeaderRow.appendChild(criterionHeaderCell);
    
    const marksHeaderCell = document.createElement("th");
    marksHeaderCell.textContent = "Max Marks";
    marksHeaderCell.className = "text-center";
    columnHeaderRow.appendChild(marksHeaderCell);
    
    const statusHeaderCell = document.createElement("th");
    statusHeaderCell.setAttribute("colspan", "4");
    statusHeaderCell.textContent = "Status";
    statusHeaderCell.className = "text-center";
    columnHeaderRow.appendChild(statusHeaderCell);
    
    criteriaContainer.appendChild(columnHeaderRow);

    // Add rows for each evaluation criterion
    evaluationCriteria.forEach(criterion => {
      const row = document.createElement("tr");
      
      // Criterion name
      const nameCell = document.createElement("td");
      nameCell.textContent = criterion.name;
      row.appendChild(nameCell);
      
      // Max marks input
      const marksCell = document.createElement("td");
      marksCell.className = "text-center";
      const marksInput = document.createElement("input");
      marksInput.type = "number";
      marksInput.name = `eval_${criterion.id}_max`;
      marksInput.value = criterion.max_marks;
      marksInput.min = "0";
      marksInput.step = "0.5";
      marksInput.className = "form-control form-control-sm";
      marksInput.style.width = "70px";
      marksCell.appendChild(marksInput);
      row.appendChild(marksCell);
      
      // Status dropdown
      const statusCell = document.createElement("td");
      statusCell.setAttribute("colspan", "4");
      statusCell.className = "text-center";
      
      const statusSelect = document.createElement("select");
      statusSelect.name = `eval_${criterion.id}`;
      statusSelect.className = "form-select form-select-sm";
      
      // Add options to dropdown
      statusOptions.forEach(option => {
        const optionElement = document.createElement("option");
        optionElement.value = option.value;
        optionElement.textContent = option.label;
        
        // Set "Meets Requirements" as default
        if (option.value === "MR") {
          optionElement.selected = true;
        }
        
        statusSelect.appendChild(optionElement);
      });
      
      statusCell.appendChild(statusSelect);
      row.appendChild(statusCell);
      
      criteriaContainer.appendChild(row);
    });
  }

  /**
   * Check for an existing signoff for this student and part
   * @param {number} partId - ID of the selected part
   */
  function checkExistingSignoff(partId) {
    // Show loading indicator
    showSpinner();
    
    fetch(
      `/api/get-signoff-details/?student_id=${currentStudent.studentId}&part_id=${partId}`
    )
      .then((response) => response.json())
      .then((data) => {
        hideSpinner();
        
        if (data.found) {
          // Populate form with existing data
          document.getElementById("comments").value = data.comments || "";

          // Set overall score
          const overallScoreMap = {
            rejected: data.overall_score <= 1 ? data.overall_score : 1,
            approved: data.overall_score >= 2 ? data.overall_score : 2,
            pending: 2,
          };

          const scoreValue = overallScoreMap[data.status];
          const overallRadio = document.querySelector(
            `input[name="overall_score"][value="${scoreValue}"]`
          );
          if (overallRadio) {
            overallRadio.checked = true;
          }

          // Set criteria scores
          if (data.quality_scores && data.quality_scores.length > 0) {
            data.quality_scores.forEach((score) => {
              const scoreValue = calculateRadioValue(
                score.score,
                score.criteria__max_points
              );
              const radio = document.querySelector(
                `input[name="criteria_${score.criteria_id}"][value="${scoreValue}"]`
              );
              if (radio) {
                radio.checked = true;
              }
            });
          }
          
          // Set evaluation sheet data if available
          if (data.has_evaluation_sheet) {
            const evalSheet = data.evaluation_sheet;
            
            // For each evaluation criterion, set its value and max marks
            for (const [criterion, values] of Object.entries(evalSheet)) {
              // Skip non-criterion fields
              if (criterion === 'total_marks' || criterion === 'total_max_marks' || criterion === 'percentage') {
                continue;
              }
              
              // Set the status dropdown
              const statusSelect = document.querySelector(`select[name="eval_${criterion}"]`);
              if (statusSelect && values.value) {
                statusSelect.value = values.value;
              }
              
              // Set the max marks input
              const marksInput = document.querySelector(`input[name="eval_${criterion}_max"]`);
              if (marksInput && values.max_marks) {
                marksInput.value = values.max_marks;
              }
            }
          }

          // Show history if available
          if (data.history && data.history.length > 0) {
            renderSignoffHistory(data.history);
            historyCard.style.display = "block";
          } else {
            historyCard.style.display = "none";
          }

          showAlert("Loaded existing signoff data", "info");
        } else {
          // Reset form for new signoff
          resetFormInputs();
          historyCard.style.display = "none";
        }
      })
      .catch((error) => {
        hideSpinner();
        console.error("Error:", error);
        showAlert("Error loading signoff data. Please try again.", "danger");
      });
  }

  /**
   * Calculate radio value from score and max points
   * @param {number} score - The actual score
   * @param {number} maxPoints - The maximum possible score
   * @returns {number} - The radio button value (0-4)
   */
  function calculateRadioValue(score, maxPoints) {
    const percentage = score / maxPoints;

    if (score === 0) return 0; // Not Applicable
    if (percentage <= 0.25) return 1; // Poor/Not Complete
    if (percentage <= 0.5) return 2; // Meets Requirements
    if (percentage <= 0.75) return 3; // Exceeds Requirements
    return 4; // Outstanding
  }

  /**
   * Render signoff history
   * @param {Array} history - Array of historical signoff objects
   */
  function renderSignoffHistory(history) {
    signoffHistory.innerHTML = "";

    history.forEach((item) => {
      const historyItem = document.createElement("div");
      historyItem.className = `history-item ${item.status}`;

      const date = new Date(item.date_updated);
      const formattedDate =
        date.toLocaleDateString() + " " + date.toLocaleTimeString();

      historyItem.innerHTML = `
                <div class="d-flex justify-content-between">
                    <strong>${item.instructor__username}</strong>
                    <span class="small text-muted">${formattedDate}</span>
                </div>
                <div class="mt-1">
                    <span class="badge bg-${getStatusColor(item.status)}">${
        item.status
      }</span>
                </div>
                <p class="mt-2 mb-0 small">${item.comments || "No comments"}</p>
            `;

      signoffHistory.appendChild(historyItem);
    });
  }

  /**
   * Get bootstrap color class for status
   * @param {string} status - Status string
   * @returns {string} - Bootstrap color class
   */
  function getStatusColor(status) {
    switch (status) {
      case "approved":
        return "success";
      case "rejected":
        return "danger";
      case "pending":
        return "warning";
      default:
        return "secondary";
    }
  }

  /**
   * Submit the signoff form
   * @param {Event} e - Form submission event
   */
  function submitSignoff(e) {
    e.preventDefault();

    // Validate form
    if (!currentStudent) {
      showAlert("Please select a student first", "warning");
      return;
    }

    if (!partIdInput.value) {
      showAlert("Please select a part to grade", "warning");
      return;
    }

    // Show loading indicator
    showSpinner();

    // Get form data
    const formData = new FormData(signoffForm);

    // AJAX call to submit signoff
    fetch("/api/quick-signoff/", {
      method: "POST",
      body: formData,
      headers: {
        "X-CSRFToken": getCsrfToken(),
      },
    })
      .then((response) => response.json())
      .then((data) => {
        hideSpinner();

        if (data.success) {
          // Show success modal
          successModal.show();

          // Update part status badge
          const statusBadge = document.getElementById(
            `status-${partIdInput.value}`
          );
          if (statusBadge) {
            const status =
              data.status ||
              getStatusFromOverallScore(formData.get("overall_score"));
            statusBadge.className = `status-badge ${status}`;
            statusBadge.textContent =
              status.charAt(0).toUpperCase() + status.slice(1);
          }
        } else {
          showAlert(data.message || "Error submitting signoff", "danger");
        }
      })
      .catch((error) => {
        hideSpinner();
        console.error("Error:", error);
        showAlert("Error submitting signoff", "danger");
      });
  }

  /**
   * Get status based on overall score
   * @param {string} score - Overall score value
   * @returns {string} - Status value
   */
  function getStatusFromOverallScore(score) {
    const scoreNum = parseInt(score);
    if (scoreNum <= 1) return "rejected";
    return "approved";
  }

  /**
   * Reset the form inputs
   */
  function resetFormInputs() {
    // Reset comments
    document.getElementById("comments").value = "";

    // Reset overall score to "Meets Requirements"
    document.querySelector(
      'input[name="overall_score"][value="2"]'
    ).checked = true;

    // Reset all criteria to "Meets Requirements"
    criteriaContainer.querySelectorAll('input[value="2"]').forEach((radio) => {
      radio.checked = true;
    });
    
    // Reset evaluation sheet fields
    
    // Reset all evaluation status dropdowns to "Meets Requirements"
    criteriaContainer.querySelectorAll('select[name^="eval_"]').forEach((select) => {
      select.value = "MR";  // Meets Requirements
    });
    
    // Reset max marks to their default values
    const defaultMaxMarks = {
      "eval_cleanliness_max": 5.0,
      "eval_hardware_max": 10.0,
      "eval_timeliness_max": 5.0,
      "eval_student_preparation_max": 10.0,
      "eval_code_implementation_max": 15.0,
      "eval_commenting_max": 5.0,
      "eval_schematic_max": 10.0,
      "eval_course_participation_max": 5.0
    };
    
    Object.entries(defaultMaxMarks).forEach(([inputName, defaultValue]) => {
      const input = criteriaContainer.querySelector(`input[name="${inputName}"]`);
      if (input) {
        input.value = defaultValue;
      }
    });
  }

  /**
   * Reset the entire form
   */
  function resetForm() {
    resetFormInputs();

    // Reset the criteria container and hide the grading form
    criteriaContainer.innerHTML = "";
    gradingForm.style.display = "none";
    initialMessage.style.display = "block";
    historyCard.style.display = "none";

    // Reset part selection
    document.querySelectorAll(".part-item").forEach((el) => {
      el.classList.remove("active");
    });

    // Clear the part ID
    partIdInput.value = "";
  }

  /**
   * Start a new signoff (after submitting one)
   */
  function newSignoff() {
    successModal.hide();
    resetForm();

    // Clear student selection too
    if (studentNameInput) {
      studentNameInput.value = "";
    }
    studentInfo.style.display = "none";
    currentStudent = null;
  }

  /**
   * Print the current signoff form
   */
  function printSignoff() {
    window.print();
  }

  /**
   * Show an alert message
   * @param {string} message - Alert message
   * @param {string} type - Alert type (success, info, warning, danger)
   */
  function showAlert(message, type = "info") {
    const alertDiv = document.createElement("div");
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;

    // Insert alert at the top of the content area
    const mainContent = document.querySelector("main");
    mainContent.insertBefore(alertDiv, mainContent.firstChild);

    // Auto-dismiss after 5 seconds
    setTimeout(() => {
      if (alertDiv.parentNode) {
        const bsAlert = new bootstrap.Alert(alertDiv);
        bsAlert.close();
      }
    }, 5000);
  }

  /**
   * Show loading spinner
   */
  function showSpinner() {
    // Check if spinner already exists
    if (document.querySelector(".spinner-overlay")) return;

    const spinner = document.createElement("div");
    spinner.className = "spinner-overlay";
    spinner.innerHTML = `
            <div class="spinner-container">
                <div class="spinner-border text-primary" role="status"></div>
                <p class="mt-2 mb-0">Loading...</p>
            </div>
        `;

    document.body.appendChild(spinner);
  }

  /**
   * Hide loading spinner
   */
  function hideSpinner() {
    const spinner = document.querySelector(".spinner-overlay");
    if (spinner) {
      spinner.remove();
    }
  }

  /**
   * Get CSRF token from cookies
   * @returns {string} - CSRF token
   */
  function getCsrfToken() {
    const cookieValue = document.cookie
      .split("; ")
      .find((row) => row.startsWith("csrftoken="))
      ?.split("=")[1];

    return cookieValue || "";
  }
});
