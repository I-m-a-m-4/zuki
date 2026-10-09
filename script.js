// ==============================================================================
// Zuki — Interactive Desktop Engine & UI Controller
// ==============================================================================

document.addEventListener("DOMContentLoaded", () => {
  // 1. Live Menubar Clock
  const timeEl = document.querySelector(".time");
  function updateTime() {
    if (!timeEl) return;
    const now = new Date();
    let hours = now.getHours();
    const minutes = now.getMinutes().toString().padStart(2, "0");
    const ampm = hours >= 12 ? "PM" : "AM";
    hours = hours % 12;
    hours = hours ? hours : 12;
    timeEl.textContent = `${hours}:${minutes} ${ampm}`;
  }
  updateTime();
  setInterval(updateTime, 1000);

  // 2. Interactive Desktop Playground (Prompt Chips & Pointer Buddy)
  const chips = document.querySelectorAll(".prompt-chip");
  const pointerBuddy = document.getElementById("zukiPointerBuddy");
  const pointerBubble = document.getElementById("zukiPointerBubble");
  const snapBox = document.getElementById("targetSnapBox");

  const actionCoordinates = {
    export: { top: "52%", left: "58%", snapTop: "48%", snapLeft: "56%", snapW: "140px", snapH: "48px", label: "UIA Snap: Button [Export]" },
    clean: { top: "25%", left: "15%", snapTop: "20%", snapLeft: "12%", snapW: "160px", snapH: "65px", label: "COM Shell: Desktop Icons (18)" },
    research: { top: "70%", left: "62%", snapTop: "66%", snapLeft: "60%", snapW: "190px", snapH: "45px", label: "Hermes Harness: Background Thread" },
    summarize: { top: "35%", left: "30%", snapTop: "30%", snapLeft: "26%", snapW: "220px", snapH: "70px", label: "Vision OCR: Active Window Bounds" }
  };

  chips.forEach((chip) => {
    chip.addEventListener("click", () => {
      chips.forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");

      const action = chip.getAttribute("data-action") || "export";
      const speech = chip.getAttribute("data-speech") || "Executing action...";
      const coords = actionCoordinates[action] || actionCoordinates.export;

      // Move Zuki Pointer Buddy
      if (pointerBuddy) {
        pointerBuddy.style.top = coords.top;
        pointerBuddy.style.left = coords.left;
      }

      // Update Speech Bubble
      if (pointerBubble) {
        const textSpan = pointerBubble.querySelector(".bubble-text");
        if (textSpan) {
          textSpan.style.opacity = "0";
          setTimeout(() => {
            textSpan.textContent = `"${speech}"`;
            textSpan.style.opacity = "1";
          }, 150);
        }
      }

      // Move Target Snap Box
      if (snapBox) {
        snapBox.style.top = coords.snapTop;
        snapBox.style.left = coords.snapLeft;
        snapBox.style.width = coords.snapW;
        snapBox.style.height = coords.snapH;
        const snapLabel = snapBox.querySelector(".snap-label");
        if (snapLabel) snapLabel.textContent = coords.label;
      }
    });
  });

  // 3. Menubar Audio / Voice Engine Equalizer Toggle
  const npBtn = document.querySelector(".np-btn");
  const npBars = document.querySelector(".status-bars");
  let isListening = false;
  if (npBtn && npBars) {
    npBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      isListening = !isListening;
      npBtn.setAttribute("aria-pressed", isListening ? "true" : "false");
      if (isListening) {
        npBars.classList.remove("dim");
      } else {
        npBars.classList.add("dim");
      }
    });
  }

  // 4. Smooth Anchor Scrolling for Menubar & Footer Links
  const navTargets = document.querySelectorAll("[data-target]");
  navTargets.forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetId = btn.getAttribute("data-target");
      const targetEl = document.getElementById(targetId) || document.querySelector(`.${targetId}`);
      if (targetEl) {
        targetEl.scrollIntoView({ behavior: "smooth" });
      }
    });
  });

  // Check URL hash on page load (e.g. #pricing)
  if (window.location.hash) {
    const hashId = window.location.hash.replace("#", "");
    const targetEl = document.getElementById(hashId);
    if (targetEl) {
      setTimeout(() => {
        targetEl.scrollIntoView({ behavior: "smooth" });
      }, 200);
    }
  }

  // 5. FAQ Accordion Interaction
  const faqItems = document.querySelectorAll(".faq-item");
  faqItems.forEach((item) => {
    item.addEventListener("click", () => {
      const isOpen = item.classList.contains("open");
      faqItems.forEach((other) => {
        if (other !== item) {
          other.classList.remove("open");
          other.setAttribute("aria-expanded", "false");
          const aWrap = other.querySelector(".faq-a-wrap");
          if (aWrap) {
            aWrap.style.gridTemplateRows = "0fr";
            aWrap.style.opacity = "0";
          }
        }
      });

      if (isOpen) {
        item.classList.remove("open");
        item.setAttribute("aria-expanded", "false");
        const aWrap = item.querySelector(".faq-a-wrap");
        if (aWrap) {
          aWrap.style.gridTemplateRows = "0fr";
          aWrap.style.opacity = "0";
        }
      } else {
        item.classList.add("open");
        item.setAttribute("aria-expanded", "true");
        const aWrap = item.querySelector(".faq-a-wrap");
        if (aWrap) {
          aWrap.style.gridTemplateRows = "1fr";
          aWrap.style.opacity = "1";
        }
      }
    });
  });

  // 6. Pricing Toggle (Monthly vs. Yearly with 20% discount)
  const monthBtn = document.querySelector(".pr-seg-month");
  const yearBtn = document.querySelector(".pr-seg-year");
  const proCard = document.querySelector(".pr-card-pro");
  const maxCard = document.querySelector(".pr-card-max");

  function setPricingMode(isYearly) {
    if (!monthBtn || !yearBtn) return;

    if (isYearly) {
      monthBtn.classList.remove("on");
      monthBtn.setAttribute("aria-selected", "false");
      yearBtn.classList.add("on");
      yearBtn.setAttribute("aria-selected", "true");

      if (proCard) {
        const slot = proCard.querySelector(".pr-price-slot");
        if (slot) slot.innerHTML = '<span class="pr-price-col"><span class="pr-price-char">$</span></span><span class="pr-price-col"><span class="pr-price-char">1</span></span><span class="pr-price-col"><span class="pr-price-char">6</span></span>';
        const note = proCard.querySelector(".pr-price-note");
        if (note) note.textContent = "per month, billed annually ($192/yr)";
      }

      if (maxCard) {
        const slot = maxCard.querySelector(".pr-price-slot");
        if (slot) slot.innerHTML = '<span class="pr-price-col"><span class="pr-price-char">$</span></span><span class="pr-price-col"><span class="pr-price-char">8</span></span><span class="pr-price-col"><span class="pr-price-char">0</span></span>';
        const note = maxCard.querySelector(".pr-price-note");
        if (note) note.textContent = "per month, billed annually ($960/yr)";
      }
    } else {
      yearBtn.classList.remove("on");
      yearBtn.setAttribute("aria-selected", "false");
      monthBtn.classList.add("on");
      monthBtn.setAttribute("aria-selected", "true");

      if (proCard) {
        const slot = proCard.querySelector(".pr-price-slot");
        if (slot) slot.innerHTML = '<span class="pr-price-col"><span class="pr-price-char">$</span></span><span class="pr-price-col"><span class="pr-price-char">2</span></span><span class="pr-price-col"><span class="pr-price-char">0</span></span>';
        const note = proCard.querySelector(".pr-price-note");
        if (note) note.textContent = "per month, billed monthly";
      }

      if (maxCard) {
        const slot = maxCard.querySelector(".pr-price-slot");
        if (slot) slot.innerHTML = '<span class="pr-price-col"><span class="pr-price-char">$</span></span><span class="pr-price-col"><span class="pr-price-char">1</span></span><span class="pr-price-col"><span class="pr-price-char">0</span></span><span class="pr-price-col"><span class="pr-price-char">0</span></span>';
        const note = maxCard.querySelector(".pr-price-note");
        if (note) note.textContent = "per month, billed monthly";
      }
    }
  }

  if (monthBtn && yearBtn) {
    monthBtn.addEventListener("click", () => setPricingMode(false));
    yearBtn.addEventListener("click", () => setPricingMode(true));
  }

  // 7. Scroll Reveal Observer
  const revealElements = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("rv-in");
            entry.target.style.opacity = "1";
            entry.target.style.transform = "none";
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.1 }
    );
    revealElements.forEach((el) => observer.observe(el));
  } else {
    revealElements.forEach((el) => {
      el.classList.add("rv-in");
      el.style.opacity = "1";
    });
  }

  // 8. Retro Window Controls (Close & Minimize)
  const winWraps = document.querySelectorAll(".win-wrap");
  winWraps.forEach((win) => {
    const closeBtn = win.querySelector(".dot.close");
    if (closeBtn) {
      closeBtn.style.cursor = "pointer";
      closeBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        win.style.transition = "transform 0.25s ease, opacity 0.25s ease";
        win.style.transform = "scale(0.85) translateY(-8px)";
        win.style.opacity = "0";
        setTimeout(() => {
          win.style.display = "none";
        }, 250);
      });
    }

    const minBtn = win.querySelector(".dot.min");
    if (minBtn) {
      minBtn.style.cursor = "pointer";
      minBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        const content = win.querySelector(".screen, .showcase-body");
        if (content) {
          content.style.display = content.style.display === "none" ? "flex" : "none";
        }
      });
    }
  });

  // 9. Pricing Starry Sky Canvas Animation
  const canvas = document.querySelector(".pricing-sky");
  if (canvas && canvas.getContext) {
    const ctx = canvas.getContext("2d");
    let width = (canvas.width = canvas.parentElement.offsetWidth || window.innerWidth);
    let height = (canvas.height = canvas.parentElement.offsetHeight || 600);

    const stars = Array.from({ length: 65 }, () => ({
      x: Math.random() * width,
      y: Math.random() * height,
      size: Math.random() * 1.8 + 0.4,
      alpha: Math.random(),
      speed: Math.random() * 0.015 + 0.005,
    }));

    function drawSky() {
      ctx.clearRect(0, 0, width, height);
      stars.forEach((star) => {
        star.alpha += star.speed;
        if (star.alpha > 1 || star.alpha < 0) star.speed = -star.speed;
        ctx.fillStyle = `rgba(255, 255, 255, ${Math.abs(star.alpha)})`;
        ctx.beginPath();
        ctx.arc(star.x, star.y, star.size, 0, Math.PI * 2);
        ctx.fill();
      });
      requestAnimationFrame(drawSky);
    }
    drawSky();

    window.addEventListener("resize", () => {
      width = canvas.width = canvas.parentElement.offsetWidth || window.innerWidth;
      height = canvas.height = canvas.parentElement.offsetHeight || 600;
    });
  }

  
  // 10. Showcase Hero Video Controls
  const heroVideo = document.getElementById("zukiHeroVideo");
  const playPauseBtn = document.getElementById("playPauseBtn");
  const muteToggleBtn = document.getElementById("muteToggleBtn");
  const fsBtn = document.getElementById("fsBtn");
  const heroVideoZoomBtn = document.getElementById("heroVideoZoomBtn");
  const vidProgress = document.getElementById("vidProgress");
  const vidTimeline = document.getElementById("vidTimeline");

  if (heroVideo) {
    // Autoplay fallback
    heroVideo.play().catch(() => {
      heroVideo.muted = true;
      heroVideo.play().catch(() => {});
    });

    if (playPauseBtn) {
      const playIcon = playPauseBtn.querySelector(".icon-play");
      const pauseIcon = playPauseBtn.querySelector(".icon-pause");
      playPauseBtn.addEventListener("click", () => {
        if (heroVideo.paused) {
          heroVideo.play();
          if (playIcon) playIcon.style.display = "none";
          if (pauseIcon) pauseIcon.style.display = "inline";
        } else {
          heroVideo.pause();
          if (playIcon) playIcon.style.display = "inline";
          if (pauseIcon) pauseIcon.style.display = "none";
        }
      });
    }

    if (muteToggleBtn) {
      const muteIcon = muteToggleBtn.querySelector(".icon-muted");
      const soundIcon = muteToggleBtn.querySelector(".icon-sound");
      muteToggleBtn.addEventListener("click", () => {
        heroVideo.muted = !heroVideo.muted;
        if (heroVideo.muted) {
          if (muteIcon) muteIcon.style.display = "inline";
          if (soundIcon) soundIcon.style.display = "none";
        } else {
          if (muteIcon) muteIcon.style.display = "none";
          if (soundIcon) soundIcon.style.display = "inline";
        }
      });
    }

    function toggleFullscreen() {
      if (heroVideo.requestFullscreen) {
        heroVideo.requestFullscreen();
      } else if (heroVideo.webkitRequestFullscreen) {
        heroVideo.webkitRequestFullscreen();
      }
    }

    if (fsBtn) fsBtn.addEventListener("click", toggleFullscreen);
    if (heroVideoZoomBtn) heroVideoZoomBtn.addEventListener("click", toggleFullscreen);

    if (vidProgress) {
      heroVideo.addEventListener("timeupdate", () => {
        if (heroVideo.duration) {
          const pct = (heroVideo.currentTime / heroVideo.duration) * 100;
          vidProgress.style.width = pct + "%";
        }
      });
    }

    if (vidTimeline) {
      vidTimeline.addEventListener("click", (e) => {
        const rect = vidTimeline.getBoundingClientRect();
        const clickX = e.clientX - rect.left;
        const pct = Math.max(0, Math.min(1, clickX / rect.width));
        if (heroVideo.duration) {
          heroVideo.currentTime = pct * heroVideo.duration;
        }
      });
    }
  }

  console.log("Zuki Orange Edition initialized successfully!");
});
