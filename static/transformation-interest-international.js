(() => {
  const form = document.getElementById("transformation-interest");
  const success = document.getElementById("interest-success");
  const successName = document.getElementById("success-name");
  if (!form) return;

  sessionStorage.removeItem("transformation_interest_id");
  sessionStorage.removeItem("transformation_interest_name");

  const params = new URLSearchParams(window.location.search);
  const adSource = params.get("source") || params.get("utm_source") || "direct";
  const source = `international:${adSource}`;
  const querySnapshotId = params.get("snapshot_id");

  let savedLead = {};
  try { savedLead = JSON.parse(localStorage.getItem("nourisherLead") || "{}"); } catch (_) { savedLead = {}; }

  const nameField = form.querySelector('[name="name"]');
  const phoneField = form.querySelector('[name="phone"]');
  const countryField = form.querySelector('[name="country"]');
  if (savedLead.name && nameField) nameField.value = savedLead.name;
  if (savedLead.phone && phoneField) phoneField.value = savedLead.phone;

  // Optional URL prefill for testing/referral links.
  // This only fills the form. It deliberately does NOT submit it.
  const prefillFields = [
    "name", "country", "phone", "age_range", "occupation",
    "goals", "frustration", "readiness", "timeline", "why_now"
  ];

  prefillFields.forEach((fieldName) => {
    const value = params.get(fieldName);
    if (!value) return;

    const fields = [...form.querySelectorAll(`[name="${fieldName}"]`)];
    if (!fields.length) return;

    if (fields[0].type === "radio" || fields[0].type === "checkbox") {
      const values = value.split(",").map((item) => item.trim());
      fields.forEach((field) => {
        field.checked = values.includes(field.value);
        if (field.checked) {
          field.dispatchEvent(new Event("change", { bubbles: true }));
        }
      });
      return;
    }

    const field = fields[0];
    field.value = value;
    field.dispatchEvent(new Event("input", { bubbles: true }));
    field.dispatchEvent(new Event("change", { bubbles: true }));
  });

  const goalBoxes = [...form.querySelectorAll('input[name="goals"]')];
  goalBoxes.forEach((box) => box.addEventListener("change", () => {
    if (goalBoxes.filter((item) => item.checked).length > 2) {
      box.checked = false;
      alert("Please choose up to two priorities.");
    }
  }));

  let bookingWatchInterestId = null;
  let bookingWatchRunning = false;

  function showBookedState() {
    const bookingButton = document.getElementById("clarity-booking-button");
    const confirming = document.getElementById("booking-confirming");
    const complete = document.getElementById("booking-complete");
    if (confirming) confirming.classList.add("hidden");
    if (bookingButton) bookingButton.classList.add("hidden");
    if (complete) complete.classList.remove("hidden");
  }

  async function checkBookingOnce(interestId) {
    try {
      const response = await fetch(`/transformation-interest/booking-status?interest_id=${encodeURIComponent(interestId)}`, { cache: "no-store" });
      if (!response.ok) return false;
      const data = await response.json();
      if (data.booked || data.qualified) {
        showBookedState();
        return true;
      }
    } catch (_) {}
    return false;
  }

  async function startBookingWatch(interestId) {
    bookingWatchInterestId = String(interestId);
    sessionStorage.setItem("transformation_interest_id", bookingWatchInterestId);
    if (bookingWatchRunning) {
      await checkBookingOnce(bookingWatchInterestId);
      return;
    }
    bookingWatchRunning = true;
    const confirming = document.getElementById("booking-confirming");
    if (confirming) confirming.classList.remove("hidden");
    let attempts = 0;
    const maxAttempts = 200;
    while (bookingWatchInterestId && attempts++ < maxAttempts) {
      if (await checkBookingOnce(bookingWatchInterestId)) {
        bookingWatchRunning = false;
        return;
      }
      await new Promise((resolve) => setTimeout(resolve, 3000));
    }
    bookingWatchRunning = false;
  }

  window.addEventListener("focus", () => {
    if (bookingWatchInterestId) checkBookingOnce(bookingWatchInterestId);
  });
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && bookingWatchInterestId) checkBookingOnce(bookingWatchInterestId);
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!form.checkValidity()) { form.reportValidity(); return; }

    const snapshotId = querySnapshotId || savedLead.snapshotId || null;
    const payload = {
      name: nameField?.value.trim() || "",
      phone: phoneField?.value.trim() || "",
      country: countryField?.value || "",
      age_range: form.querySelector('[name="age_range"]:checked')?.value || "",
      occupation: form.querySelector('[name="occupation"]:checked')?.value || "",
      goals: goalBoxes.filter((item) => item.checked).map((item) => item.value),
      frustration: form.querySelector('[name="frustration"]:checked')?.value || "",
      readiness: form.querySelector('[name="readiness"]:checked')?.value || "",
      timeline: form.querySelector('[name="timeline"]:checked')?.value || "",
      why_now: form.querySelector('[name="why_now"]')?.value.trim() || "",
      source,
      snapshot_id: snapshotId ? Number(snapshotId) : null,
      website: "",
    };
    if (!payload.goals.length) { alert("Please choose at least one priority."); return; }

    const submit = form.querySelector('button[type="submit"]');
    submit.disabled = true;
    submit.textContent = "Sending…";

    try {
      const response = await fetch("/transformation-interest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok || data.status !== "saved") {
        throw new Error(data.message || data.detail || "We couldn't send your enquiry. Please try again.");
      }

      const interestId = data.interest_id;
      sessionStorage.setItem("transformation_interest_name", payload.name);
      sessionStorage.setItem("transformation_interest_id", String(interestId));

      form.classList.add("hidden");
      if (success) success.classList.remove("hidden");
      if (successName) successName.textContent = payload.name || "there";

      const bookingButton = document.getElementById("clarity-booking-button");
      if (bookingButton) {
        try {
          const bookingUrl = new URL(bookingButton.href);
          bookingUrl.searchParams.set("name", payload.name);
          bookingUrl.searchParams.set("full_name", payload.name);
          bookingUrl.searchParams.set("phone", payload.phone);
          bookingButton.href = bookingUrl.toString();
        } catch (_) {}
        bookingButton.addEventListener("click", () => startBookingWatch(interestId), { once: true });
      }

      success?.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (error) {
      console.error("International transformation interest submission failed:", error);
      alert(error.message || "We couldn't send your enquiry. Please try again.");
      submit.disabled = false;
      submit.textContent = "I'd like to explore NourisHer →";
    }
  });
})();
