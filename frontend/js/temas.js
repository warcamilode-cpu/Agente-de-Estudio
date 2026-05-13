// Módulo de gestión de temas (cursos > temas)

const COLORES_PRESET = [
  "#6366f1", "#8b5cf6", "#ec4899", "#ef4444",
  "#f59e0b", "#22c55e", "#14b8a6", "#3b82f6",
];

let _temaEditandoId  = null;
let _parentIdActual  = null; // null = es un curso, número = es un subtema

// ── Lista jerárquica ─────────────────────────────────────────────
async function cargarTemas() {
  const arbol = await api("GET", "/topics/arbol");
  const lista  = document.getElementById("temas-lista");
  lista.innerHTML = "";

  if (!arbol.length) {
    lista.innerHTML = `
      <div style="text-align:center; padding:3rem; color:var(--text-muted);">
        <div style="font-size:2.5rem; margin-bottom:1rem;">📚</div>
        <p>No tenés cursos todavía.</p>
        <p style="font-size:.85rem; margin-top:.5rem;">Creá el primero para organizar tus notas y flashcards.</p>
      </div>`;
    return;
  }

  arbol.forEach(curso => {
    const bloque = document.createElement("div");
    bloque.className = "curso-bloque";

    // Cabecera del curso
    bloque.innerHTML = `
      <div class="curso-header">
        <div class="tema-dot" style="background:${curso.color}"></div>
        <div class="tema-info">
          <strong>${curso.nombre}</strong>
          ${curso.descripcion ? `<span class="meta">${curso.descripcion}</span>` : ""}
        </div>
        <div class="row" style="flex-shrink:0; gap:.4rem;">
          <button class="btn btn-secondary btn-sm" onclick="editarTema(${curso.id})">Editar</button>
          <button class="btn btn-danger btn-sm"    onclick="eliminarTema(${curso.id}, '${_esc(curso.nombre)}')">Borrar</button>
        </div>
      </div>`;

    // Subtemas
    const subLista = document.createElement("div");
    subLista.className = "subtemas-lista";

    if (curso.temas.length) {
      curso.temas.forEach(t => {
        const fila = document.createElement("div");
        fila.className = "subtema-item";
        fila.innerHTML = `
          <div class="subtema-dot" style="background:${t.color}"></div>
          <span class="subtema-nombre">${t.nombre}</span>
          ${t.descripcion ? `<span class="meta" style="flex:1">${t.descripcion}</span>` : '<span style="flex:1"></span>'}
          <div class="row" style="flex-shrink:0; gap:.4rem;">
            <button class="btn btn-secondary btn-sm" onclick="editarTema(${t.id})">Editar</button>
            <button class="btn btn-danger btn-sm"    onclick="eliminarTema(${t.id}, '${_esc(t.nombre)}')">Borrar</button>
          </div>`;
        subLista.appendChild(fila);
      });
    }

    // Botón agregar subtema
    const btnAgregar = document.createElement("button");
    btnAgregar.className = "btn btn-secondary btn-sm agregar-subtema";
    btnAgregar.textContent = "+ Agregar tema";
    btnAgregar.onclick = () => abrirModalTema(null, curso.id, curso.color);
    subLista.appendChild(btnAgregar);

    bloque.appendChild(subLista);
    lista.appendChild(bloque);
  });
}

function _esc(str) {
  return str.replace(/'/g, "\\'").replace(/"/g, "&quot;");
}

// ── Modal ────────────────────────────────────────────────────────
function abrirModalTema(tema = null, parentId = null, colorHeredado = "#6366f1") {
  _temaEditandoId = tema ? tema.id : null;
  _parentIdActual = tema ? tema.parent_id : parentId;

  const esCurso = _parentIdActual === null;
  document.getElementById("modal-tema-titulo").textContent =
    tema
      ? (esCurso ? "Editar curso" : "Editar tema")
      : (esCurso ? "Nuevo curso"  : "Nuevo tema");

  document.getElementById("mt-nombre").value      = tema?.nombre      ?? "";
  document.getElementById("mt-descripcion").value = tema?.descripcion ?? "";

  const colorInicial = tema?.color ?? colorHeredado;
  document.getElementById("mt-color").value = colorInicial;
  _renderColorPicker(colorInicial);

  document.getElementById("modal-tema").classList.add("open");
  setTimeout(() => document.getElementById("mt-nombre").focus(), 50);
}

function cerrarModalTema() {
  document.getElementById("modal-tema").classList.remove("open");
  _temaEditandoId = null;
  _parentIdActual = null;
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
    parent_id:   _parentIdActual,
  };
  if (!body.nombre) { toast("El nombre es obligatorio"); return; }

  if (_temaEditandoId) {
    await api("PUT", `/topics/${_temaEditandoId}`, body);
    toast("Actualizado");
  } else {
    await api("POST", "/topics", body);
    toast(_parentIdActual === null ? "Curso creado" : "Tema agregado");
  }
  cerrarModalTema();
  await cargarTopics();
  cargarTemas();
}

async function editarTema(id) {
  const todos = await api("GET", "/topics");
  const tema  = todos.find(t => t.id === id);
  if (tema) abrirModalTema(tema, tema.parent_id);
}

async function eliminarTema(id, nombre) {
  const todos   = await api("GET", "/topics");
  const esCurso = todos.find(t => t.id === id)?.parent_id === null;
  const aviso   = esCurso
    ? `¿Eliminar el curso "${nombre}"?\nSe eliminarán también todos sus temas.`
    : `¿Eliminar el tema "${nombre}"?`;
  if (!confirm(aviso)) return;
  await api("DELETE", `/topics/${id}`);
  toast("Eliminado");
  await cargarTopics();
  cargarTemas();
}

// ── Eventos ──────────────────────────────────────────────────────
document.getElementById("btn-nuevo-tema").addEventListener("click", () => abrirModalTema());
