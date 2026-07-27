const form = document.getElementById("registration-form");
const steps = [...document.querySelectorAll(".form-step")];
const stepTabs = [...document.querySelectorAll(".step-tab")];
const nextButton = document.getElementById("next-button");
const previousButton = document.getElementById("previous-button");
const submitButton = document.getElementById("submit-button");
const currentStepNumber = document.getElementById("current-step-number");
const formTitle = document.getElementById("form-title");
const progressBar = document.getElementById("progress-bar");
const formAlert = document.getElementById("form-alert");
const saveStatus = document.getElementById("save-status");
const reviewCard = document.getElementById("review-card");
const storageKey = "nourisher-registration-draft-v1";

const stepTitles = [
  "Tell us about yourself",
  "Your goals and challenges",
  "Health and lifestyle",
  "Review your registration"
];

let currentStep = 1;

function showStep(stepNumber) {
  currentStep = stepNumber;
  steps.forEach((step) => step.classList.toggle("active", Number(step.dataset.step) === stepNumber));
  stepTabs.forEach((tab, index) => {
    tab.classList.toggle("active", index + 1 === stepNumber);
    tab.classList.toggle("complete", index + 1 < stepNumber);
  });

  currentStepNumber.textContent = stepNumber;
  formTitle.textContent = stepTitles[stepNumber - 1];
  progressBar.style.width = `${stepNumber * 25}%`;
  previousButton.hidden = stepNumber === 1;
  nextButton.hidden = stepNumber === 4;
  submitButton.hidden = stepNumber !== 4;
  formAlert.textContent = "";

  if (stepNumber === 4) buildReview();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function setFieldError(field, message) {
  const wrapper = field.closest(".field");
  if (!wrapper) return;
  wrapper.classList.toggle("invalid", Boolean(message));
  const error = wrapper.querySelector(".error-message");
  if (error) error.textContent = message || "";
}

function validateCurrentStep() {
  let valid = true;
  const current = steps[currentStep - 1];

  current.querySelectorAll("input[required], select[required], textarea[required]").forEach((field) => {
    if (field.type === "radio" || field.type === "checkbox") return;

    let message = "";
    if (!field.value.trim()) {
      message = "This field is required.";
    } else if (field.type === "email" && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(field.value)) {
      message = "Enter a valid email address.";
    } else if (field.id === "phone" && field.value.replace(/\D/g, "").length < 8) {
      message = "Enter a valid WhatsApp number.";
    } else if (field.id === "age" && (Number(field.value) < 18 || Number(field.value) > 90)) {
      message = "Enter an age between 18 and 90.";
    }

    setFieldError(field, message);
    if (message) valid = false;
  });

  current.querySelectorAll("[data-required-group]").forEach((group) => {
    const name = group.dataset.requiredGroup;
    const checked = group.querySelectorAll(`input[name="${name}"]:checked`).length > 0;
    const error = group.querySelector(".group-error");
    error.textContent = checked ? "" : "Please select at least one option.";
    if (!checked) valid = false;
  });

  current.querySelectorAll(".radio-section").forEach((group) => {
    const radio = group.querySelector('input[type="radio"]');
    if (!radio || !radio.required) return;
    const checked = group.querySelector(`input[name="${radio.name}"]:checked`);
    const error = group.querySelector(".group-error");
    error.textContent = checked ? "" : "Please choose Yes or No.";
    if (!checked) valid = false;
  });

  if (currentStep === 4) {
    current.querySelectorAll('.consent-item input[required]').forEach((box) => {
      const item = box.closest(".consent-item");
      item.style.borderColor = box.checked ? "" : "#b8345b";
      if (!box.checked) valid = false;
    });
  }

  formAlert.textContent = valid ? "" : "Please complete the highlighted fields before continuing.";
  return valid;
}

function getFormDataObject() {
  const data = new FormData(form);
  const result = {};

  for (const [key, value] of data.entries()) {
    if (result[key]) {
      result[key] = Array.isArray(result[key]) ? [...result[key], value] : [result[key], value];
    } else {
      result[key] = value;
    }
  }

  result.goals = data.getAll("goals");
  result.challenges = data.getAll("challenges");
  return result;
}

function saveDraft() {
  const data = getFormDataObject();
  localStorage.setItem(storageKey, JSON.stringify(data));
  saveStatus.textContent = "Saved on this device";
}

function restoreDraft() {
  const raw = localStorage.getItem(storageKey);
  if (!raw) return;

  try {
    const data = JSON.parse(raw);
    Object.entries(data).forEach(([name, value]) => {
      const fields = [...form.elements].filter((el) => el.name === name);
      if (!fields.length) return;

      fields.forEach((field) => {
        if (field.type === "checkbox") {
          field.checked = Array.isArray(value) ? value.includes(field.value) : value === field.value || value === "on";
        } else if (field.type === "radio") {
          field.checked = field.value === value;
        } else {
          field.value = value;
        }
      });
    });

    updateConditionalFields();
    updateRange();
    updateCharacterCount();
    saveStatus.textContent = "Draft restored";
  } catch {
    localStorage.removeItem(storageKey);
  }
}

function selectedText(name) {
  return [...form.querySelectorAll(`[name="${name}"]:checked`)].map((field) => field.value).join(", ") || "Not provided";
}

function fieldValue(name) {
  const field = form.elements[name];
  if (!field) return "Not provided";
  if (field instanceof RadioNodeList) return field.value || "Not provided";
  return field.value || "Not provided";
}

function escapeHTML(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function reviewRow(title, content) {
  return `<div class="review-section"><strong>${escapeHTML(title)}</strong><p>${escapeHTML(content)}</p></div>`;
}

function buildReview() {
  reviewCard.innerHTML = [
    reviewRow("Participant", `${fieldValue("fullName")}\n${fieldValue("age")} years · ${fieldValue("city")}, ${fieldValue("country")}`),
    reviewRow("Contact", `${fieldValue("email")}\n${fieldValue("phone")}`),
    reviewRow("Goals", selectedText("goals")),
    reviewRow("Challenges", selectedText("challenges")),
    reviewRow("Readiness", `${fieldValue("readiness")}/10`),
    reviewRow("Diet & activity", `${fieldValue("diet")}\n${fieldValue("activity")}`),
    reviewRow("Health details", [
      `Conditions: ${fieldValue("hasConditions")}${fieldValue("hasConditions") === "Yes" ? ` — ${fieldValue("conditions")}` : ""}`,
      `Medication: ${fieldValue("hasMedication")}${fieldValue("hasMedication") === "Yes" ? ` — ${fieldValue("medication")}` : ""}`,
      `Restrictions: ${fieldValue("hasRestrictions")}${fieldValue("hasRestrictions") === "Yes" ? ` — ${fieldValue("restrictions")}` : ""}`
    ].join("\n"))
  ].join("");
}

function updateConditionalFields() {
  const mappings = [
    ["hasConditions", "conditions-field"],
    ["hasMedication", "medication-field"],
    ["hasRestrictions", "restrictions-field"]
  ];

  mappings.forEach(([name, id]) => {
    const selected = form.querySelector(`input[name="${name}"]:checked`);
    document.getElementById(id).classList.toggle("visible", selected?.value === "Yes");
  });
}

function updateRange() {
  const readiness = document.getElementById("readiness");
  document.getElementById("readiness-output").textContent = `${readiness.value}/10`;
}

function updateCharacterCount() {
  const textarea = document.getElementById("successMeaning");
  document.getElementById("success-count").textContent = textarea.value.length;
}

nextButton.addEventListener("click", () => {
  if (!validateCurrentStep()) return;
  saveDraft();
  showStep(Math.min(4, currentStep + 1));
});

previousButton.addEventListener("click", () => {
  saveDraft();
  showStep(Math.max(1, currentStep - 1));
});

stepTabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    const requested = Number(tab.dataset.stepTarget);
    if (requested < currentStep) {
      showStep(requested);
      return;
    }
    if (requested === currentStep + 1 && validateCurrentStep()) {
      saveDraft();
      showStep(requested);
    }
  });
});

form.addEventListener("input", (event) => {
  saveStatus.textContent = "Saving…";
  window.clearTimeout(form.saveTimer);
  form.saveTimer = window.setTimeout(saveDraft, 350);

  if (event.target.id === "readiness") updateRange();
  if (event.target.id === "successMeaning") updateCharacterCount();
  if (event.target.type === "radio") updateConditionalFields();

  if (event.target.matches("input, select, textarea")) {
    setFieldError(event.target, "");
  }
});

form.addEventListener("change", updateConditionalFields);

form.addEventListener("submit", (event) => {
  event.preventDefault();
  if (!validateCurrentStep()) return;

  const submission = {
    ...getFormDataObject(),
    submittedAt: new Date().toISOString(),
    status: "registration_completed_payment_pending"
  };

  localStorage.setItem("nourisher-last-submission", JSON.stringify(submission));
  localStorage.removeItem(storageKey);

  document.getElementById("success-name").textContent = submission.fullName?.split(" ")[0] || "there";
  document.getElementById("success-overlay").hidden = false;
  document.body.style.overflow = "hidden";

  console.log("NourisHer registration payload:", submission);
});

restoreDraft();
showStep(1);
