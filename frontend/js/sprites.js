// ── Sprites de agentes — movimiento libre + drag ─────────────────

(function () {
  const SPRITE_W    = 52;
  const SPRITE_H    = 58;   // img 40px + label ~12px + padding
  const SPEED_MIN   = 0.4;
  const SPEED_MAX   = 1.1;
  const BOUNCE_DAMP = 1.0;  // sin pérdida de velocidad al rebotar

  const agentes = [];
  let animFrame = null;
  let paused    = false;

  function rand(min, max) { return min + Math.random() * (max - min); }
  function randSpeed()    { return rand(SPEED_MIN, SPEED_MAX) * (Math.random() < .5 ? 1 : -1); }

  function iniciarSprites() {
    const contenedor = document.getElementById("agentes-sprites");
    if (!contenedor) return;

    const wraps = contenedor.querySelectorAll(".sprite-wrap");
    wraps.forEach((wrap, i) => {
      const bounds = contenedor.getBoundingClientRect();
      const maxX   = Math.max(0, bounds.width  - SPRITE_W);
      const maxY   = Math.max(0, bounds.height - SPRITE_H);

      const agente = {
        el:   wrap,
        img:  wrap.querySelector(".sprite-img"),
        x:    rand(0, maxX || 10),
        y:    rand(0, maxY || 10),
        vx:   randSpeed(),
        vy:   randSpeed(),
        tab:  wrap.dataset.tab,
        dragging: false,
      };

      wrap.style.left = agente.x + "px";
      wrap.style.top  = agente.y + "px";

      wrap.addEventListener("mousedown",  e => iniciarDrag(e, agente, contenedor));
      wrap.addEventListener("touchstart", e => iniciarDrag(e, agente, contenedor), { passive: false });
      wrap.addEventListener("click", () => {
        if (!agente._dragged) navegarAgente(agente.tab);
      });

      agentes.push(agente);
    });

    actualizarActivo(document.querySelector(".nav-item.active")?.dataset.tab);
    iniciarLoop(contenedor);
    iniciarResize();
  }

  // ── Loop de movimiento ───────────────────────────────────────────
  function iniciarLoop(contenedor) {
    function tick() {
      if (!paused) moverTodos(contenedor);
      animFrame = requestAnimationFrame(tick);
    }
    animFrame = requestAnimationFrame(tick);
  }

  function moverTodos(contenedor) {
    const bounds = contenedor.getBoundingClientRect();
    const maxX   = bounds.width  - SPRITE_W;
    const maxY   = bounds.height - SPRITE_H;

    agentes.forEach(a => {
      if (a.dragging) return;

      a.x += a.vx;
      a.y += a.vy;

      // Rebotar en paredes X
      if (a.x <= 0)         { a.x = 0;    a.vx =  Math.abs(a.vx) * BOUNCE_DAMP; }
      if (a.x >= maxX)      { a.x = maxX; a.vx = -Math.abs(a.vx) * BOUNCE_DAMP; }

      // Rebotar en paredes Y
      if (a.y <= 0)         { a.y = 0;    a.vy =  Math.abs(a.vy) * BOUNCE_DAMP; }
      if (a.y >= maxY)      { a.y = maxY; a.vy = -Math.abs(a.vy) * BOUNCE_DAMP; }

      a.el.style.left = a.x + "px";
      a.el.style.top  = a.y + "px";

      // Voltear imagen según dirección horizontal
      if (a.img) {
        a.img.style.transform = a.vx < 0 ? "scaleX(-1)" : "scaleX(1)";
      }
    });
  }

  // ── Drag dentro del contenedor ──────────────────────────────────
  function iniciarDrag(e, agente, contenedor) {
    e.preventDefault();
    agente._dragged  = false;
    agente.dragging  = true;
    paused = false;

    const isTouch  = e.type === "touchstart";
    const pos0     = isTouch ? e.touches[0] : e;
    const rect     = contenedor.getBoundingClientRect();
    const offsetX  = pos0.clientX - rect.left - agente.x;
    const offsetY  = pos0.clientY - rect.top  - agente.y;

    let lastX = agente.x, lastY = agente.y;
    let lastT = performance.now();

    function onMove(ev) {
      agente._dragged = true;
      const pos  = isTouch ? ev.touches[0] : ev;
      const nowT = performance.now();
      const newX = Math.max(0, Math.min(rect.width  - SPRITE_W, pos.clientX - rect.left - offsetX));
      const newY = Math.max(0, Math.min(rect.height - SPRITE_H, pos.clientY - rect.top  - offsetY));

      const dt = Math.max(1, nowT - lastT);
      agente.vx = (newX - lastX) / dt * 16;
      agente.vy = (newY - lastY) / dt * 16;
      lastX = newX; lastY = newY; lastT = nowT;

      agente.x = newX;
      agente.y = newY;
      agente.el.style.left = newX + "px";
      agente.el.style.top  = newY + "px";
    }

    function onUp() {
      agente.dragging = false;
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup",   onUp);
      document.removeEventListener("touchmove", onMove);
      document.removeEventListener("touchend",  onUp);

      // Limitar velocidad al soltar
      const maxV = SPEED_MAX * 2.5;
      agente.vx = Math.max(-maxV, Math.min(maxV, agente.vx));
      agente.vy = Math.max(-maxV, Math.min(maxV, agente.vy));
      if (Math.abs(agente.vx) < SPEED_MIN) agente.vx = SPEED_MIN * Math.sign(agente.vx || 1);
      if (Math.abs(agente.vy) < SPEED_MIN) agente.vy = SPEED_MIN * Math.sign(agente.vy || 1);

      setTimeout(() => { agente._dragged = false; }, 10);
    }

    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup",   onUp);
    document.addEventListener("touchmove", onMove, { passive: false });
    document.addEventListener("touchend",  onUp);
  }

  // ── Navegación y estado activo ───────────────────────────────────
  function navegarAgente(tab) {
    if (!tab) return;
    const btn = document.querySelector(`.nav-item[data-tab="${tab}"]`);
    if (btn) btn.click();
  }

  function actualizarActivo(tabActual) {
    agentes.forEach(a => a.el.classList.toggle("active-agent", a.tab === tabActual));
  }

  document.addEventListener("tabchange", e => actualizarActivo(e.detail));

  // ── Resize del panel ─────────────────────────────────────────────
  function iniciarResize() {
    const handle = document.getElementById("agentes-resize-handle");
    const panel  = document.getElementById("agentes-panel");
    if (!handle || !panel) return;

    const MIN_H = 88, MAX_H = 340;

    function doResize(startY, startH, getMoveY) {
      function onMove(ev) {
        const delta = startY - getMoveY(ev);
        panel.style.height = Math.min(MAX_H, Math.max(MIN_H, startH + delta)) + "px";
      }
      function onUp() {
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup",   onUp);
        document.removeEventListener("touchmove", onMove);
        document.removeEventListener("touchend",  onUp);
      }
      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup",   onUp);
      document.addEventListener("touchmove", onMove, { passive: false });
      document.addEventListener("touchend",  onUp);
    }

    handle.addEventListener("mousedown", e => {
      e.preventDefault();
      doResize(e.clientY, panel.getBoundingClientRect().height, ev => ev.clientY);
    });
    handle.addEventListener("touchstart", e => {
      e.preventDefault();
      doResize(e.touches[0].clientY, panel.getBoundingClientRect().height, ev => ev.touches[0].clientY);
    }, { passive: false });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", iniciarSprites);
  } else {
    iniciarSprites();
  }
})();
