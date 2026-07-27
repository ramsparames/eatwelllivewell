const menuToggle = document.querySelector(".menu-toggle");
const mainNav = document.querySelector(".main-nav");

if (menuToggle && mainNav) {
  menuToggle.addEventListener("click", () => {
    const isOpen = menuToggle.getAttribute("aria-expanded") === "true";
    menuToggle.setAttribute("aria-expanded", String(!isOpen));
    mainNav.classList.toggle("open");
    document.body.classList.toggle("menu-open", !isOpen);
  });

  mainNav.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", () => {
      menuToggle.setAttribute("aria-expanded", "false");
      mainNav.classList.remove("open");
      document.body.classList.remove("menu-open");
    });
  });
}

document.querySelectorAll(".faq-question").forEach((button) => {
  button.addEventListener("click", () => {
    const item = button.closest(".faq-item");
    const answer = item.querySelector(".faq-answer");
    const isOpen = button.getAttribute("aria-expanded") === "true";

    document.querySelectorAll(".faq-question").forEach((otherButton) => {
      if (otherButton !== button) {
        otherButton.setAttribute("aria-expanded", "false");
        otherButton.closest(".faq-item").querySelector(".faq-answer").style.maxHeight = null;
      }
    });

    button.setAttribute("aria-expanded", String(!isOpen));
    answer.style.maxHeight = isOpen ? null : `${answer.scrollHeight}px`;
  });
});

const year = document.getElementById("year");
if (year) year.textContent = new Date().getFullYear();
