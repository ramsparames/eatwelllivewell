import intlTelInput from "https://cdn.jsdelivr.net/npm/intl-tel-input@25.3.2/+esm";

(async () => {
    "use strict";

    let assessmentFormToken = "";
    if (document.querySelector("[data-snapshot-intro]")) {
        fetch("/form-token/assessment", { credentials: "same-origin" })
            .then(response => response.ok ? response.json() : Promise.reject(new Error("token")))
            .then(data => { assessmentFormToken = data.token || ""; })
            .catch(() => { assessmentFormToken = ""; });
    }

    const ASSESSMENT_KEY = "nourisherAssessment";
    const APPLICATION_KEY = "nourisherApplication";
    const LEAD_KEY = "nourisherLead";

    const labels = {
        recovery: "Recovery",
        metabolic: "Energy & Metabolic Rhythm",
        nutrition: "Nutrition & Cravings",
        behaviour: "Consistency",
        confidence: "Confidence & Self-trust",
    };

    const descriptions = {
        recovery: "How supported your sleep, morning freshness and stress load currently feel.",
        metabolic: "How steady your energy and physical wellbeing feel across the day.",
        nutrition: "How manageable and predictable your cravings currently feel.",
        behaviour: "How consistently you can follow through without repeatedly restarting.",
        confidence: "How connected, capable and in control you currently feel.",
    };

    const profiles = {
        belly: [
            "You notice the biggest changes around your belly area.",
            "This can feel especially frustrating in midlife. Your wider pattern—sleep, stress, energy, cravings and consistency—matters more than any one body area.",
        ],
        overall: [
            "You are noticing more general weight or body-composition changes.",
            "Rather than treating this as one isolated issue, your snapshot looks at the habits and recovery patterns influencing the bigger picture.",
        ],
        hips: [
            "You notice the biggest changes around your hips or thighs.",
            "Where the body changes is personal. The useful focus is sustainable nourishment, strength, recovery and metabolic health—not spot reduction.",
        ],
        off: [
            "More than one symptom may be contributing to the sense that you feel “off.”",
            "That feeling is valid. Looking at the whole picture can be more useful than chasing one symptom at a time.",
        ],
    };

    const feelingScore = {
        "not-self": 36,
        "out-control": 28,
        frustrated: 45,
        stuck: 40,
        "starting-over": 32,
    };

    const save = (key, value) => {
        localStorage.setItem(key, JSON.stringify(value));
    };

    const load = (key) => {
        try {
            return JSON.parse(localStorage.getItem(key) || "{}");
        } catch {
            return {};
        }
    };

    const scale = (value) => ({ 1: 25, 2: 50, 3: 72, 4: 92 }[Number(value)] || 50);
    const average = (values) => Math.round(values.reduce((sum, value) => sum + value, 0) / values.length);

    function calculate(answers) {
        const wake = scale(answers.wake);
        const energy = scale(answers.energy);
        const cravings = scale(answers.cravings);
        const sleep = scale(answers.sleep);
        const stress = scale(answers.stress);
        const consistency = scale(answers.consistency);
        const confidence = feelingScore[answers.feeling] || 40;

        const dimensions = {
            recovery: average([wake, sleep, stress]),
            metabolic: average([wake, energy]),
            nutrition: cravings,
            behaviour: consistency,
            confidence,
        };

        const total = Math.round(
            dimensions.recovery * 0.28 +
            dimensions.metabolic * 0.22 +
            dimensions.nutrition * 0.18 +
            dimensions.behaviour * 0.18 +
            dimensions.confidence * 0.14
        );

        const ordered = Object.entries(dimensions).sort((a, b) => a[1] - b[1]);

        return {
            answers,
            dimensions,
            total,
            opportunity: ordered[0][0],
            strength: ordered.at(-1)[0],
            bodyProfile: answers.body,
            feeling: answers.feeling,
            createdAt: new Date().toISOString(),
        };
    }

    async function sendSnapshotToBackend(answers, name, phone) {
        const response = await fetch("/snapshot", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                name,
                phone,
                answers,
                form_token: assessmentFormToken,
                website: document.getElementById("assessment-website")?.value || "",
            }),
        });

        const data = await response.json();

        if (!response.ok || data.status !== "saved") {
            throw new Error(data.detail || data.message || `Snapshot request failed (${response.status})`);
        }

        save(LEAD_KEY, {
            snapshotId: data.submission_id,
            name,
            phone,
            assessmentResult: data.result,
        });

        return data;
    }

    // Assessment intro and phone field
    const intro = document.querySelector("[data-snapshot-intro]");
    const assessment = document.querySelector("[data-snapshot-assessment]");
    const assessmentForm = document.querySelector("[data-assessment-form]");
    const startButton = document.querySelector("[data-start-snapshot]");

    let assessmentPhoneWidget = null;

    if (intro && assessment && assessmentForm && startButton) {
        const phoneInput = document.getElementById("phone");
        const nameInput = document.getElementById("name");

        if (phoneInput) {
            assessmentPhoneWidget = intlTelInput(phoneInput, {
                initialCountry: "in",
                separateDialCode: true,
                nationalMode: true,
                strictMode: true,
                loadUtils: () => import(
                    "https://cdn.jsdelivr.net/npm/intl-tel-input@25.3.2/build/js/utils.js"
                ),
            });

            phoneInput.addEventListener("input", () => {
                phoneInput.setCustomValidity("");
            });
        }

        startButton.addEventListener("click", async () => {
            if (!nameInput || !phoneInput || !assessmentPhoneWidget) {
                console.error("Assessment page elements were not found.");
                return;
            }

            if (!nameInput.checkValidity()) {
                nameInput.reportValidity();
                return;
            }

            await assessmentPhoneWidget.promise;

            if (!assessmentPhoneWidget.isValidNumber()) {
                phoneInput.setCustomValidity("Please enter a valid phone number.");
                phoneInput.reportValidity();
                return;
            }

            phoneInput.setCustomValidity("");
            intro.hidden = true;
            assessment.hidden = false;

            requestAnimationFrame(() => {
                assessment.classList.add("active");
                const header = document.querySelector(".site-header");
                const offset = (header?.offsetHeight || 78) + 16;
                const targetTop = assessment.getBoundingClientRect().top + window.scrollY - offset;
                window.scrollTo({ top: Math.max(0, targetTop), behavior: "smooth" });
            });
        });

        const questions = [...assessmentForm.querySelectorAll("[data-question]")];
        const progressFill = document.querySelector("[data-progress-fill]");
        const progressText = document.querySelector("[data-progress-text]");
        const progressPercent = document.querySelector("[data-progress-percent]");
        const backButton = document.querySelector("[data-back]");
        let current = 0;
        let submitting = false;

        const showQuestion = (index) => {
            questions.forEach((question, questionIndex) => {
                question.classList.toggle("active", index === questionIndex);
            });

            current = index;
            const progress = Math.round(((index + 1) / questions.length) * 100);

            if (progressFill) progressFill.style.width = `${progress}%`;
            if (progressText) progressText.textContent = `Question ${index + 1} of ${questions.length}`;
            if (progressPercent) progressPercent.textContent = `${progress}% complete`;
            if (backButton) backButton.disabled = index === 0;

            requestAnimationFrame(() => {
                const activeQuestion = questions[index];
                const header = document.querySelector(".site-header");
                const progressWrap = document.querySelector(".snapshot-progress-wrap");
                const offset = (header?.offsetHeight || 78) + (progressWrap?.offsetHeight || 42) + 25;
                const targetTop = activeQuestion.getBoundingClientRect().top + window.scrollY - offset;
                window.scrollTo({ top: Math.max(0, targetTop), behavior: "smooth" });
            });
        };

        questions.forEach((question, index) => {
            question.querySelectorAll("input").forEach((input) => {
                input.addEventListener("change", async () => {
                    question.querySelectorAll("label").forEach((label) => {
                        label.classList.toggle("selected", label.contains(input) && input.checked);
                    });

                    await new Promise((resolve) => setTimeout(resolve, 260));

                    if (index < questions.length - 1) {
                        showQuestion(index + 1);
                        return;
                    }

                    if (submitting) return;
                    submitting = true;

                    try {
                        const formData = Object.fromEntries(new FormData(assessmentForm).entries());
                        const result = calculate(formData);
                        const name = nameInput?.value.trim() || "";
                        const phone = assessmentPhoneWidget?.getNumber() || "";

                        save(ASSESSMENT_KEY, result);
                        await sendSnapshotToBackend(formData, name, phone);
                        window.location.href = "/results";
                    } catch (error) {
                        console.error("Assessment submission failed:", error);
                        alert("We could not save your assessment. Please try again.");
                        submitting = false;
                    }
                });
            });
        });

        backButton?.addEventListener("click", () => {
            if (current > 0) showQuestion(current - 1);
        });

        if (questions.length) showQuestion(0);
    }

    // Results page
    const resultsPage = document.querySelector("[data-results-page]");

    if (resultsPage) {
        const result = load(ASSESSMENT_KEY);

        if (!result.total) {
            window.location.href = "/assessment";
            return;
        }

        const put = (selector, text) => {
            const element = document.querySelector(selector);
            if (element) element.textContent = text;
        };

        put("[data-total-score]", result.total);
        document.querySelector("[data-score-ring]")?.style.setProperty("--score", result.total);
        put("[data-strength-title]", labels[result.strength]);
        put("[data-strength-copy]", `At ${result.dimensions[result.strength]}/100, this is the strongest part of your current foundation.`);
        put("[data-opportunity-title]", labels[result.opportunity]);
        put("[data-opportunity-copy]", `At ${result.dimensions[result.opportunity]}/100, focused support here may create the biggest difference.`);

        const summaries = {
            recovery: ["Your body may not need more discipline. It may need better recovery.", "Sleep quality, morning freshness and stress load may be making hunger, energy and consistency harder than they need to feel."],
            metabolic: ["Steadier energy may be the key that unlocks everything else.", "When energy is unpredictable, healthy choices can feel much harder. A more supportive daily rhythm may help."],
            nutrition: ["Your cravings may be information—not a lack of willpower.", "Cravings can be shaped by meal structure, recovery, stress and daily routines. The answer is often better support, not stricter restriction."],
            behaviour: ["Consistency may matter more than finding the perfect plan.", "Starting, stopping or feeling discouraged may be creating more friction than the plan itself."],
            confidence: ["Rebuilding trust in yourself may be the most important first step.", "Emotional wellbeing and self-trust deserve a central place in your health strategy."],
        }[result.opportunity];

        put("[data-summary-title]", summaries[0]);
        put("[data-summary-copy]", summaries[1]);

        const contributors = {
            recovery: ["Sleep quality", "Morning freshness", "Daily stress load"],
            metabolic: ["Energy fluctuations", "Recovery patterns", "Changing body signals"],
            nutrition: ["Cravings", "Meal rhythm", "Stress and sleep interactions"],
            behaviour: ["Stop-start cycles", "Slow feedback", "All-or-nothing expectations"],
            confidence: ["Body trust", "Frustration", "Feeling stuck or disconnected"],
        }[result.opportunity];

        const contributorsElement = document.querySelector("[data-contributors]");
        if (contributorsElement) {
            contributorsElement.innerHTML = contributors.map((item) => `<span>✓ ${item}</span>`).join("");
        }

        const profile = profiles[result.bodyProfile];
        const profileElement = document.querySelector("[data-body-profile]");
        if (profile && profileElement) {
            profileElement.innerHTML = `<span class="result-kicker">Your body-change profile</span><h3>${profile[0]}</h3><p>${profile[1]}</p>`;
        }

        const dimensionGrid = document.querySelector("[data-dimension-grid]");
        if (dimensionGrid) {
            dimensionGrid.innerHTML = Object.entries(result.dimensions)
                .sort((a, b) => b[1] - a[1])
                .map(([key, value]) => `
                    <article class="dimension-card ${key === result.strength ? "is-strength" : ""} ${key === result.opportunity ? "is-opportunity" : ""}">
                        <div class="dimension-card-top"><h3>${labels[key]}</h3><strong>${value}</strong></div>
                        <div class="dimension-bar"><span style="width:${value}%"></span></div>
                        <p>${descriptions[key]}</p>
                        ${key === result.strength ? "<small>Strongest area</small>" : ""}
                        ${key === result.opportunity ? "<small>Biggest opportunity</small>" : ""}
                    </article>
                `)
                .join("");
        }

        const band = result.total < 42 ? "high" : result.total < 65 ? "building" : "steady";
        let recommendation;

        if (band === "high") {
            recommendation = [
                "The NourisHer Transformation™",
                "Several areas appear to be interacting at once. A personalised strategy may help you stop guessing and focus on what matters most.",
                ["Individual review of your routines and priorities", "A strategy tailored to your body and real life", "Private accountability and adjustments"],
                "Apply to Transformation →",
                "/transformation-interest?source=assessment",
                "Explore Foundations",
                "/foundations",
            ];
        } else if (band === "building" && result.opportunity === "behaviour") {
            recommendation = [
                "NourisHer Foundations",
                "Your biggest need appears to be structure and consistency. Foundations may be the best place to build momentum with guided habits, challenges and community.",
                ["Build repeatable habits without perfection", "Focus on the highest-impact actions", "Use group support to create momentum"],
                "Explore Foundations →",
                "/foundations",
                "See Transformation",
                "/transformation",
            ];
        } else if (band === "building") {
            recommendation = [
                "Choose the level of support that fits you",
                "You have useful strengths, but one or two areas may need focused attention. Foundations builds structure; Transformation offers deeper personalisation.",
                ["Focus on one or two high-impact areas", "Choose group structure or 1:1 coaching", "Build on what is already working"],
                "Explore Transformation →",
                "/transformation",
                "See Foundations",
                "/foundations",
            ];
        } else {
            recommendation = [
                "Build on the strong foundation you already have",
                "Your snapshot shows several supportive habits. Your next step is likely refinement through Foundations or personalised coaching if results still feel slow.",
                ["Protect the habits already working", "Refine the lowest-scoring area", "Use personalisation if effort and results feel mismatched"],
                "Explore Foundations →",
                "/foundations",
                "Explore Transformation",
                "/transformation",
            ];
        }

        put("[data-recommendation-title]", recommendation[0]);
        put("[data-recommendation-copy]", recommendation[1]);

        const recommendationPoints = document.querySelector("[data-recommendation-points]");
        if (recommendationPoints) {
            recommendationPoints.innerHTML = recommendation[2].map((item) => `<li>${item}</li>`).join("");
        }

        const primaryRecommendation = document.querySelector("[data-primary-recommendation]");
        const secondaryRecommendation = document.querySelector("[data-secondary-recommendation]");

        if (primaryRecommendation) {
            primaryRecommendation.textContent = recommendation[3];
            primaryRecommendation.href = recommendation[4];
        }

        if (secondaryRecommendation) {
            secondaryRecommendation.textContent = recommendation[5];
            secondaryRecommendation.href = recommendation[6];
        }
    }

    // Transformation application
    const applicationForm = document.querySelector("[data-application-form]");
    let applicationFormToken = "";

    if (applicationForm) {
        fetch("/form-token/application", { credentials: "same-origin" })
            .then(response => response.ok ? response.json() : Promise.reject(new Error("token")))
            .then(data => { applicationFormToken = data.token || ""; })
            .catch(() => { applicationFormToken = ""; });
    }

    if (applicationForm) {
        const hasInterestToken = new URLSearchParams(window.location.search).has("interest_token");
        // When an application is opened from a secure interest link,
        // the token-prefill script is authoritative. Do not let an
        // older browser localStorage lead overwrite the current enquiry.
        const savedLead = hasInterestToken ? {} : load(LEAD_KEY);
        const nameField = document.getElementById("name");
        const phoneField = document.getElementById("phone");
        const emailField = document.getElementById("email");
        const consentField = document.getElementById("consent");
        let applicationPhoneWidget = null;

        if (savedLead.name && nameField) {
            nameField.value = savedLead.name;
        }

        if (savedLead.email && emailField) {
            emailField.value = savedLead.email;
        }

        if (phoneField) {
            applicationPhoneWidget = intlTelInput(phoneField, {
                initialCountry: "in",
                separateDialCode: true,
                nationalMode: true,
                strictMode: true,
                loadUtils: () => import(
                    "https://cdn.jsdelivr.net/npm/intl-tel-input@25.3.2/build/js/utils.js"
                ),
            });

            if (savedLead.phone) {
                applicationPhoneWidget.setNumber(savedLead.phone);
            }

            phoneField.addEventListener("input", () => {
                phoneField.setCustomValidity("");
            });
        }

        // Prefill from a secure Transformation interest link.
        // The interest token is authoritative for this application.
        const interestToken = new URLSearchParams(
            window.location.search
        ).get("interest_token");

        if (interestToken) {
            fetch(
                `/transformation-interest/application-prefill?token=${encodeURIComponent(interestToken)}`,
                {
                    credentials: "same-origin",
                    cache: "no-store",
                }
            )
                .then((response) => {
                    if (!response.ok) {
                        throw new Error(
                            `Interest prefill failed (${response.status})`
                        );
                    }
                    return response.json();
                })
                .then((data) => {
                    if (nameField && data.name) {
                        nameField.value = data.name;
                        nameField.dispatchEvent(
                            new Event("input", { bubbles: true })
                        );
                    }

                    if (
                        phoneField &&
                        data.phone &&
                        applicationPhoneWidget
                    ) {
                        applicationPhoneWidget.setNumber(data.phone);
                    }

                    const occupationField =
                        document.getElementById("occupation");

                    if (occupationField && data.occupation) {
                        occupationField.value = data.occupation;
                        occupationField.dispatchEvent(
                            new Event("change", { bubbles: true })
                        );
                    }

                    const whyNowField =
                        document.getElementById("why-now");

                    if (whyNowField && data.why_now) {
                        whyNowField.value = data.why_now;
                        whyNowField.dispatchEvent(
                            new Event("input", { bubbles: true })
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

                    const mappedPriorities = [];

                    (data.goals || []).forEach((goal) => {
                        const value = priorityMap[goal];

                        if (Array.isArray(value)) {
                            mappedPriorities.push(...value);
                        } else if (value) {
                            mappedPriorities.push(value);
                        }
                    });

                    document
                        .querySelectorAll('input[name="priorities"]')
                        .forEach((input) => {
                            input.checked =
                                mappedPriorities.includes(input.value);
                        });

                    const hiddenToken =
                        document.getElementById("interest-token");

                    if (hiddenToken) {
                        hiddenToken.value = interestToken;
                    }

                    const hiddenInterest =
                        document.getElementById("interest-id");

                    if (hiddenInterest) {
                        hiddenInterest.value =
                            data.interest_id || "";
                    }
                })
                .catch((error) => {
                    console.error(
                        "Transformation application prefill failed:",
                        error
                    );
                });
        }


        // Seven-step application navigation.
        // Steps 1–6 advance with Continue; only Step 7 submits the form.
        const applicationSteps = [...applicationForm.querySelectorAll("[data-application-step]")];
        const applicationStepLabel = document.querySelector("[data-application-step-label]");
        const applicationProgress = document.querySelector("[data-application-progress]");
        let currentApplicationStep = Math.max(
            0,
            applicationSteps.findIndex((step) => step.classList.contains("active"))
        );

        const updateApplicationStep = (index, behavior = "smooth") => {
            if (!applicationSteps.length) return;

            currentApplicationStep = Math.max(
                0,
                Math.min(index, applicationSteps.length - 1)
            );

            applicationSteps.forEach((step, stepIndex) => {
                step.classList.toggle("active", stepIndex === currentApplicationStep);
            });

            const stepNumber = currentApplicationStep + 1;
            const progress = (stepNumber / applicationSteps.length) * 100;

            if (applicationStepLabel) {
                applicationStepLabel.textContent = `Step ${stepNumber} of ${applicationSteps.length}`;
            }

            if (applicationProgress) {
                applicationProgress.style.width = `${progress}%`;
            }

            requestAnimationFrame(() => {
                const activeStep = applicationSteps[currentApplicationStep];
                const header = document.querySelector(".journey-header");
                const progressBar = document.querySelector(".application-progress");
                const offset =
                    (header?.offsetHeight || 0) +
                    (progressBar?.offsetHeight || 0) +
                    24;

                if (activeStep) {
                    const targetTop =
                        activeStep.getBoundingClientRect().top +
                        window.scrollY -
                        offset;

                    window.scrollTo({
                        top: Math.max(0, targetTop),
                        behavior,
                    });
                }
            });
        };

        const validateCurrentApplicationStep = () => {
            const activeStep = applicationSteps[currentApplicationStep];
            if (!activeStep) return true;

            const fields = [...activeStep.querySelectorAll("input, select, textarea")]
                .filter((field) => !field.disabled && field.type !== "hidden");

            for (const field of fields) {
                if (!field.checkValidity()) {
                    field.reportValidity();
                    return false;
                }
            }

            return true;
        };

        applicationForm.querySelectorAll("[data-application-next]").forEach((button) => {
            button.addEventListener("click", () => {
                if (!validateCurrentApplicationStep()) return;

                if (currentApplicationStep < applicationSteps.length - 1) {
                    updateApplicationStep(currentApplicationStep + 1);
                }
            });
        });

        applicationForm.querySelectorAll("[data-application-back]").forEach((button) => {
            button.addEventListener("click", () => {
                if (currentApplicationStep > 0) {
                    updateApplicationStep(currentApplicationStep - 1);
                }
            });
        });

        updateApplicationStep(currentApplicationStep, "auto");

        applicationForm.addEventListener("submit", async (event) => {
            event.preventDefault();

            if (!applicationForm.checkValidity()) {
                applicationForm.reportValidity();
                return;
            }

            const submitButton = applicationForm.querySelector('button[type="submit"]');
            let phone = phoneField?.value.trim() || "";

            if (applicationPhoneWidget && phoneField) {
                await applicationPhoneWidget.promise;

                if (!applicationPhoneWidget.isValidNumber()) {
                    phoneField.setCustomValidity("Please enter a valid mobile number.");
                    phoneField.reportValidity();
                    return;
                }

                phoneField.setCustomValidity("");
                phone = applicationPhoneWidget.getNumber();
            }

            const checkedValues = (name) =>
                [...applicationForm.querySelectorAll(`input[name="${name}"]:checked`)]
                    .map((input) => input.value);

            const triedValues = checkedValues("triedOptions");
            const supportValues = checkedValues("coachNeeds");

            const triedField = document.getElementById("tried");
            const supportField = document.getElementById("support");

            if (triedField) triedField.value = triedValues.join(", ");
            if (supportField) supportField.value = supportValues.join(", ");

            const payload = {
                snapshot_id: savedLead.snapshotId || null,
                interest_token:
                    document.getElementById("interest-token")?.value ||
                    interestToken ||
                    null,
                name: nameField?.value.trim() || "",
                email: emailField?.value.trim() || "",
                phone,
                age_range: document.getElementById("age")?.value || "",
                why_now: document.getElementById("why-now")?.value.trim() || "",
                tried: document.getElementById("tried")?.value.trim() || "",
                success_goal: document.getElementById("success")?.value.trim() || "",
                support_needed: document.getElementById("support")?.value || "",
                application_data: {},
                consent: Boolean(consentField?.checked),
                form_token: applicationFormToken,
                website: document.getElementById("website")?.value || "",
            };

            console.log("APPLICATION PAYLOAD CHECK", {
                why_now: payload.why_now,
                success_goal: payload.success_goal,
                why_now_length: payload.why_now.length,
                success_goal_length: payload.success_goal.length,
            });

            console.log("APPLICATION PAYLOAD CHECK", {
                why_now: payload.why_now,
                success_goal: payload.success_goal,
                why_now_length: payload.why_now.length,
                success_goal_length: payload.success_goal.length,
            });

            try {
                if (submitButton) {
                    console.log("WHY NOW VALUE:", JSON.stringify(payload.why_now));
                    console.log("SUCCESS GOAL VALUE:", JSON.stringify(payload.success_goal));
                    submitButton.disabled = true;
                    submitButton.textContent = "Submitting…";
                }

                const response = await fetch("/application", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload),
                });

                const data = await response.json();

                if (!response.ok || data.status !== "saved") {
                    let message = data.message || "";

                    if (!message && Array.isArray(data.detail)) {
                        message = data.detail
                            .map((item) => {
                                const field = Array.isArray(item.loc)
                                    ? item.loc.join(".")
                                    : "form";
                                return `${field}: ${item.msg}`;
                            })
                            .join("\n");
                    }

                    if (!message && typeof data.detail === "string") {
                        message = data.detail;
                    }

                    throw new Error(
                        message || "The application could not be submitted."
                    );
                }

                save(APPLICATION_KEY, {
                    ...payload,
                    applicationId: data.application_id,
                    submittedAt: new Date().toISOString(),
                });

                save(LEAD_KEY, {
                    ...savedLead,
                    name: payload.name,
                    phone: payload.phone,
                    email: payload.email,
                    applicationId: data.application_id,
                });

                window.location.href = "/thank-you";
            } catch (error) {
                console.error("Application submission failed:", error);
                alert(error.message || "We could not submit your application. Please try again.");

                if (submitButton) {
                    submitButton.disabled = false;
                    submitButton.textContent = "Submit my application →";
                }
            }
        });
    }

    // Generic international phone field on other pages, without reinitialising assessment/application forms.
    if (!assessmentForm && !applicationForm) {
        const genericPhoneInput = document.getElementById("phone");

        if (genericPhoneInput) {
            intlTelInput(genericPhoneInput, {
                initialCountry: "in",
                separateDialCode: true,
                nationalMode: true,
                strictMode: true,
                loadUtils: () => import(
                    "https://cdn.jsdelivr.net/npm/intl-tel-input@25.3.2/build/js/utils.js"
                ),
            });
        }
    }
})();
