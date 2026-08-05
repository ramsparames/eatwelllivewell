(() => {
  const header = document.querySelector("[data-header]");
  const toggle = document.querySelector("[data-menu-toggle]");
  const nav = document.querySelector("[data-nav]");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const updateHeader = () => {
    header?.classList.toggle("scrolled", window.scrollY > 20);
  };

  updateHeader();
  window.addEventListener("scroll", updateHeader, { passive: true });

  if (toggle && nav) {
    const closeMenu = () => {
      toggle.classList.remove("active");
      toggle.setAttribute("aria-expanded", "false");
      nav.classList.remove("open");
      document.body.classList.remove("menu-open");
    };

    toggle.addEventListener("click", () => {
      const isOpen = toggle.getAttribute("aria-expanded") === "true";
      toggle.classList.toggle("active", !isOpen);
      toggle.setAttribute("aria-expanded", String(!isOpen));
      nav.classList.toggle("open", !isOpen);
      document.body.classList.toggle("menu-open", !isOpen);
    });

    nav.querySelectorAll("a").forEach((link) => {
      link.addEventListener("click", closeMenu);
    });

    window.addEventListener("resize", () => {
      if (window.innerWidth > 900) closeMenu();
    });
  }

  const revealElements = document.querySelectorAll(".reveal");

  if (reduceMotion || !("IntersectionObserver" in window)) {
    revealElements.forEach((element) => element.classList.add("in"));
  } else {
    const observer = new IntersectionObserver(
      (entries, obs) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("in");
          obs.unobserve(entry.target);
        });
      },
      { threshold: 0.12, rootMargin: "0px 0px -40px" }
    );

    revealElements.forEach((element) => observer.observe(element));
  }

  document.querySelectorAll('a[href^="#"]').forEach((link) => {
    link.addEventListener("click", (event) => {
      const targetId = link.getAttribute("href");
      if (!targetId || targetId === "#") return;

      const target = document.querySelector(targetId);
      if (!target) return;

      event.preventDefault();
      const headerHeight = header?.offsetHeight ?? 0;
      const top = target.getBoundingClientRect().top + window.scrollY - headerHeight + 1;

      window.scrollTo({
        top,
        behavior: reduceMotion ? "auto" : "smooth"
      });

      history.pushState(null, "", targetId);
    });
  });
// Prefill the Synamate Clarity Call booking link
const clarityBookingLink = document.querySelector(
    "[data-clarity-booking-link]"
);

if (clarityBookingLink) {
    let savedApplication = {};
    let savedLead = {};

    try {
        savedApplication = JSON.parse(
            localStorage.getItem("nourisherApplication") || "{}"
        );

        savedLead = JSON.parse(
            localStorage.getItem("nourisherLead") || "{}"
        );
    } catch (error) {
        console.warn(
            "Saved applicant details could not be read:",
            error
        );
    }

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
            "name",
            fullName
        );

        bookingUrl.searchParams.set(
            "full_name",
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
