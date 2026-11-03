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

  function setPaymentAmount(amountRupees) {
    const payButton = document.getElementById("pay-button");
    const paymentCopy = document.getElementById("payment-copy");
    const bookingAmount = document.getElementById("booking-amount");
    const amount = Number(amountRupees) || 499;
    const label = amount === 1 ? "Pay ₹1" : `Pay ₹${amount}`;
    if (payButton) payButton.textContent = label;
    if (paymentCopy) paymentCopy.textContent = `Complete the payment in the new tab. This page will automatically confirm your payment.`;
    if (bookingAmount) bookingAmount.textContent = amount === 1 ? "Your ₹1 test payment has been received." : `Your ₹${amount} commitment has been received.`;
  }

  async function pollPayment(interestId) {
    const bookingStep = document.getElementById("booking-step");
    const paymentStep = document.getElementById("payment-step");
    const wait = document.getElementById("payment-wait");
    const confirming = document.getElementById("payment-confirming");
    const error = document.getElementById("payment-error");
    let attempts = 0;
    const maxAttempts = 200;

    while (attempts++ < maxAttempts) {
      try {
        const response = await fetch(`/transformation-interest/payment-status?interest_id=${encodeURIComponent(interestId)}`, {
          cache: "no-store",
        });
        if (response.ok) {
          const data = await response.json();
          if (data.paid) {
            if (paymentStep) paymentStep.classList.add("hidden");
            if (wait) wait.classList.add("hidden");
            if (confirming) confirming.classList.add("hidden");
            if (error) error.classList.add("hidden");
            if (bookingStep) bookingStep.classList.remove("hidden");
            startBookingWatch(interestId);
            return;
          }
        }
      } catch (_) {}

      await new Promise((resolve) => setTimeout(resolve, 3000));
    }

    if (confirming) confirming.classList.add("hidden");
    if (error) {
      error.textContent = "Payment is taking longer than usual to confirm. Please wait a moment and refresh this page if needed.";
      error.classList.remove("hidden");
    }
  }

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

    const confirming = document.getElementById("booking-confirming");
    if (confirming) confirming.classList.remove("hidden");

    if (bookingWatchRunning) {
      await checkBookingOnce(bookingWatchInterestId);
      return;
    }

    bookingWatchRunning = true;
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

  async function restoreInterestState() {
    const storedInterestId = sessionStorage.getItem("transformation_interest_id");
    if (!storedInterestId) return;

    const storedName = sessionStorage.getItem("transformation_interest_name") || "there";
    try {
      const response = await fetch(`/transformation-interest/payment-status?interest_id=${encodeURIComponent(storedInterestId)}`, { cache: "no-store" });
      if (!response.ok) return;
      const data = await response.json();
      if (!data.paid) return;

      form.classList.add("hidden");
      if (success) success.classList.remove("hidden");
      if (successName) successName.textContent = storedName;

      const paymentStep = document.getElementById("payment-step");
      const bookingStep = document.getElementById("booking-step");
      if (paymentStep) paymentStep.classList.add("hidden");
      if (bookingStep) bookingStep.classList.remove("hidden");
      setPaymentAmount(data.amount_rupees || 499);

      startBookingWatch(storedInterestId);
    } catch (_) {}
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

      const paymentResponse = await fetch(`/transformation-interest/payment-link?interest_id=${encodeURIComponent(interestId)}`, {
        method: "POST",
      });
      const paymentData = await paymentResponse.json();
      if (!paymentResponse.ok || !paymentData.payment_url) {
        throw new Error(paymentData.detail || "We couldn't prepare the payment. Please try again.");
      }

      form.classList.add("hidden");
      if (success) success.classList.remove("hidden");
      if (successName) successName.textContent = payload.name || "there";

      setPaymentAmount(paymentData.amount_rupees);

      const bookingButton = document.getElementById("clarity-booking-button");
      if (bookingButton) {
        try {
          const bookingUrl = new URL(bookingButton.href);
          bookingUrl.searchParams.set("name", payload.name);
          bookingUrl.searchParams.set("full_name", payload.name);
          bookingUrl.searchParams.set("phone", payload.phone);
          bookingButton.href = bookingUrl.toString();
        } catch (_) {}
        bookingButton.addEventListener("click", () => startBookingWatch(interestId));
      }

      const payButton = document.getElementById("pay-button");
      if (payButton) {
        payButton.href = paymentData.payment_url;
        payButton.addEventListener("click", () => {
          const wait = document.getElementById("payment-wait");
          if (wait) wait.classList.add("hidden");
          const confirming = document.getElementById("payment-confirming");
          if (confirming) confirming.classList.remove("hidden");
          pollPayment(interestId);
        }, { once: true });
      }
      success?.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (error) {
      console.error("Transformation interest submission failed:", error);
      alert(error.message || "We couldn't send your enquiry. Please try again.");
      submit.disabled = false;
      submit.textContent = "I'd like to explore NourisHer →";
    }
  });

  restoreInterestState();
})();
