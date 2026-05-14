// Router de tabs, sidebar y utilidades globales

const TABS = ["chat", "temas", "notas", "flashcards", "documentos", "plan", "dashboard"];

// ── Sidebar toggle ──────────────────────────────────────────────
const sidebar       = document.getElementById("sidebar");
const sidebarToggle = document.getElementById("sidebar-toggle");

function _aplicarEstadoSidebar(colapsado) {
  sidebar.classList.toggle("collapsed", colapsado);
  sidebarToggle.textContent = colapsado ? "›" : "‹";
  sidebarToggle.title       = colapsado ? "Expandir menú" : "Colapsar menú";
  // Ocultar fallback del avatar cuando hay imagen
  const img = sidebar.querySelector(".brand-avatar img");
  const fallback = document.getElementById("brand-avatar-fallback");
  if (img && fallback) {
    img.onload  = () => { fallback.style.display = "none"; };
    img.onerror = () => { img.style.display = "none"; fallback.style.display = ""; };
  }
}

sidebarToggle.addEventListener("click", () => {
  const colapsado = !sidebar.classList.contains("collapsed");
  localStorage.setItem("sidebar-colapsado", colapsado);
  _aplicarEstadoSidebar(colapsado);
});

// Restaurar estado guardado
const _guardado = localStorage.getItem("sidebar-colapsado") === "true";
_aplicarEstadoSidebar(_guardado);

// ── Cambio de tabs ─────────────────────────────────────────────
document.querySelectorAll(".nav-item[data-tab]").forEach(btn => {
  btn.addEventListener("click", () => cambiarTab(btn.dataset.tab));
});

function cambiarTab(nombre) {
  document.querySelectorAll(".nav-item[data-tab]").forEach(b =>
    b.classList.toggle("active", b.dataset.tab === nombre)
  );
  document.querySelectorAll(".section").forEach(s =>
    s.classList.toggle("active", s.id === `tab-${nombre}`)
  );
  if (nombre === "temas")      cargarTemas();
  if (nombre === "notas")      cargarNotas();
  if (nombre === "flashcards") cargarFlashcards();
  if (nombre === "documentos") cargarDocumentos();
  if (nombre === "dashboard")  cargarDashboard();

  // En móvil, cerrar sidebar al navegar
  if (window.innerWidth < 640) _aplicarEstadoSidebar(true);
}

// ── API helper ─────────────────────────────────────────────────
async function api(metodo, ruta, body = null) {
  const opts = { method: metodo, headers: { "Content-Type": "application/json" } };
  if (body !== null) opts.body = JSON.stringify(body);
  const r = await fetch(ruta, opts);
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  if (r.status === 204) return null;
  return r.json();
}

// ── Toast ───────────────────────────────────────────────────────
let _toastTimer;
function toast(msg, ms = 2500) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => el.classList.remove("show"), ms);
}

// ── Topics: cache compartido ────────────────────────────────────
let _topics = [];
let _arbol  = [];

async function cargarTopics() {
  [_topics, _arbol] = await Promise.all([
    api("GET", "/topics"),
    api("GET", "/topics/arbol"),
  ]);
  _poblarSelects();
}

function _poblarSelects() {
  const todosIds = [
    "chat-topic", "notas-filtro-topic", "fc-filtro-topic",
    "docs-filtro-topic", "mn-topic", "mc-topic",
  ];
  const esFiltro = new Set([
    "chat-topic", "notas-filtro-topic", "fc-filtro-topic", "docs-filtro-topic",
  ]);

  todosIds.forEach(id => {
    const sel = document.getElementById(id);
    if (!sel) return;
    const val = sel.value;
    sel.innerHTML = esFiltro.has(id)
      ? '<option value="">— Sin filtro —</option>'
      : '<option value="">— Sin tema —</option>';

    _arbol.forEach(curso => {
      const bloques = curso.bloques || [];
      if (!bloques.length) {
        const opt = document.createElement("option");
        opt.value = curso.id;
        opt.textContent = curso.nombre;
        sel.appendChild(opt);
        return;
      }
      bloques.forEach(bloque => {
        const temas = bloque.temas || [];
        const grp   = document.createElement("optgroup");
        grp.label   = `${curso.nombre} › ${bloque.nombre}`;
        if (!temas.length) {
          const opt = document.createElement("option");
          opt.value = bloque.id;
          opt.textContent = bloque.nombre;
          grp.appendChild(opt);
        } else {
          temas.forEach(t => {
            const opt = document.createElement("option");
            opt.value = t.id;
            opt.textContent = t.nombre;
            grp.appendChild(opt);
          });
        }
        sel.appendChild(grp);
      });
    });

    if (val) sel.value = val;
  });
}

// Inicialización
cargarTopics();
