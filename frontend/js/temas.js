// Módulo de gestión de temas

const COLORES_PRESET = [
  "#6366f1", "#8b5cf6", "#ec4899", "#ef4444",
  "#f59e0b", "#22c55e", "#14b8a6", "#3b82f6",
];

let _temaEditandoId = null;

// ── Renderiza la lista de temas ──────────────────────────────────
async function cargarTemas() {
  const temas = await api("GET", "/topics");
  const lista = document.getElementById("temas-lista");
  lista.innerHTML = "";

  if (!temas.length) {
    lista.innerHTML = `
      <div style="text-align:center; padding:3rem; color:var(--text-muted);">
        <div style="font-size:2.5rem; margin-bottom:1rem;">📚</div>
        <p>No tenés temas todavía.</p>
        <p style="font-size:.85rem; margin-top:.5rem;">Creá el primero para organizar tus notas y flashcards.</p>
      </div>`;
    return;
  }

  temas.forEach(t => {
    const div = document.createElement("div");
    div.className = "tema-item card";
    div.innerHTML = `
      <div class="tema-dot" style="background:${t.color}"></div>
      <div class="tema-info">
        <strong>${t.nombre}</strong>
        ${t.descripcion ? `<span class="meta">${t.descripcion}</span>` : ""}
      </div>
      <div class="row" style="flex-shrink:0">
        <button class="btn btn-secondary btn-sm" onclick="editarTema(${t.id})">Editar</button>
        <button class="btn btn-danger btn-sm" onclick="eliminarTema(${t.id}, '${t.nombre.replace(/'/g, "\\'")}')">Borrar</button>
      </div>`;
    lista.appendChild(div);
  });
}

// ── Modal ────────────────────────────────────────────────────────
function abrirModalTema(tema = null) {
  _temaEditandoId = tema ? tema.id : null;
  document.getElementById("modal-tema-titulo").textContent = tema ? "Editar tema" : "Nuevo tema";
  document.getElementById("mt-nombre").value      = tema?.nombre      ?? "";
  document.getElementById("mt-descripcion").value = tema?.descripcion ?? "";
  document.getElementById("mt-color").value       = tema?.color       ?? "#6366f1";
  _renderColorPicker(tema?.color ?? "#6366f1");
  document.getElementById("modal-tema").classList.add("open");
  setTimeout(() => document.getElementById("mt-nombre").focus(), 50);
}

function cerrarModalTema() {
  document.getElementById("modal-tema").classList.remove("open");
  _temaEditandoId = null;
}

function _renderColorPicker(seleccionado) {
  const picker = document.getElementById("mt-color-picker");
  picker.innerHTML = "";
  COLORES_PRESET.forEach(color => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "color-swatch" + (color === seleccionado ? " active" : "");
    btn.style.background = color;
    btn.title = color;
    btn.onclick = () => {
      document.getElementById("mt-color").value = color;
      picker.querySelectorAll(".color-swatch").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
    };
    picker.appendChild(btn);
  });
}

async function guardarTema() {
  const body = {
    nombre:      document.getElementById("mt-nombre").value.trim(),
    descripcion: document.getElementById("mt-descripcion").value.trim() || null,
    color:       document.getElementById("mt-color").value,
  };
  if (!body.nombre) { toast("El nombre es obligatorio"); return; }

  if (_temaEditandoId) {
    await api("PUT", `/topics/${_temaEditandoId}`, body);
    toast("Tema actualizado");
  } else {
    await api("POST", "/topics", body);
    toast("Tema creado");
  }
  cerrarModalTema();
  await cargarTopics();
  cargarTemas();
}

async function editarTema(id) {
  const temas = await api("GET", "/topics");
  const tema  = temas.find(t => t.id === id);
  if (tema) abrirModalTema(tema);
}

async function eliminarTema(id, nombre) {
  if (!confirm(`¿Eliminar el tema "${nombre}"?\nLas notas y flashcards de este tema quedarán sin tema asignado.`)) return;
  await api("DELETE", `/topics/${id}`);
  toast("Tema eliminado");
  await cargarTopics();
  cargarTemas();
}

// ── Eventos ──────────────────────────────────────────────────────
document.getElementById("btn-nuevo-tema").addEventListener("click", () => abrirModalTema());
