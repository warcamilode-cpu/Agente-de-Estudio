// Router de tabs, sidebar y utilidades globales

const TABS = ["chat", "cuaderno", "flashcards", "documentos", "plan", "dashboard"];

// ── Sidebar toggle ──────────────────────────────────────────────
const sidebar       = document.getElementById("sidebar");
const sidebarToggle = document.getElementById("sidebar-toggle");

function _aplicarEstadoSidebar(colapsado) {
  sidebar.classList.toggle("collapsed", colapsado);
  sidebarToggle.textContent = colapsado ? "›" : "‹";
  sidebarToggle.title       = colapsado ? "Expandir menú" : "Colapsar menú";
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
  if (nombre === "cuaderno")   cargarCuaderno();
  if (nombre === "flashcards") cargarFlashcards();
  if (nombre === "documentos") cargarDocumentos();
  if (nombre === "dashboard")  cargarDashboard();

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

// ── Estructura: cache compartido (programas → semestres → materias)
let _estructura = [];   // [{id, nombre, tipo, semestres: [{id, nombre, materias: [...]}]}]
let _materias   = [];   // lista plana de todas las materias

async function cargarEstructura() {
  try {
    _estructura = await api("GET", "/cuaderno/estructura");
    _materias = _estructura.flatMap(p =>
      (p.semestres || []).flatMap(s => s.materias || [])
    );
  } catch {
    _estructura = [];
    _materias = [];
  }
  _poblarSelects();
}

function _poblarSelects() {
  const filtroIds = ["chat-materia", "fc-filtro-materia", "docs-filtro-materia"];
  const modalIds  = ["mc-materia", "docs-materia"];

  filtroIds.forEach(id => {
    const sel = document.getElementById(id);
    if (!sel) return;
    const val = sel.value;
    sel.innerHTML = '<option value="">— Sin filtro —</option>';
    _poblarOpcionesMaterias(sel);
    if (val) sel.value = val;
  });

  modalIds.forEach(id => {
    const sel = document.getElementById(id);
    if (!sel) return;
    const val = sel.value;
    sel.innerHTML = '<option value="">— Sin materia —</option>';
    _poblarOpcionesMaterias(sel);
    if (val) sel.value = val;
  });
}

function _poblarOpcionesMaterias(sel) {
  _estructura.forEach(prog => {
    (prog.semestres || []).forEach(sem => {
      const mats = sem.materias || [];
      if (!mats.length) return;
      const grp = document.createElement("optgroup");
      grp.label = `${prog.nombre} › ${sem.nombre}`;
      mats.forEach(m => {
        const opt = document.createElement("option");
        opt.value = m.id;
        opt.textContent = `${m.emoji || "📚"} ${m.nombre}`;
        grp.appendChild(opt);
      });
      sel.appendChild(grp);
    });
  });
}

// Inicialización
cargarEstructura();
