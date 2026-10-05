(() => {
  "use strict";

  const initialiseInterestPrefill = async () => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get("interest_token");

    if (!token) return;

    const setValue = (id, value) => {
      const field = document.getElementById(id);

      if (
        field &&
        value !== undefined &&
        value !== null &&
        value !== ""
      ) {
        field.value = value;
        field.dispatchEvent(new Event("input", { bubbles: true }));
        field.dispatchEvent(new Event("change", { bubbles: true }));
      }
    };

    const checkValues = (name, values) => {
      if (!Array.isArray(values)) return;

      document
        .querySelectorAll(`input[name="${name}"]`)
        .forEach((input) => {
          input.checked = values.includes(input.value);

          if (input.checked) {
            input.dispatchEvent(
              new Event("change", { bubbles: true })
            );
          }
        });
    };

    try {
      const response = await fetch(
        `/transformation-interest/application-prefill?token=${encodeURIComponent(token)}`,
        {
          credentials: "same-origin",
          cache: "no-store",
        }
      );

      if (!response.ok) {
        throw new Error(
          `Prefill request failed (${response.status})`
        );
      }

      const data = await response.json();

      // The secure interest token is authoritative.
      // Existing localStorage data may belong to an older
      // assessment/test and must not overwrite this enquiry.
      setValue("name", data.name);
      setValue("occupation", data.occupation);
      setValue("why-now", data.why_now);

      const phone = document.getElementById("phone");

      if (phone && data.phone) {
        const iti =
          window.intlTelInputGlobals?.getInstance(phone);

        if (iti) {
          iti.setNumber(data.phone);
        } else {
          phone.value = data.phone;
        }

        phone.dispatchEvent(
          new Event("input", { bubbles: true })
        );
        phone.dispatchEvent(
          new Event("change", { bubbles: true })
        );
      }

      const priorityMap = {
        "Lose weight and reduce belly fat":
          "Sustainable fat loss",
        "Feel better through perimenopause / menopause":
          "Hormonal wellbeing",
        "Improve eating habits without dieting":
          "Confidence and consistency",
        "Get stronger and feel fitter":
          "Strength and fitness",
        "Improve energy, sleep and wellbeing":
          ["Better energy", "Better sleep"],
        "Feel confident and comfortable in my body":
          "Confidence and consistency",
      };

      const mapped = [];

      (data.goals || []).forEach((goal) => {
        const value = priorityMap[goal];

        if (Array.isArray(value)) {
          mapped.push(...value);
        } else if (value) {
          mapped.push(value);
        }
      });

      checkValues(
        "priorities",
        [...new Set(mapped)].slice(0, 3)
      );

      const hiddenToken =
        document.getElementById("interest-token");

      if (hiddenToken) {
        hiddenToken.value = token;
      }

      const hiddenInterest =
        document.getElementById("interest-id");

      if (hiddenInterest) {
        hiddenInterest.value = data.interest_id || "";
      }

      // Keep current lead storage aligned with this enquiry.
      // This prevents later application code from restoring
      // the previous test person's name or phone.
      try {
        const existing = JSON.parse(
          localStorage.getItem("nourisherLead") || "{}"
        );

        localStorage.setItem(
          "nourisherLead",
          JSON.stringify({
            ...existing,
            name: data.name || existing.name || "",
            phone: data.phone || existing.phone || "",
            interestId:
              data.interest_id ||
              existing.interestId ||
              null,
            snapshotId:
              data.snapshot_id ||
              existing.snapshotId ||
              null,
          })
        );
      } catch (storageError) {
        console.warn(
          "Could not update saved lead data:",
          storageError
        );
      }
    } catch (error) {
      console.error(
        "Transformation application prefill failed:",
        error
      );
    }
  };

  // Wait until the DOM is ready. funnel.js initializes the
  // existing seven-step application first; this script then
  // applies the authoritative interest data.
  if (document.readyState === "loading") {
    document.addEventListener(
      "DOMContentLoaded",
      initialiseInterestPrefill,
      { once: true }
    );
  } else {
    initialiseInterestPrefill();
  }
})();
