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

    document.querySelectorAll("[data-character-counter]").forEach((counter) => {
        const targetId = counter.dataset.counterFor || "content";
        const textarea = document.getElementById(targetId);

        if (!textarea) {
            return;
        }

        const maxLength = Number(textarea.getAttribute("maxlength")) || 1000;
        const updateCounter = () => {
            counter.textContent = `${textarea.value.length}/${maxLength} characters`;
        };

        textarea.addEventListener("input", updateCounter);
        updateCounter();
    });

    const studio = document.querySelector("[data-writing-studio]");
    const rawContent = document.querySelector("[data-raw-content]");
    const finalContent = document.querySelector("[data-final-content]");
    const aiOutput = document.querySelector("[data-ai-output]");
    const aiStatus = document.querySelector("[data-ai-status]");
    const voiceStatus = document.querySelector("[data-voice-status]");
    const selectedModeInput = document.querySelector("[data-selected-mode]");
    let finalWasEdited = Boolean(finalContent && finalContent.value.trim());

    const selectedMode = () => {
        if (selectedModeInput && selectedModeInput.value) {
            return selectedModeInput.value;
        }

        const checked = document.querySelector('input[name="mode_choice"]:checked');
        return checked ? checked.value : "Calm";
    };

    const setSelectedMode = (mode) => {
        const modeValue = mode || "Calm";

        if (selectedModeInput) {
            selectedModeInput.value = modeValue;
        }

        document.querySelectorAll('input[name="mode_choice"]').forEach((input) => {
            input.checked = input.value === modeValue;
        });
        updateStudioMode();
    };

    const updateStudioMode = () => {
        if (studio) {
            studio.dataset.mode = selectedMode().toLowerCase();
        }
    };

    document.querySelectorAll("[data-mode-option]").forEach((option) => {
        option.addEventListener("click", () => {
            setSelectedMode(option.dataset.modeValue);
        });
    });

    document.querySelectorAll('input[name="mode_choice"]').forEach((input) => {
        input.addEventListener("change", () => {
            setSelectedMode(input.value);
        });
    });
    setSelectedMode(selectedMode());

    if (rawContent && finalContent) {
        rawContent.addEventListener("input", () => {
            if (!finalWasEdited) {
                finalContent.value = rawContent.value;
                finalContent.dispatchEvent(new Event("input"));
            }
        });

        finalContent.addEventListener("input", () => {
            finalWasEdited = true;
        });
    }

    document.querySelectorAll("[data-ai-action]").forEach((button) => {
        button.addEventListener("click", async () => {
            if (!rawContent || !aiOutput || !aiStatus) {
                return;
            }

            const text = rawContent.value.trim();
            if (!text) {
                aiStatus.textContent = "Add a raw thought first.";
                return;
            }

            aiStatus.textContent = "PILOT is shaping a suggestion...";
            button.disabled = true;

            try {
                const response = await fetch("/ai_assist", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify({
                        text,
                        mode: selectedMode(),
                        action: button.dataset.aiAction,
                    }),
                });
                const data = await response.json();

                if (!response.ok) {
                    aiStatus.textContent = data.error || "AI Assist could not respond.";
                    return;
                }

                aiOutput.value = data.suggestion;
                aiStatus.textContent = `${data.mode} suggestion ready. Accept it only if it fits.`;
            } catch (error) {
                aiStatus.textContent = "AI Assist is unavailable right now.";
            } finally {
                button.disabled = false;
            }
        });
    });

    const acceptButton = document.querySelector("[data-accept-suggestion]");
    if (acceptButton && aiOutput && finalContent) {
        acceptButton.addEventListener("click", () => {
            if (!aiOutput.value.trim()) {
                if (aiStatus) {
                    aiStatus.textContent = "There is no suggestion to accept yet.";
                }
                return;
            }

            finalContent.value = aiOutput.value;
            finalWasEdited = true;
            finalContent.dispatchEvent(new Event("input"));
            if (aiStatus) {
                aiStatus.textContent = "Suggestion accepted into your final journal content.";
            }
        });
    }

    const copyButton = document.querySelector("[data-copy-suggestion]");
    if (copyButton && aiOutput) {
        copyButton.addEventListener("click", async () => {
            if (!aiOutput.value.trim()) {
                if (aiStatus) {
                    aiStatus.textContent = "There is no suggestion to copy yet.";
                }
                return;
            }

            try {
                await navigator.clipboard.writeText(aiOutput.value);
                if (aiStatus) {
                    aiStatus.textContent = "Suggestion copied.";
                }
            } catch (error) {
                aiOutput.select();
                if (aiStatus) {
                    aiStatus.textContent = "Select and copy the suggestion manually.";
                }
            }
        });
    }

    const discardButton = document.querySelector("[data-discard-suggestion]");
    if (discardButton && aiOutput) {
        discardButton.addEventListener("click", () => {
            aiOutput.value = "";
            if (aiStatus) {
                aiStatus.textContent = "Suggestion discarded. Your original thought is unchanged.";
            }
        });
    }

    const voiceButton = document.querySelector("[data-voice-button]");
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (voiceButton && rawContent) {
        if (!SpeechRecognition) {
            voiceButton.disabled = true;
            if (voiceStatus) {
                voiceStatus.textContent = "Voice input is not available in this browser. Typing still works.";
            }
        } else {
            const recognition = new SpeechRecognition();
            recognition.continuous = false;
            recognition.interimResults = false;
            recognition.lang = "en-US";

            voiceButton.addEventListener("click", () => {
                recognition.start();
                if (voiceStatus) {
                    voiceStatus.textContent = "Listening...";
                }
            });

            recognition.addEventListener("result", (event) => {
                const transcript = event.results[0][0].transcript;
                const spacer = rawContent.value.trim() ? " " : "";
                rawContent.value = `${rawContent.value}${spacer}${transcript}`;
                rawContent.dispatchEvent(new Event("input"));
                if (voiceStatus) {
                    voiceStatus.textContent = "Voice captured. You can edit it before saving.";
                }
            });

            recognition.addEventListener("error", () => {
                if (voiceStatus) {
                    voiceStatus.textContent = "Voice input paused. Typing still works.";
                }
            });

            recognition.addEventListener("end", () => {
                if (voiceStatus && voiceStatus.textContent === "Listening...") {
                    voiceStatus.textContent = "Voice input ready.";
                }
            });
        }
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
