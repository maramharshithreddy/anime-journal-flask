document.addEventListener("DOMContentLoaded", () => {
    const petalLayer = document.querySelector("[data-petal-fall]");
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    if (petalLayer && !prefersReducedMotion) {
        const petalCount = 18;

        for (let index = 0; index < petalCount; index += 1) {
            const petal = document.createElement("span");
            const size = 10 + Math.random() * 14;
            const duration = 14 + Math.random() * 14;
            const delay = Math.random() * -duration;
            const drift = 18 + Math.random() * 58;
            const opacity = 0.36 + Math.random() * 0.34;

            petal.className = "falling-petal";
            petal.style.setProperty("--petal-left", `${Math.random() * 100}vw`);
            petal.style.setProperty("--petal-size", `${size}px`);
            petal.style.setProperty("--petal-duration", `${duration}s`);
            petal.style.setProperty("--petal-delay", `${delay}s`);
            petal.style.setProperty("--petal-drift", `${drift}px`);
            petal.style.setProperty("--petal-rotate", `${Math.random() * 360}deg`);
            petal.style.setProperty("--petal-opacity", opacity.toFixed(2));
            petal.style.setProperty("--petal-sway-duration", `${4 + Math.random() * 4}s`);
            petalLayer.appendChild(petal);
        }
    }

    const textarea = document.querySelector("#content");
    const counter = document.querySelector("[data-character-counter]");

    if (textarea && counter) {
        const maxLength = Number(textarea.getAttribute("maxlength")) || 1000;
        const updateCounter = () => {
            counter.textContent = `${textarea.value.length}/${maxLength} characters`;
        };

        textarea.addEventListener("input", updateCounter);
        updateCounter();
    }

    document.querySelectorAll("[data-confirm-delete]").forEach((button) => {
        button.addEventListener("click", (event) => {
            const confirmed = window.confirm("Delete this journal page?");
            if (!confirmed) {
                event.preventDefault();
            }
        });
    });
});
