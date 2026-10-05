(() => {
  "use strict";
  const params = new URLSearchParams(window.location.search);
  const token = params.get("interest_token");
  if (!token) return;

  const setValue = (id, value) => {
    const field = document.getElementById(id);
    if (field && value) field.value = value;
  };

  const checkValues = (name, values) => {
    if (!Array.isArray(values)) return;
    document.querySelectorAll(`input[name="${name}"]`).forEach((input) => {
      input.checked = values.includes(input.value);
    });
  };

  fetch(`/transformation-interest/application-prefill?token=${encodeURIComponent(token)}`, {
    credentials: "same-origin",
  })
    .then((response) => response.ok ? response.json() : Promise.reject(new Error("prefill")))
    .then((data) => {
      setValue("name", data.name);
      setValue("occupation", data.occupation);
      setValue("why-now", data.why_now);

      const phone = document.getElementById("phone");
      if (phone && data.phone) {
        phone.value = data.phone;
        const iti = window.intlTelInputGlobals?.getInstance(phone);
        if (iti) iti.setNumber(data.phone);
      }

      const priorityMap = {
        "Lose weight and reduce belly fat": "Sustainable fat loss",
        "Feel better through perimenopause / menopause": "Hormonal wellbeing",
        "Improve eating habits without dieting": "Confidence and consistency",
        "Get stronger and feel fitter": "Strength and fitness",
        "Improve energy, sleep and wellbeing": ["Better energy", "Better sleep"],
        "Feel confident and comfortable in my body": "Confidence and consistency",
      };
      const mapped = [];
      (data.goals || []).forEach((goal) => {
        const value = priorityMap[goal];
        if (Array.isArray(value)) mapped.push(...value);
        else if (value) mapped.push(value);
      });
      checkValues("priorities", [...new Set(mapped)].slice(0, 3));

      const hiddenToken = document.getElementById("interest-token");
      if (hiddenToken) hiddenToken.value = token;
      const hiddenInterest = document.getElementById("interest-id");
      if (hiddenInterest) hiddenInterest.value = data.interest_id || "";
    })
    .catch((error) => console.error("Transformation application prefill failed:", error));
})();
