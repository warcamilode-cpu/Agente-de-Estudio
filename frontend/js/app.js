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
let _topics = [];   // lista plana
let _arbol  = [];   // cursos con temas anidados

async function cargarTopics() {
  [_topics, _arbol] = await Promise.all([
    api("GET", "/topics"),
    api("GET", "/topics/arbol"),
  ]);
  _poblarSelects();
}

function _poblarSelects() {
  // Selects de filtro (chat, notas, flashcards): muestran todo agrupado
  const filtros = ["chat-topic", "notas-filtro-topic", "fc-filtro-topic"];
  filtros.forEach(id => {
    const sel = document.getElementById(id);
    if (!sel) return;
    const val = sel.value;
    sel.innerHTML = '<option value="">— Sin filtro —</option>';
    _arbol.forEach(curso => {
      if (curso.temas && curso.temas.length) {
        const grp = document.createElement("optgroup");
        grp.label = curso.nombre;
        curso.temas.forEach(t => {
          const opt = document.createElement("option");
          opt.value = t.id;
          opt.textContent = t.nombre;
          grp.appendChild(opt);
        });
        sel.appendChild(grp);
      } else {
        // Curso sin subtemas: aparece como opción directa
        const opt = document.createElement("option");
        opt.value = curso.id;
        opt.textContent = curso.nombre;
        sel.appendChild(opt);
      }
    });
    if (val) sel.value = val;
  });

  // Selects de modal (notas, flashcards): solo temas hoja para asignar
  const modales = ["mn-topic", "mc-topic"];
  modales.forEach(id => {
    const sel = document.getElementById(id);
    if (!sel) return;
    const val = sel.value;
    sel.innerHTML = '<option value="">— Sin tema —</option>';
    _arbol.forEach(curso => {
      if (curso.temas && curso.temas.length) {
        const grp = document.createElement("optgroup");
        grp.label = curso.nombre;
        curso.temas.forEach(t => {
          const opt = document.createElement("option");
          opt.value = t.id;
          opt.textContent = t.nombre;
          grp.appendChild(opt);
        });
        sel.appendChild(grp);
      } else {
        const opt = document.createElement("option");
        opt.value = curso.id;
        opt.textContent = curso.nombre;
        sel.appendChild(opt);
      }
    });
    if (val) sel.value = val;
  });
}

// Inicialización
cargarTopics();
