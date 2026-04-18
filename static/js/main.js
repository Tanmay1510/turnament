// Tournament Manager - Main JavaScript

// — Custom Cursor Trail —
(function () {
  const dot = document.getElementById("cursor-dot");
  const ring = document.getElementById("cursor-ring");
  if (!dot || !ring) return;
  let mx = 0,
    my = 0,
    rx = 0,
    ry = 0;

  document.addEventListener("mousemove", (e) => {
    mx = e.clientX;
    my = e.clientY;
    dot.style.left = mx - 4 + "px";
    dot.style.top = my - 4 + "px";
    dot.style.opacity = "1";
    ring.style.opacity = "1";
  });

  function followCursor() {
    rx += (mx - rx - 16) * 0.12;
    ry += (my - ry - 16) * 0.12;
    ring.style.left = rx + "px";
    ring.style.top = ry + "px";
    requestAnimationFrame(followCursor);
  }
  followCursor();

  document.addEventListener("mouseover", (e) => {
    if (
      e.target.closest(
        "a, button, .glass-hover, .hover-lift, .tilt-3d, [onclick]",
      )
    ) {
      ring.style.width = "48px";
      ring.style.height = "48px";
      ring.style.borderColor = "rgba(232,121,249,0.5)";
      dot.style.background = "rgba(232,121,249,0.8)";
    }
  });

  document.addEventListener("mouseout", (e) => {
    if (
      e.target.closest(
        "a, button, .glass-hover, .hover-lift, .tilt-3d, [onclick]",
      )
    ) {
      ring.style.width = "32px";
      ring.style.height = "32px";
      ring.style.borderColor = "rgba(244,114,182,0.3)";
      dot.style.background = "rgba(244,114,182,0.6)";
    }
  });
})();

// Toast Notifications
function showToast(message, type = "success") {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.innerHTML = `${type === "success" ? "✔" : "✖"} ${message}`;

  container.appendChild(toast);

  setTimeout(() => {
    toast.classList.add("fade-out");
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

// API Helper
async function apiCall(url, method = "GET", data = null) {
  const opts = {
    method,
    headers: { "Content-Type": "application/json" },
  };
  if (data) opts.body = JSON.stringify(data);

  const res = await fetch(url, opts);
  const json = await res.json();
  if (!res.ok) throw new Error(json.error || "Request failed");
  return json;
}

// — Page Load Animations —
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".animate-in").forEach((el, i) => {
    if (!el.style.getPropertyValue("--delay")) {
      el.style.setProperty("--delay", i);
    }
    setTimeout(() => el.classList.add("show"), 80);
  });

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("show");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.1, rootMargin: "0px 0px -50px 0px" },
  );

  document
    .querySelectorAll(".scroll-animate")
    .forEach((el) => observer.observe(el));

  const scrollRevealObs = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("visible");
          scrollRevealObs.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.12, rootMargin: "0px 0px -80px 0px" },
  );

  document
    .querySelectorAll(".scroll-rotate-in, .scroll-flip-in, .scroll-zoom-rotate")
    .forEach((el) => scrollRevealObs.observe(el));

  document.querySelectorAll(".count-up").forEach((el) => {
    const target = parseInt(el.textContent) || 0;
    if (target === 0) return;
    el.textContent = "0";

    const obs = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        obs.disconnect();
        let current = 0;
        const step = Math.max(1, Math.floor(target / 40));
        const interval = setInterval(() => {
          current += step;
          if (current >= target) {
            current = target;
            clearInterval(interval);
          }
          el.textContent = current;
        }, 30);
      }
    });
    obs.observe(el);
  });

  document.querySelectorAll(".tilt-3d").forEach((card) => {
    card.addEventListener("mousemove", (e) => {
      const rect = card.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const centerX = rect.width / 2;
      const centerY = rect.height / 2;
      const rotateX = ((y - centerY) / centerY) * -8;
      const rotateY = ((x - centerX) / centerX) * 8;
      card.style.transform = `perspective(800px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) scale(1.02)`;
    });

    card.addEventListener("mouseleave", () => {
      card.style.transform =
        "perspective(800px) rotateX(0) rotateY(0) scale(1)";
    });
  });

  document.querySelectorAll(".btn-primary, .btn-secondary").forEach((btn) => {
    btn.style.position = "relative";
    btn.style.overflow = "hidden";

    btn.addEventListener("click", (e) => {
      const rect = btn.getBoundingClientRect();
      const ripple = document.createElement("span");
      const size = Math.max(rect.width, rect.height);

      ripple.style.cssText = `
position:absolute;
border-radius:50%;
background:rgba(255,255,255,0.3);
width:${size}px;
height:${size}px;
left:${e.clientX - rect.left - size / 2}px;
top:${e.clientY - rect.top - size / 2}px;
transform:scale(0);
animation:ripple 0.6s ease-out;
pointer-events:none;
`;

      btn.appendChild(ripple);
      setTimeout(() => ripple.remove(), 600);
    });
  });

  const orbs = document.querySelectorAll(".parallax-orb");
  if (orbs.length) {
    window.addEventListener("scroll", () => {
      const y = window.scrollY;
      orbs.forEach((orb, i) => {
        const speed = (i + 1) * 0.05;
        orb.style.transform = `translateY(${y * speed}px)`;
      });
    });
  }

  document.querySelectorAll(".magnetic").forEach((el) => {
    el.addEventListener("mousemove", (e) => {
      const rect = el.getBoundingClientRect();
      const x = e.clientX - rect.left - rect.width / 2;
      const y = e.clientY - rect.top - rect.height / 2;
      el.style.transform = `translate(${x * 0.2}px, ${y * 0.2}px)`;
    });

    el.addEventListener("mouseleave", () => {
      el.style.transform = "translate(0, 0)";
      el.style.transition = "transform 0.3s ease";
    });

    el.addEventListener("mouseenter", () => {
      el.style.transition = "none";
    });
  });

  document.querySelectorAll(".typewriter").forEach((el) => {
    const text = el.textContent;
    el.textContent = "";
    el.style.visibility = "visible";
    let i = 0;

    const type = () => {
      if (i < text.length) {
        el.textContent += text[i];
        i++;
        setTimeout(type, 60);
      }
    };

    const obs = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        obs.disconnect();
        type();
      }
    });
    obs.observe(el);
  });

  document.querySelectorAll(".spotlight").forEach((card) => {
    card.addEventListener("mousemove", (e) => {
      const rect = card.getBoundingClientRect();
      const before = card.querySelector(".spotlight-inner") || card;
      before.style.setProperty("--spot-x", e.clientX - rect.left + "px");
      before.style.setProperty("--spot-y", e.clientY - rect.top + "px");
    });

    card.addEventListener("mouseleave", () => {
      card.style.background = "";
    });
  });

  document.querySelectorAll(".stagger-children").forEach((container) => {
    container.addEventListener("mouseenter", () => {
      container.querySelectorAll(".stagger-child").forEach((child, i) => {
        child.style.transitionDelay = i * 0.05 + "s";
        child.classList.add("stagger-active");
      });
    });

    container.addEventListener("mouseleave", () => {
      container.querySelectorAll(".stagger-child").forEach((child) => {
        child.style.transitionDelay = "0s";
        child.classList.remove("stagger-active");
      });
    });
  });

  window.confettiBurst = function (x, y) {
    const colors = [
      "#f472b6",
      "#e879f9",
      "#fb7185",
      "#fbbf24",
      "#f9a8d4",
      "#fda4af",
    ];

    for (let i = 0; i < 30; i++) {
      const particle = document.createElement("div");
      const color = colors[Math.floor(Math.random() * colors.length)];
      const angle = (Math.random() * 360 * Math.PI) / 180;
      const velocity = 100 + Math.random() * 200;
      const dx = Math.cos(angle) * velocity;
      const dy = Math.sin(angle) * velocity;

      particle.style.cssText = `
position:fixed;
left:${x}px;
top:${y}px;
width:${4 + Math.random() * 4}px;
height:${4 + Math.random() * 4}px;
background:${color};
border-radius:${Math.random() > 0.5 ? "50%" : "2px"};
pointer-events:none;
z-index:999999;
transition:all ${0.6 + Math.random() * 0.8}s cubic-bezier(.25,.46,.45,.94);
`;

      document.body.appendChild(particle);

      requestAnimationFrame(() => {
        particle.style.transform = `translate(${dx}px, ${dy}px) rotate(${Math.random() * 720}deg)`;
        particle.style.opacity = "0";
      });

      setTimeout(() => particle.remove(), 1500);
    }
  };

  // Mobile Menu Toggle
  function toggleMobileMenu() {
    const menu = document.getElementById("mobile-menu");
    if (!menu) return;

    if (menu.style.maxHeight === "0px" || !menu.style.maxHeight) {
      menu.style.maxHeight = menu.scrollHeight + "px";
    } else {
      menu.style.maxHeight = "0px";
    }
  }

  // Admin Sidebar Toggle
  let sidebarCollapsed = false;
  function toggleSidebar() {
    const sidebar = document.getElementById("admin-sidebar");
    const main = document.getElementById("admin-main");
    const btn = sidebar?.querySelector("button");

    sidebarCollapsed = !sidebarCollapsed;

    if (sidebarCollapsed) {
      sidebar.style.width = "72px";
      if (main) main.style.marginLeft = "72px";
      sidebar.querySelectorAll(".sidebar-text").forEach((el) => {
        el.style.opacity = "0";
        el.style.display = "none";
      });
      if (btn) btn.textContent = ">";
    } else {
      sidebar.style.width = "260px";
      if (main) main.style.marginLeft = "260px";
      sidebar.querySelectorAll(".sidebar-text").forEach((el) => {
        el.style.display = "block";
        setTimeout(() => (el.style.opacity = "1"), 100);
      });
    }
  }

  // Toast Notifications
  function showToast(message, type = "success") {
    const container = document.getElementById("toast-container");
    if (!container) return;

    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.innerHTML = `${type === "success" ? "✔" : "✖"} ${message}`;

    container.appendChild(toast);

    setTimeout(() => {
      toast.classList.add("fade-out");
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }

  // API Helper
  async function apiCall(url, method = "GET", data = null) {
    const opts = {
      method,
      headers: { "Content-Type": "application/json" },
    };
    if (data) opts.body = JSON.stringify(data);

    const res = await fetch(url, opts);
    const json = await res.json();
    if (!res.ok) throw new Error(json.error || "Request failed");
    return json;
  }

  // Score Animation
  function animateScore(element) {
    element.classList.remove("anim-score-flash");
    void element.offsetWidth;
    element.classList.add("anim-score-flash");
  }

  // Create Particles
  function createParticles(container, count = 8) {
    for (let i = 0; i < count; i++) {
      const particle = document.createElement("div");
      particle.className = "particle";
      particle.style.top = 15 + Math.random() * 70 + "%";
      particle.style.left = 5 + Math.random() * 90 + "%";
      particle.style.animationDelay = Math.random() * 4 + "s";
      particle.style.animationDuration = 3 + Math.random() * 3 + "s";
      particle.style.width = 2 + Math.random() * 3 + "px";
      particle.style.height = particle.style.width;
      container.appendChild(particle);
    }
  }

  // Form Submit with AJAX
  function ajaxSubmit(formId, url, method, onSuccess) {
    const form = document.getElementById(formId);
    if (!form) return;

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const formData = new FormData(form);
      const data = Object.fromEntries(formData.entries());

      try {
        const result = await apiCall(url, method, data);
        showToast(onSuccess || "Success!");
        if (typeof window.onFormSuccess === "function")
          window.onFormSuccess(result);
        else location.reload();
      } catch (err) {
        showToast(err.message, "error");
      }
    });
  }
});
