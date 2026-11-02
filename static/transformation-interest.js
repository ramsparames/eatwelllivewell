(() => {
  const form = document.getElementById("transformation-interest");
  const success = document.getElementById("interest-success");
  const successName = document.getElementById("success-name");
  if (!form) return;

  const params = new URLSearchParams(window.location.search);
  const source = params.get("source") || params.get("utm_source") || "direct";
  const querySnapshotId = params.get("snapshot_id");

  let savedLead = {};
  try { savedLead = JSON.parse(localStorage.getItem("nourisherLead") || "{}"); } catch (_) { savedLead = {}; }

  const nameField = form.querySelector('[name="name"]');
  const phoneField = form.querySelector('[name="phone"]');
  if (savedLead.name && nameField) nameField.value = savedLead.name;
  if (savedLead.phone && phoneField) phoneField.value = savedLead.phone;

  const goalBoxes = [...form.querySelectorAll('input[name="goals"]')];
  goalBoxes.forEach((box) => box.addEventListener("change", () => {
    if (goalBoxes.filter((item) => item.checked).length > 2) {
      box.checked = false;
      alert("Please choose up to two priorities.");
    }
  }));

  async function pollPayment(interestId) {
    const bookingStep = document.getElementById("booking-step");
    const paymentStep = document.getElementById("payment-step");
    const wait = document.getElementById("payment-wait");
    const error = document.getElementById("payment-error");
    let attempts = 0;
    const maxAttempts = 200;
    while (attempts++ < maxAttempts) {
      try {
        const response = await fetch(`/transformation-interest/payment-status?interest_id=${encodeURIComponent(interestId)}`, { cache: "no-store" });
        if (response.ok) {
          const data = await response.json();
          if (data.paid) {
            if (paymentStep) paymentStep.classList.add("hidden");
            if (wait) wait.classList.add("hidden");
            if (error) error.classList.add("hidden");
            if (bookingStep) bookingStep.classList.remove("hidden");
            return;
          }
        }
      } catch (_) {}
      await new Promise((resolve) => setTimeout(resolve, 3000));
    }
    if (wait) wait.textContent = "Payment is taking longer than usual to confirm. Please wait a moment and refresh this page if needed.";
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!form.checkValidity()) { form.reportValidity(); return; }

    const snapshotId = querySnapshotId || savedLead.snapshotId || null;
    const payload = {
      name: nameField?.value.trim() || "",
      phone: phoneField?.value.trim() || "",
      age_range: form.querySelector('[name="age_range"]:checked')?.value || "",
      occupation: form.querySelector('[name="occupation"]:checked')?.value || "",
      goals: goalBoxes.filter((item) => item.checked).map((item) => item.value),
      frustration: form.querySelector('[name="frustration"]:checked')?.value || "",
      readiness: form.querySelector('[name="readiness"]:checked')?.value || "",
      timeline: form.querySelector('[name="timeline"]:checked')?.value || "",
      why_now: form.querySelector('[name="why_now"]')?.value.trim() || "",
      source,
      snapshot_id: snapshotId ? Number(snapshotId) : null,
      website: ""
    };
    if (!payload.goals.length) { alert("Please choose at least one priority."); return; }

    const submit = form.querySelector('button[type="submit"]');
    submit.disabled = true; submit.textContent = "Sending…";

    try {
      const response = await fetch("/transformation-interest", { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify(payload) });
      const data = await response.json();
      if (!response.ok || data.status !== "saved") throw new Error(data.message || data.detail || "We couldn't send your enquiry. Please try again.");

      const interestId = data.interest_id;
      sessionStorage.setItem("transformation_interest_name", payload.name);
      sessionStorage.setItem("transformation_interest_id", String(interestId));

      const paymentResponse = await fetch(`/transformation-interest/payment-link?interest_id=${encodeURIComponent(interestId)}`, { method: "POST" });
      const paymentData = await paymentResponse.json();
      if (!paymentResponse.ok || !paymentData.payment_url) throw new Error(paymentData.detail || "We couldn't prepare the ₹499 payment. Please try again.");

      form.classList.add("hidden");
      if (success) success.classList.remove("hidden");
      if (successName) successName.textContent = payload.name || "there";

      const payButton = document.getElementById("pay-499");
      if (payButton) payButton.href = paymentData.payment_url;
      pollPayment(interestId);
      success?.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (error) {
      console.error("Transformation interest submission failed:", error);
      alert(error.message || "We couldn't send your enquiry. Please try again.");
      submit.disabled = false; submit.textContent = "I'd like to explore NourisHer →";
    }
  });
})();
