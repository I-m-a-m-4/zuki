// Interactive Playground Simulation
document.addEventListener("DOMContentLoaded", () => {
  const chips = document.querySelectorAll(".prompt-chip");
  const simText = document.getElementById("simText");
  const pointer = document.getElementById("zukiPointer");
  const bubble = document.getElementById("pointerBubble");
  const voiceStatus = document.getElementById("voiceStatusText");

  // Coordinate positions for pointer animation based on action
  const targets = {
    tour: { top: "75px", left: "280px", text: '"Found the Export button! Clicking it now…"' },
    act: { top: "150px", left: "120px", text: '"Opening Spotify app & initiating music playback…"' },
    organize: { top: "210px", left: "220px", text: '"Classified 14 files into organized folders."' },
    background: { top: "110px", left: "400px", text: '"Spawned Hermes research task in background."' }
  };

  chips.forEach((chip) => {
    chip.addEventListener("click", () => {
      chips.forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");

      const reply = chip.getAttribute("data-reply");
      const action = chip.getAttribute("data-action");
      const promptTitle = chip.innerText.trim();

      // Update spoken response text
      simText.style.opacity = "0";
      setTimeout(() => {
        simText.innerText = `"${reply}"`;
        simText.style.opacity = "1";
      }, 150);

      // Update simulated voice status bar
      if (voiceStatus) {
        voiceStatus.innerText = `Listening: ${promptTitle}`;
      }

      // Move simulated Zuki pointer buddy
      if (pointer && targets[action]) {
        pointer.style.top = targets[action].top;
        pointer.style.left = targets[action].left;

        if (bubble) {
          const bubbleText = bubble.querySelector(".bubble-text");
          if (bubbleText) {
            bubbleText.innerText = targets[action].text;
          }
        }
      }
    });
  });
});
