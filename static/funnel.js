import intlTelInput from "https://cdn.jsdelivr.net/npm/intl-tel-input@25.3.2/+esm";

(async () => {
    "use strict";

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
            body: JSON.stringify({ name, phone, answers }),
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
                "/join",
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
const applicationForm = document.querySelector(
    "[data-application-form]"
);

if (applicationForm) {
    const savedLead = load(LEAD_KEY) || {};
    const draftKey = "nourisher-application-draft";

    const steps = Array.from(
        applicationForm.querySelectorAll(
            "[data-application-step]"
        )
    );

    const progressFill = document.querySelector(
        "[data-application-progress]"
    );

    const stepLabel = document.querySelector(
        "[data-application-step-label]"
    );

    const nameField = document.getElementById("name");
    const phoneField = document.getElementById("phone");
    const emailField = document.getElementById("email");
    const consentField = document.getElementById("consent");
    const commitmentField = document.getElementById(
        "commitment"
    );

    const commitmentValue = document.querySelector(
        "[data-commitment-value]"
    );

    let currentStep = 0;
    let applicationPhoneWidget = null;

    const checkedValues = (name) => (
        Array.from(
            applicationForm.querySelectorAll(
                `input[name="${name}"]:checked`
            )
        ).map((input) => input.value)
    );

    const fieldValue = (id) => (
        document.getElementById(id)?.value.trim() || ""
    );

    const showStep = (stepIndex, shouldScroll = true) => {
	    const safeStep = Math.max(
	        0,
	        Math.min(stepIndex, steps.length - 1)
	    );
	
	    steps.forEach((step, index) => {
	        step.classList.toggle(
	            "active",
	            index === safeStep
	        );
	    });
	
	    currentStep = safeStep;
	
	    const progressPercent =
	        ((currentStep + 1) / steps.length) * 100;
	
	    if (progressFill) {
	        progressFill.style.width =
	            `${progressPercent}%`;
	    }
	
	    if (stepLabel) {
	        stepLabel.textContent =
	            `Step ${currentStep + 1} of ${steps.length}`;
	    }
	
	    if (!shouldScroll) {
	        return;
	    }
	
	    requestAnimationFrame(() => {
	        const progress = document.querySelector(
	            ".application-progress"
	        );
	
	        const header = document.querySelector(
	            ".journey-header"
	        );
	
	        if (!progress) {
	            return;
	        }
	
	        const headerHeight =
	            header?.offsetHeight || 0;
	
	        const targetTop =
	            progress.getBoundingClientRect().top
	            + window.scrollY
	            - headerHeight
	            - 12;
	
	        window.scrollTo({
	            top: Math.max(0, targetTop),
	            behavior: "smooth",
	        });
	    });
	};

    const findInvalidRequiredField = (step) => {
        const requiredFields = Array.from(
            step.querySelectorAll(
                "input[required], select[required], textarea[required]"
            )
        );

        return requiredFields.find(
            (field) => !field.checkValidity()
        );
    };

    const requireChoice = (
        step,
        name,
        message,
        minimum = 1,
        maximum = null
    ) => {
        const choices = checkedValues(name);

        if (choices.length < minimum) {
            alert(message);

            step.querySelector(
                `input[name="${name}"]`
            )?.focus();

            return false;
        }

        if (
            maximum !== null
            && choices.length > maximum
        ) {
            alert(
                `Please choose no more than ${maximum}.`
            );

            return false;
        }

        return true;
    };

    const validateStep = (stepIndex) => {
        const step = steps[stepIndex];

        if (!step) {
            return false;
        }

        const invalidField =
            findInvalidRequiredField(step);

        if (invalidField) {
            invalidField.reportValidity();
            invalidField.focus();

            return false;
        }

        const stepNumber = Number(
            step.dataset.applicationStep
        );

        if (
            stepNumber === 2
            && !requireChoice(
                step,
                "symptoms",
                "Please choose at least one option describing how you feel."
            )
        ) {
            return false;
        }

        if (
            stepNumber === 3
            && !requireChoice(
                step,
                "priorities",
                "Please choose your priorities.",
                1,
                3
            )
        ) {
            return false;
        }

        if (
            stepNumber === 4
            && !requireChoice(
                step,
                "triedOptions",
                "Please choose at least one thing you have tried."
            )
        ) {
            return false;
        }

        if (
            stepNumber === 4
            && !requireChoice(
                step,
                "fallOffReasons",
                "Please choose at least one reason you tend to fall off track."
            )
        ) {
            return false;
        }

        if (
            stepNumber === 6
            && !requireChoice(
                step,
                "coachNeeds",
                "Please choose at least one kind of support you are looking for."
            )
        ) {
            return false;
        }

        return true;
    };

    const collectDraft = () => {
        const draft = {};

        applicationForm
            .querySelectorAll(
                "input, select, textarea"
            )
            .forEach((field) => {
                if (!field.name) {
                    return;
                }

                if (
                    field.type === "checkbox"
                    || field.type === "radio"
                ) {
                    if (!draft[field.name]) {
                        draft[field.name] = [];
                    }

                    if (field.checked) {
                        draft[field.name].push(
                            field.value
                        );
                    }

                    return;
                }

                draft[field.name] = field.value;
            });

        draft.currentStep = currentStep;

        return draft;
    };

    const saveDraft = () => {
        try {
            localStorage.setItem(
                draftKey,
                JSON.stringify(collectDraft())
            );
        } catch (error) {
            console.warn(
                "Application draft could not be saved:",
                error
            );
        }
    };

    const restoreDraft = () => {
        let draft = null;

        try {
            draft = JSON.parse(
                localStorage.getItem(draftKey)
            );
        } catch (error) {
            console.warn(
                "Application draft could not be restored:",
                error
            );
        }

        if (!draft) {
            return;
        }

        applicationForm
            .querySelectorAll(
                "input, select, textarea"
            )
            .forEach((field) => {
                if (!field.name) {
                    return;
                }

                const storedValue = draft[field.name];

                if (storedValue === undefined) {
                    return;
                }

                if (
                    field.type === "checkbox"
                    || field.type === "radio"
                ) {
                    field.checked = Array.isArray(
                        storedValue
                    )
                        ? storedValue.includes(
                            field.value
                        )
                        : storedValue === field.value;

                    return;
                }

                field.value = storedValue;
            });

        if (
            Number.isInteger(draft.currentStep)
            && draft.currentStep >= 0
            && draft.currentStep < steps.length
        ) {
            currentStep = draft.currentStep;
        }
    };

    restoreDraft();

    // Assessment visitors get their known details pre-filled.
    if (savedLead.name && nameField) {
        nameField.value = savedLead.name;
    }

    if (savedLead.email && emailField) {
        emailField.value = savedLead.email;
    }

    if (phoneField) {
        applicationPhoneWidget = intlTelInput(
            phoneField,
            {
                initialCountry: "in",
                separateDialCode: true,
                nationalMode: true,
                strictMode: true,
                loadUtils: () => import(
                    "https://cdn.jsdelivr.net/npm/intl-tel-input@25.3.2/build/js/utils.js"
                ),
            }
        );

        if (savedLead.phone) {
            applicationPhoneWidget.setNumber(
                savedLead.phone
            );
        } else if (phoneField.value) {
            applicationPhoneWidget.setNumber(
                phoneField.value
            );
        }

        phoneField.addEventListener(
            "input",
            () => {
                phoneField.setCustomValidity("");
            }
        );
    }

    if (commitmentField && commitmentValue) {
        commitmentValue.textContent =
            commitmentField.value;

        commitmentField.addEventListener(
            "input",
            () => {
                commitmentValue.textContent =
                    commitmentField.value;

                saveDraft();
            }
        );
    }

    applicationForm.addEventListener(
        "input",
        saveDraft
    );

    applicationForm.addEventListener(
        "change",
        saveDraft
    );

    applicationForm.querySelectorAll(
        "[data-application-next]"
    ).forEach((button) => {
        button.addEventListener("click", () => {
            if (!validateStep(currentStep)) {
                return;
            }

            saveDraft();
            showStep(currentStep + 1);
        });
    });

    applicationForm.querySelectorAll(
        "[data-application-back]"
    ).forEach((button) => {
        button.addEventListener("click", () => {
            saveDraft();
            showStep(currentStep - 1);
        });
    });

    // Prevent applicants selecting more than three priorities.
    applicationForm.querySelectorAll(
        'input[name="priorities"]'
    ).forEach((input) => {
        input.addEventListener("change", () => {
            const selected =
                checkedValues("priorities");

            if (selected.length > 3) {
                input.checked = false;

                alert(
                    "Please choose no more than three priorities."
                );
            }
        });
    });

    showStep(currentStep, false);

    applicationForm.addEventListener(
        "submit",
        async (event) => {
            event.preventDefault();

            // Recheck every section before sending.
            for (
                let index = 0;
                index < steps.length;
                index += 1
            ) {
                if (!validateStep(index)) {
                    showStep(index);
                    return;
                }
            }

            const submitButton =
                applicationForm.querySelector(
                    'button[type="submit"]'
                );

            let phone =
                phoneField?.value.trim() || "";

            if (
                applicationPhoneWidget
                && phoneField
            ) {
                await applicationPhoneWidget.promise;

                if (
                    !applicationPhoneWidget
                        .isValidNumber()
                ) {
                    showStep(0);

                    phoneField.setCustomValidity(
                        "Please enter a valid mobile number."
                    );

                    phoneField.reportValidity();
                    return;
                }

                phoneField.setCustomValidity("");
                phone =
                    applicationPhoneWidget.getNumber();
            }

            const symptoms =
                checkedValues("symptoms");

            const priorities =
                checkedValues("priorities");

            const triedOptions =
                checkedValues("triedOptions");

            const fallOffReasons =
                checkedValues("fallOffReasons");

            const coachNeeds =
                checkedValues("coachNeeds");

            // Maintain the original summary fields used by
            // existing email and dashboard code.
            const triedSummary =
                triedOptions.join(", ");

            const supportSummary =
                coachNeeds.join(", ");

            const hiddenTried =
                document.getElementById("tried");

            const hiddenSupport =
                document.getElementById("support");

            if (hiddenTried) {
                hiddenTried.value = triedSummary;
            }

            if (hiddenSupport) {
                hiddenSupport.value =
                    supportSummary;
            }

            const applicationData = {
                city: fieldValue("city"),
                country: fieldValue("country"),
                occupation: fieldValue(
                    "occupation"
                ),
                relationship_status: fieldValue(
                    "relationship-status"
                ),
                children: fieldValue("children"),
                referral_source: fieldValue(
                    "referral-source"
                ),

                menopause_stage: fieldValue(
                    "menopause-stage"
                ),
                symptoms,
                health_summary: fieldValue(
                    "health-summary"
                ),

                one_year_vision:
                    fieldValue("success"),
                top_priorities: priorities,
                goals_importance: fieldValue(
                    "goals-importance"
                ),

                obstacles: fieldValue(
                    "obstacles"
                ),
                tried_options: triedOptions,
                fall_off_reasons:
                    fallOffReasons,

                why_now: fieldValue("why-now"),
                nothing_changes: fieldValue(
                    "nothing-changes"
                ),
                commitment: Number(
                    commitmentField?.value || 7
                ),
                readiness: fieldValue(
                    "readiness"
                ),
                importance: fieldValue(
                    "importance"
                ),

                coach_needs: coachNeeds,
                coaching_style: fieldValue(
                    "coaching-style"
                ),
                start_timeline: fieldValue(
                    "start-timeline"
                ),
                investment_readiness:
                    fieldValue(
                        "investment-readiness"
                    ),
                decision_maker: fieldValue(
                    "decision-maker"
                ),

                good_fit: fieldValue("good-fit"),
                additional_notes: fieldValue(
                    "additional-notes"
                ),
            };

            const payload = {
                snapshot_id:
                    savedLead.snapshotId || null,

                name:
                    nameField?.value.trim() || "",

                email:
                    emailField?.value.trim() || "",

                phone,

                age_range:
                    fieldValue("age"),

                why_now:
                    fieldValue("why-now"),

                tried:
                    triedSummary,

                success_goal:
                    fieldValue("success"),

                support_needed:
                    supportSummary,

                application_data:
                    applicationData,

                consent:
                    Boolean(
                        consentField?.checked
                    ),
            };

            try {
                if (submitButton) {
                    submitButton.disabled = true;
                    submitButton.textContent =
                        "Submitting…";
                }

                const response = await fetch(
                    "/application",
                    {
                        method: "POST",
                        headers: {
                            "Content-Type":
                                "application/json",
                        },
                        body: JSON.stringify(
                            payload
                        ),
                    }
                );

                const data =
                    await response.json();

                if (
                    !response.ok
                    || data.status !== "saved"
                ) {
                    throw new Error(
                        data.message
                        || data.detail
                        || "The application could not be submitted."
                    );
                }

                save(APPLICATION_KEY, {
                    ...payload,
                    applicationId:
                        data.application_id,
                    submittedAt:
                        new Date().toISOString(),
                });

                save(LEAD_KEY, {
                    ...savedLead,
                    name: payload.name,
                    phone: payload.phone,
                    email: payload.email,
                    applicationId:
                        data.application_id,
                });

                localStorage.removeItem(draftKey);

                window.location.href =
                    "/thank-you";
            } catch (error) {
                console.error(
                    "Application submission failed:",
                    error
                );

                alert(
                    "We could not submit your application. Please try again."
                );

                if (submitButton) {
                    submitButton.disabled = false;
                    submitButton.textContent =
                        "Submit my application →";
                }
            }
        }
    );
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
// Prefill the Synamate Clarity Call booking form
const clarityBookingLink = document.querySelector(
    "[data-clarity-booking-link]"
);

if (clarityBookingLink) {
    const savedApplication = load(APPLICATION_KEY) || {};
    const savedLead = load(LEAD_KEY) || {};

    const fullName = (
        savedApplication.name
        || savedLead.name
        || ""
    ).trim();

    const email = (
        savedApplication.email
        || savedLead.email
        || ""
    ).trim();

    const phone = (
        savedApplication.phone
        || savedLead.phone
        || ""
    ).trim();

    const bookingUrl = new URL(
        clarityBookingLink.href
    );

    if (fullName) {
        bookingUrl.searchParams.set(
            "full_name",
            fullName
        );

        // Also include the common name parameter as a fallback.
        bookingUrl.searchParams.set(
            "name",
            fullName
        );
    }

    if (email) {
        bookingUrl.searchParams.set(
            "email",
            email
        );
    }

    if (phone) {
        bookingUrl.searchParams.set(
            "phone",
            phone
        );
    }

    clarityBookingLink.href =
        bookingUrl.toString();
	}
})();
