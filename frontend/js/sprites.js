// ── Sprites de agentes — drag & click ────────────────────────────

(function () {
  const SNAP_THRESHOLD = 60; // px desde el sidebar para volver a anclarse

  function iniciarSprites() {
    const wraps = document.querySelectorAll(".sprite-wrap");
    wraps.forEach(wrap => {
      wrap.addEventListener("mousedown",  e => iniciarDrag(e, wrap));
      wrap.addEventListener("touchstart", e => iniciarDrag(e, wrap), { passive: false });
      wrap.addEventListener("click", e => {
        if (!wrap._dragged) navegarAgente(wrap.dataset.tab);
      });
    });
    actualizarActivo(document.querySelector(".nav-item.active")?.dataset.tab);
  }

  function navegarAgente(tab) {
    if (!tab) return;
    const btn = document.querySelector(`.nav-item[data-tab="${tab}"]`);
    if (btn) btn.click();
  }

  function actualizarActivo(tabActual) {
    document.querySelectorAll(".sprite-wrap, .sprite-floating").forEach(el => {
      el.classList.toggle("active-agent", el.dataset.tab === tabActual);
    });
  }

  // Escuchar cambios de tab para resaltar el agente activo
  document.addEventListener("tabchange", e => actualizarActivo(e.detail));

  function iniciarDrag(e, wrap) {
    e.preventDefault();
    wrap._dragged = false;

    const isTouch = e.type === "touchstart";
    const startPos = isTouch ? e.touches[0] : e;
    const startX = startPos.clientX;
    const startY = startPos.clientY;

    let flotante = null;
    let movido = false;

    function onMove(ev) {
      const pos = isTouch ? ev.touches[0] : ev;
      const dx = Math.abs(pos.clientX - startX);
      const dy = Math.abs(pos.clientY - startY);

      if (!movido && dx < 4 && dy < 4) return;
      movido = true;
      wrap._dragged = true;

      if (!flotante) flotante = crearFlotante(wrap, pos.clientX, pos.clientY);

      flotante.style.left = (pos.clientX - flotante._ox) + "px";
      flotante.style.top  = (pos.clientY - flotante._oy) + "px";
    }

    function onUp(ev) {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup",   onUp);
      document.removeEventListener("touchmove", onMove);
      document.removeEventListener("touchend",  onUp);

      if (!flotante) {
        // fue un click sin arrastre
        setTimeout(() => { wrap._dragged = false; }, 10);
        return;
      }

      const pos = isTouch ? ev.changedTouches[0] : ev;
      const sidebar = document.getElementById("sidebar");
      const rect = sidebar.getBoundingClientRect();

      if (pos.clientX < rect.right + SNAP_THRESHOLD) {
        // vuelve al sidebar
        flotante.remove();
        flotante = null;
      } else {
        // queda flotando — hacerlo permanente con doble-click para volver
        flotante.title = "Doble clic para volver al sidebar";
        flotante.addEventListener("dblclick", () => flotante.remove());
        flotante.addEventListener("mousedown",  ev2 => arrastrarFlotante(ev2, flotante));
        flotante.addEventListener("touchstart", ev2 => arrastrarFlotante(ev2, flotante), { passive: false });
        flotante.addEventListener("click", () => {
          if (!flotante._dragged) navegarAgente(flotante.dataset.tab);
        });
      }
      setTimeout(() => { wrap._dragged = false; }, 10);
    }

    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup",   onUp);
    document.addEventListener("touchmove", onMove, { passive: false });
    document.addEventListener("touchend",  onUp);
  }

  function crearFlotante(wrap, cx, cy) {
    const img   = wrap.querySelector(".sprite-img");
    const label = wrap.querySelector(".sprite-label");
    const rect  = wrap.getBoundingClientRect();

    const el = document.createElement("div");
    el.className  = "sprite-floating";
    el.dataset.tab    = wrap.dataset.tab;
    el.dataset.nombre = wrap.dataset.nombre;
    el._dragged = false;

    const imgEl = document.createElement("img");
    imgEl.src       = img.src;
    imgEl.alt       = img.alt;
    imgEl.className = "sprite-img";

    const lblEl = document.createElement("span");
    lblEl.className   = "sprite-label";
    lblEl.textContent = label?.textContent || wrap.dataset.nombre;

    el.appendChild(imgEl);
    el.appendChild(lblEl);

    el._ox = cx - rect.left;
    el._oy = cy - rect.top;
    el.style.left = (cx - el._ox) + "px";
    el.style.top  = (cy - el._oy) + "px";

    document.body.appendChild(el);
    return el;
  }

  function arrastrarFlotante(e, flotante) {
    e.preventDefault();
    flotante._dragged = false;
    const isTouch = e.type === "touchstart";
    const pos0 = isTouch ? e.touches[0] : e;
    const ox = pos0.clientX - flotante.getBoundingClientRect().left;
    const oy = pos0.clientY - flotante.getBoundingClientRect().top;

    function onMove(ev) {
      flotante._dragged = true;
      const pos = isTouch ? ev.touches[0] : ev;
      flotante.style.left = (pos.clientX - ox) + "px";
      flotante.style.top  = (pos.clientY - oy) + "px";
    }
    function onUp() {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup",   onUp);
      document.removeEventListener("touchmove", onMove);
      document.removeEventListener("touchend",  onUp);
      setTimeout(() => { flotante._dragged = false; }, 10);
    }
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup",   onUp);
    document.addEventListener("touchmove", onMove, { passive: false });
    document.addEventListener("touchend",  onUp);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", iniciarSprites);
  } else {
    iniciarSprites();
  }
})();
