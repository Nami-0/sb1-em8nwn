function debugLog(message, data = null) {
    console.debug(`[Travel Buddy Debug] ${message}`, data || "");
}

function updateSubmitButton(isValid) {
    const submitButton = document.querySelector('button[type="submit"]');
    if (submitButton) {
        if (!isValid) {
            submitButton.setAttribute("disabled", "");
            submitButton.classList.add("disabled");
        } else {
            submitButton.removeAttribute("disabled");
            submitButton.classList.remove("disabled");
        }
    }
}

let toastContainer = null;
let debounceTimeout = null;
let lastToastMessage = null;
let lastToastTime = 0;

function initializeToastSystem() {
    debugLog("Initializing toast system");
    const toastQueue = [];
    let isProcessingToast = false;

    function processToastQueue() {
        if (isProcessingToast || toastQueue.length === 0) {
            debugLog("Skip processing toast queue", {
                isProcessing: isProcessingToast,
                queueLength: toastQueue.length,
            });
            return;
        }

        isProcessingToast = true;
        const { title, message, type } = toastQueue.shift();

        debugLog("Processing toast:", {
            title,
            type,
            queueRemaining: toastQueue.length,
        });
        createAndShowToast(title, message, type);
    }

    function initializeToastContainer() {
        debugLog("Initializing toast container");
        toastContainer = document.querySelector(".toast-container");
        if (!toastContainer) {
            debugLog("Creating new toast container");
            toastContainer = document.createElement("div");
            toastContainer.className =
                "toast-container position-fixed bottom-0 end-0 p-3";
            document.body.appendChild(toastContainer);
        }
        return toastContainer;
    }

    function getIconForType(type) {
        const icons = {
            success: "fa-check-circle",
            error: "fa-exclamation-circle",
            warning: "fa-exclamation-triangle",
            info: "fa-info-circle",
        };
        return icons[type] || icons.info;
    }

    function createAndShowToast(title, message, type = "info") {
        if (!toastContainer) {
            toastContainer = initializeToastContainer();
        }

        const existingToasts = toastContainer.querySelectorAll(".toast");
        const zIndex = 1050 + existingToasts.length;
        const bottomOffset = existingToasts.length * 10;

        const toastElement = document.createElement("div");
        toastElement.className = `toast ${type} align-items-center border-0`;
        toastElement.setAttribute("role", "alert");
        toastElement.setAttribute("aria-live", "assertive");
        toastElement.setAttribute("aria-atomic", "true");
        toastElement.style.zIndex = zIndex;
        toastElement.style.marginBottom = `${bottomOffset}px`;

        const toastContent = `
            <div class="toast-header bg-${type} text-white">
                <i class="fas ${getIconForType(type)} me-2"></i>
                <strong class="me-auto">${title}</strong>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
            <div class="toast-body">
                ${message}
            </div>
        `;

        toastElement.innerHTML = toastContent;
        toastContainer.appendChild(toastElement);

        const toast = new bootstrap.Toast(toastElement, {
            autohide: true,
            delay: type === "error" ? 8000 : 5000,
        });

        toast.show();

        toastElement.addEventListener("hidden.bs.toast", () => {
            toastElement.remove();
            const remainingToasts = toastContainer.querySelectorAll(".toast");
            remainingToasts.forEach((t, index) => {
                t.style.marginBottom = `${index * 10}px`;
                t.style.zIndex = 1050 + index;
            });
            isProcessingToast = false;
            processToastQueue();
        });
    }

    return {
        addToast: function (title, message, type = "info") {
            const now = Date.now();
            const messageKey = `${title}-${message}-${type}`;

            if (messageKey === lastToastMessage && now - lastToastTime < 500) {
                debugLog("Skipping duplicate toast message");
                return;
            }

            lastToastMessage = messageKey;
            lastToastTime = now;

            toastQueue.push({ title, message, type });
            processToastQueue();
        },
    };
}

const toastSystem = initializeToastSystem();

function showToast(title, message, type = "info") {
    if (debounceTimeout) {
        clearTimeout(debounceTimeout);
    }

    debounceTimeout = setTimeout(() => {
        toastSystem.addToast(title, message, type);
        debounceTimeout = null;
    }, 250);
}

function validateItineraryLimits() {
    const form = document.getElementById("itineraryForm");
    if (!form) return true;

    const startDate = new Date(form.querySelector("#start_date").value);
    const endDate = new Date(form.querySelector("#end_date").value);
    const duration =
        Math.ceil((endDate - startDate) / (1000 * 60 * 60 * 24)) + 1;

    const numAdults = parseInt(form.querySelector("#num_adults").value || 0);
    const numYouth = parseInt(form.querySelector("#num_youth").value || 0);
    const numChildren = parseInt(
        form.querySelector("#num_children").value || 0,
    );
    const numInfants = parseInt(form.querySelector("#num_infants").value || 0);

    const totalTravelers = numAdults + numYouth + numChildren;

    // Get user limits from data attributes
    const maxDuration = parseInt(form.dataset.maxDuration);
    const maxTravelers = parseInt(form.dataset.maxTravelers);
    const maxInfants = parseInt(form.dataset.maxInfants);

    let isValid = true;
    const errors = [];

    // Check duration
    if (duration > maxDuration) {
        errors.push(
            `Your current plan allows trips up to ${maxDuration} days only.`,
        );
        isValid = false;
    }

    // Check travelers
    if (totalTravelers > maxTravelers) {
        errors.push(
            `Your current plan allows maximum ${maxTravelers} travelers.`,
        );
        isValid = false;
    }

    // Check infants
    if (numInfants > maxInfants) {
        errors.push(`Your current plan allows maximum ${maxInfants} infants.`);
        isValid = false;
    }

    // Display errors if any
    errors.forEach((error) => {
        showToast("Limit Exceeded", error, "warning");
    });

    return isValid;
}

function validateAndAdjustDates() {
    debugLog("Validating dates");
    const startDateInput = document.getElementById("start_date");
    const endDateInput = document.getElementById("end_date");
    if (!startDateInput || !endDateInput) {
        debugLog("Date inputs not found");
        updateSubmitButton(false);
        return;
    }

    const startDate = new Date(startDateInput.value);
    const endDate = new Date(endDateInput.value);
    if (isNaN(startDate.getTime()) || isNaN(endDate.getTime())) {
        debugLog("Invalid date values");
        updateSubmitButton(false);
        return;
    }

    const today = new Date();
    today.setHours(0, 0, 0, 0);

    // Check for past dates
    if (startDate < today) {
        showToast(
            "Invalid Date",
            "Start date cannot be in the past. Please select a future date.",
            "error",
        );
        startDateInput.value = today.toISOString().split("T")[0];
        endDateInput.value = ""; // Clear end date to force reselection
        updateSubmitButton(false);
        return;
    }

    // Check if end date is before start date
    if (endDate < startDate) {
        showToast(
            "Invalid Date Range",
            "End date cannot be before start date. Please select a valid date range.",
            "error",
        );
        endDateInput.value = startDateInput.value;
        updateSubmitButton(false);
        return;
    }

    const duration =
        Math.ceil((endDate - startDate) / (1000 * 60 * 60 * 24)) + 1;
    const form = document.getElementById("itineraryForm");
    const maxDuration = parseInt(form.dataset.maxDuration);

    if (duration > maxDuration) {
        const newEndDate = new Date(startDate);
        newEndDate.setDate(startDate.getDate() + maxDuration - 1);
        endDateInput.value = newEndDate.toISOString().split("T")[0];

        showToast(
            "Trip Duration",
            `Your current plan allows trips up to ${maxDuration} days. The end date has been adjusted automatically.`,
            "warning",
        );
    }

    updateBudgetDisplay();
    updateSubmitButton(true);
}

let travelerValidationTimeout = null;
let lastTravelerValidation = null;

function validateTravelerCounts() {
    if (travelerValidationTimeout) {
        clearTimeout(travelerValidationTimeout);
    }

    travelerValidationTimeout = setTimeout(() => {
        debugLog("Validating traveler counts");
        const form = document.getElementById("itineraryForm");
        if (!form) return;

        const inputs = {
            adults: form.querySelector("#num_adults"),
            youth: form.querySelector("#num_youth"),
            children: form.querySelector("#num_children"),
            infants: form.querySelector("#num_infants"),
        };

        if (!Object.values(inputs).every((input) => input)) {
            debugLog("Missing traveler input fields");
            return;
        }

        const counts = {
            adults: parseInt(inputs.adults.value || 0),
            youth: parseInt(inputs.youth.value || 0),
            children: parseInt(inputs.children.value || 0),
            infants: parseInt(inputs.infants.value || 0),
        };

        const maxTravelers = parseInt(form.dataset.maxTravelers);
        const maxInfants = parseInt(form.dataset.maxInfants);
        const totalTravelersExcludingInfants =
            counts.adults + counts.youth + counts.children;

        debugLog("Traveler validation:", {
            ...counts,
            totalExcludingInfants: totalTravelersExcludingInfants,
            maxTravelers: maxTravelers,
            maxInfants: maxInfants,
        });

        let isValid = true;
        let hasChanges = false;
        const validationMessages = [];

        if (totalTravelersExcludingInfants > maxTravelers) {
            const excess = totalTravelersExcludingInfants - maxTravelers;

            if (counts.youth > 0) {
                const youthReduction = Math.min(counts.youth, excess);
                counts.youth -= youthReduction;
                inputs.youth.value = counts.youth;
                hasChanges = true;
            }

            const remainingExcess =
                totalTravelersExcludingInfants - counts.youth - maxTravelers;
            if (remainingExcess > 0 && counts.children > 0) {
                const childrenReduction = Math.min(
                    counts.children,
                    remainingExcess,
                );
                counts.children -= childrenReduction;
                inputs.children.value = counts.children;
                hasChanges = true;
            }

            if (
                (counts.children > 0 || counts.infants > 0) &&
                counts.adults < 1
            ) {
                counts.adults = 1;
                inputs.adults.value = 1;
                hasChanges = true;
                validationMessages.push({
                    title: "Adult Required",
                    message:
                        "At least one adult is required when traveling with children or infants.",
                    type: "warning",
                });
            }

            validationMessages.push({
                title: "Traveler Limit Exceeded",
                message: `Your current plan allows a maximum of ${maxTravelers} travelers. Numbers have been adjusted automatically.`,
                type: "warning",
            });
            isValid = false;
        }

        if (counts.infants > maxInfants) {
            inputs.infants.value = maxInfants;
            hasChanges = true;
            validationMessages.push({
                title: "Infant Limit Reached",
                message: `Your current plan allows a maximum of ${maxInfants} infants.`,
                type: "warning",
            });
            isValid = false;
        }

        const validationKey = JSON.stringify(validationMessages);
        if (validationKey !== lastTravelerValidation) {
            lastTravelerValidation = validationKey;
            validationMessages.forEach((msg) => {
                showToast(msg.title, msg.message, msg.type);
            });
        }

        if (hasChanges) {
            updateBudgetDisplay();
        }

        updateSubmitButton(isValid);
        return isValid;
    }, 250);
}

function updateBudgetDisplay() {
    debugLog("Updating budget display");
    const form = document.getElementById("itineraryForm");
    if (!form) {
        debugLog("Budget form not found");
        return;
    }

    const formElements = {
        budget: form.querySelector("#budget"),
        destination: form.querySelector("#destinations"),
        startDate: form.querySelector("#start_date"),
        endDate: form.querySelector("#end_date"),
        numAdults: form.querySelector("#num_adults"),
        numYouth: form.querySelector("#num_youth"),
        numChildren: form.querySelector("#num_children"),
        numInfants: form.querySelector("#num_infants"),
        includeFlights: form.querySelector("#include_flights"),
        includeAccommodation: form.querySelector("#include_accommodation"),
    };

    if (!Object.values(formElements).every((element) => element)) {
        debugLog("Missing form elements");
        return;
    }

    const budget = parseFloat(formElements.budget.value);
    if (isNaN(budget)) {
        updateSubmitButton(false);
        return;
    }

    // Calculate budget breakdown
    const budgetBreakdown = document.getElementById("budgetBreakdown");
    const budgetDetails = document.getElementById("budgetDetails");
    if (budgetBreakdown && budgetDetails) {
        const totalTravelers =
            parseInt(formElements.numAdults.value || 0) +
            parseInt(formElements.numYouth.value || 0) +
            parseInt(formElements.numChildren.value || 0);
        const numInfants = parseInt(formElements.numInfants.value || 0);
        const startDate = new Date(formElements.startDate.value);
        const endDate = new Date(formElements.endDate.value);
        const duration =
            Math.ceil((endDate - startDate) / (1000 * 60 * 60 * 24)) + 1;

        if (!isNaN(duration) && !isNaN(totalTravelers)) {
            budgetBreakdown.style.display = "block";
            let breakdownHtml = `
                <p><strong>Daily Budget per Person:</strong> MYR ${(budget / (duration * totalTravelers)).toLocaleString()}</p>
                <p><strong>Estimated Breakdown:</strong></p>
                <ul class="mb-0">
            `;

            if (formElements.includeFlights.checked) {
                const flightCost = totalTravelers * 2000 + numInfants * 300;
                const flightPercentage = Math.round(
                    (flightCost / budget) * 100,
                );
                breakdownHtml += `<li>Flights: MYR ${flightCost.toLocaleString()} (${flightPercentage}%)</li>`;
            }

            if (formElements.includeAccommodation.checked) {
                const accommodationCost = duration * 400;
                const accommodationPercentage = Math.round(
                    (accommodationCost / budget) * 100,
                );
                breakdownHtml += `<li>Accommodation: MYR ${accommodationCost.toLocaleString()} (${accommodationPercentage}%)</li>`;
            }

            const dailyExpenses = duration * totalTravelers * 200;
            const dailyPercentage = Math.round((dailyExpenses / budget) * 100);
            breakdownHtml += `<li>Daily Expenses: MYR ${dailyExpenses.toLocaleString()} (${dailyPercentage}%)</li>`;

            breakdownHtml += "</ul>";
            budgetDetails.innerHTML = breakdownHtml;
        }
    }
}

function initializeItineraryForm() {
    debugLog("Initializing itinerary form");
    try {
        const form = document.getElementById("itineraryForm");
        if (!form) {
            debugLog("Itinerary form not found");
            return;
        }

        // Initialize form with validation
        form.addEventListener("submit", function (e) {
            if (!validateItineraryLimits()) {
                e.preventDefault();
                return false;
            }
        });

        // Set up event listeners
        const dateInputs = ["start_date", "end_date"];
        dateInputs.forEach((inputId) => {
            const input = form.querySelector(`#${inputId}`);
            if (input) {
                input.addEventListener("change", validateAndAdjustDates);
            }
        });

        const travelerInputs = [
            "num_adults",
            "num_youth",
            "num_children",
            "num_infants",
        ];
        travelerInputs.forEach((inputId) => {
            const input = form.querySelector(`#${inputId}`);
            if (input) {
                input.addEventListener("change", validateTravelerCounts);
            }
        });

        const budgetInputs = [
            "budget",
            "include_flights",
            "include_accommodation",
        ];
        budgetInputs.forEach((inputId) => {
            const input = form.querySelector(`#${inputId}`);
            if (input) {
                input.addEventListener("change", updateBudgetDisplay);
            }
        });

        // Initial validation
        validateAndAdjustDates();
        validateTravelerCounts();
        updateBudgetDisplay();

        // Add inside initializeItineraryForm function after existing initializations
        handleTravelFocusSelection();

        const destinationSelect = form.querySelector("#destinations");
        const landmarksInput = form.querySelector("#specific_locations");
        if (destinationSelect && landmarksInput) {
            destinationSelect.addEventListener("change", validateLandmarks);
            landmarksInput.addEventListener(
                "input",
                debounce(validateLandmarks, 500),
            );
        }

        debugLog("Itinerary form initialized successfully");
    } catch (error) {
        console.error("Error initializing itinerary form:", error);
    }
}

function validateLandmarks() {
    debugLog("Validating landmarks");
    const destinationSelect = document.getElementById("destinations");
    const landmarksInput = document.getElementById("specific_locations");
    const landmarksError = document.getElementById("landmarks-error");
    const landmarksSuggestions = document.getElementById(
        "landmarks-suggestions",
    );

    if (
        !destinationSelect ||
        !landmarksInput ||
        !landmarksError ||
        !landmarksSuggestions
    ) {
        debugLog("Landmark validation elements not found");
        return;
    }

    const destination = destinationSelect.value;
    const landmarks = landmarksInput.value
        .toLowerCase()
        .split(",")
        .map((l) => l.trim())
        .filter((l) => l);

    if (destination === "surprise_me" || !landmarks.length) {
        landmarksInput.classList.remove("is-invalid");
        landmarksError.style.display = "none";
        landmarksSuggestions.style.display = "none";
        updateSubmitButton(true);
        return;
    }

    const validLandmarks = VALID_LANDMARKS[destination] || [];
    const invalidLandmarks = landmarks.filter(
        (l) => l && !validLandmarks.includes(l),
    );

    if (invalidLandmarks.length > 0) {
        landmarksInput.classList.add("is-invalid");
        landmarksError.style.display = "block";
        landmarksError.textContent = `Invalid landmarks for ${destination.replace("_", " ")}: ${invalidLandmarks.join(", ")}`;

        const suggestions = validLandmarks.slice(0, 5);
        landmarksSuggestions.style.display = "block";
        landmarksSuggestions.innerHTML = `
            <span>Popular landmarks in ${destination.replace("_", " ")}: ${suggestions.join(", ")}</span>
        `;
        updateSubmitButton(false);
    } else {
        landmarksInput.classList.remove("is-invalid");
        landmarksError.style.display = "none";
        landmarksSuggestions.style.display = "none";
        updateSubmitButton(true);
    }
}

function handleTravelFocusSelection() {
    const selectAllButton = document.getElementById("selectAllTravelFocus");
    const travelFocusCheckboxes = document.querySelectorAll(
        'input[name="travel_focus"]',
    );

    if (selectAllButton && travelFocusCheckboxes.length > 0) {
        selectAllButton.addEventListener("click", () => {
            const allChecked = Array.from(travelFocusCheckboxes).every(
                (cb) => cb.checked,
            );
            travelFocusCheckboxes.forEach((cb) => (cb.checked = !allChecked));
            validateForm();
        });

        // Add validation for minimum selection
        travelFocusCheckboxes.forEach((checkbox) => {
            checkbox.addEventListener("change", () => {
                const checkedCount = Array.from(travelFocusCheckboxes).filter(
                    (cb) => cb.checked,
                ).length;

                if (checkedCount === 0) {
                    showToast(
                        "Travel Focus Required",
                        "Please select at least one travel focus.",
                        "warning",
                    );
                    updateSubmitButton(false);
                } else {
                    updateSubmitButton(true);
                }
            });
        });
    }
}

function validateForm() {
    const isLandmarksValid = validateLandmarks();
    const isTravelersValid = validateTravelerCounts();
    const isDatesValid = validateDateRange();
    const isBudgetValid = validateBudget();

    updateSubmitButton(
        isLandmarksValid && isTravelersValid && isDatesValid && isBudgetValid,
    );
}

function validateDateRange() {
    const startDate = document.getElementById("start_date");
    const endDate = document.getElementById("end_date");

    if (!startDate || !endDate) return true;

    const start = new Date(startDate.value);
    const end = new Date(endDate.value);

    if (isNaN(start.getTime()) || isNaN(end.getTime())) {
        return false;
    }

    if (end < start) {
        showToast(
            "Invalid Date Range",
            "End date must be after start date.",
            "error",
        );
        return false;
    }

    return true;
}

function validateBudget() {
    const budgetInput = document.getElementById("budget");
    if (!budgetInput) return true;

    const budget = parseFloat(budgetInput.value);
    if (isNaN(budget) || budget <= 0) {
        showToast(
            "Invalid Budget",
            "Please enter a valid budget amount.",
            "error",
        );
        return false;
    }

    return true;
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Initialize when document is ready
document.addEventListener("DOMContentLoaded", () => {
    debugLog("DOM content loaded, initializing application...");
    initializeToastSystem();
    debugLog("Toast system initialized");
    if (document.getElementById("itineraryForm")) {
        debugLog("Detected itinerary form page");
        initializeItineraryForm();
    }
});
