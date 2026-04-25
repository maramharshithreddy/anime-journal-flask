document.addEventListener("DOMContentLoaded", () => {
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
            const confirmed = window.confirm("Delete this journal entry?");
            if (!confirmed) {
                event.preventDefault();
            }
        });
    });
});
