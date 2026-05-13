// Router de tabs y utilidades globales

const TABS = ["chat", "temas", "notas", "flashcards", "dashboard"];

document.querySelectorAll("nav button").forEach(btn => {
  btn.addEventListener("click", () => cambiarTab(btn.dataset.tab));
});

function cambiarTab(nombre) {
  document.querySelectorAll("nav button").forEach(b =>
    b.classList.toggle("active", b.dataset.tab === nombre)
  );
  document.querySelectorAll(".section").forEach(s =>
    s.classList.toggle("active", s.id === `tab-${nombre}`)
  );
  if (nombre === "temas")      cargarTemas();
  if (nombre === "notas")      cargarNotas();
  if (nombre === "flashcards") cargarFlashcards();
  if (nombre === "dashboard")  cargarDashboard();
}

// ── API helper ─────────────────────────────────────────────────
async function api(metodo, ruta, body = null) {
  const opts = {
    method: metodo,
    headers: { "Content-Type": "application/json" },
  };
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

async function cargarTopics() {
  _topics = await api("GET", "/topics");
  _poblarSelects();
}

function _poblarSelects() {
  const ids = ["chat-topic", "notas-filtro-topic", "fc-filtro-topic", "mn-topic", "mc-topic"];
  ids.forEach(id => {
    const sel = document.getElementById(id);
    if (!sel) return;
    const conTodos = ["chat-topic", "notas-filtro-topic", "fc-filtro-topic"].includes(id);
    const valorActual = sel.value;
    sel.innerHTML = conTodos ? '<option value="">— Sin filtro —</option>' : '<option value="">— Sin tema —</option>';
    _topics.forEach(t => {
      const opt = document.createElement("option");
      opt.value = t.id;
      opt.textContent = t.nombre;
      sel.appendChild(opt);
    });
    if (valorActual) sel.value = valorActual;
  });
}

// Inicialización
cargarTopics();
