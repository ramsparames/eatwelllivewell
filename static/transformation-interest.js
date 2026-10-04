(() => {
  const form = document.getElementById("transformation-interest");
  const success = document.getElementById("interest-success");
  const successName = document.getElementById("success-name");
  if (!form) return;

  const goalBoxes = [...form.querySelectorAll('input[name="goals"]')];
  goalBoxes.forEach((box) => box.addEventListener("change", () => {
    if (goalBoxes.filter((item) => item.checked).length > 2) {
      box.checked = false;
      alert("Please choose up to two priorities.");
    }
  }));

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!form.checkValidity()) { form.reportValidity(); return; }

    const payload = {
      name: form.name.value.trim(),
      phone: form.phone.value.trim(),
      occupation: form.occupation.value,
      goals: goalBoxes.filter((item) => item.checked).map((item) => item.value),
      frustration: form.frustration.value,
      readiness: form.readiness.value,
      timeline: form.timeline.value,
      why_now: form.why_now.value.trim(),
      source: new URLSearchParams(window.location.search).get("source") || "direct",
      snapshot_id: localStorage.getItem("nourisher_snapshot_id") || null,
      website: ""
    };

    if (!payload.goals.length) { alert("Please choose at least one priority."); return; }

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
        throw new Error(data.message || "We couldn't send your enquiry. Please try again.");
      }
      successName.textContent = payload.name;
      form.classList.add("hidden");
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