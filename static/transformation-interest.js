(() => {
  const form = document.getElementById("transformation-interest");
  const success = document.getElementById("interest-success");
  const successName = document.getElementById("success-name");
  const hero = document.getElementById("interest-hero");
  if (!form) return;

  const params = new URLSearchParams(window.location.search);
  const source = params.get("source") || params.get("utm_source") || "direct";
  const querySnapshotId = params.get("snapshot_id");

  // Assessment data is already captured before a woman reaches this page.
  // Reuse it so she doesn't have to type her name and WhatsApp number again.
  let savedLead = {};
  try {
    savedLead = JSON.parse(localStorage.getItem("nourisherLead") || "{}");
  } catch (_) {
    savedLead = {};
  }

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

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!form.checkValidity()) {
      form.reportValidity();
      return;
    }

    const snapshotId = querySnapshotId || savedLead.snapshotId || null;

    const payload = {
      name: nameField?.value.trim() || "",
      phone: phoneField?.value.trim() || "",
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

    if (!payload.goals.length) {
      alert("Please choose at least one priority.");
      return;
    }

    const submit = form.querySelector('button[type="submit"]');
    submit.disabled = true;
    submit.textContent = "Sending…";

    try {
      const response = await fetch("/transformation-interest", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload)
      });
      const data = await response.json();

      if (!response.ok || data.status !== "saved") {
        throw new Error(data.message || data.detail || "We couldn't send your enquiry. Please try again.");
      }

      successName.textContent = payload.name;
      form.classList.add("hidden");
      if (hero) hero.classList.add("hidden");
      success.classList.remove("hidden");
      window.scrollTo({top: 0, behavior: "smooth"});
    } catch (error) {
      console.error("Transformation interest submission failed:", error);
      alert(error.message || "We couldn't send your enquiry. Please try again.");
      submit.disabled = false;
      submit.textContent = "I'd like to explore NourisHer →";
    }
  });
})();
