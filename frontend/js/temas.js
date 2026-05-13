// Módulo de gestión de temas (curso → bloque → tema)

const COLORES_PRESET = [
  "#6366f1", "#8b5cf6", "#ec4899", "#ef4444",
  "#f59e0b", "#22c55e", "#14b8a6", "#3b82f6",
];

let _editandoId     = null;
let _parentIdActual = null;
let _nivelActual    = 0; // 0=curso, 1=bloque, 2=tema

const LABELS = ["Curso", "Bloque", "Tema"];

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
        <p style="font-size:.85rem; margin-top:.5rem;">Creá el primero con el botón de arriba.</p>
      </div>`;
    return;
  }

  arbol.forEach(curso => {
    const cursoEl = document.createElement("div");
    cursoEl.className = "curso-bloque";

    // Cabecera curso
    cursoEl.innerHTML = `
      <div class="nivel-header nivel-0" style="border-left: 4px solid ${curso.color}">
        <span class="nivel-badge">Curso</span>
        <div class="tema-info">
          <strong>${curso.nombre}</strong>
          ${curso.descripcion ? `<span class="meta">${curso.descripcion}</span>` : ""}
        </div>
        <div class="row" style="flex-shrink:0; gap:.4rem;">
          <button class="btn btn-secondary btn-sm" onclick="editarNodo(${curso.id})">Editar</button>
          <button class="btn btn-danger btn-sm"    onclick="eliminarNodo(${curso.id}, '${_esc(curso.nombre)}', 0)">Borrar</button>
        </div>
      </div>`;

    // Bloques
    const bloquesEl = document.createElement("div");
    bloquesEl.className = "hijos-lista nivel-1-lista";

    (curso.bloques || []).forEach(bloque => {
      const bloqueEl = document.createElement("div");
      bloqueEl.className = "nodo-item nivel-1";

      bloqueEl.innerHTML = `
        <div class="nivel-header" style="border-left: 3px solid ${bloque.color}">
          <span class="nivel-badge">Bloque</span>
          <div class="tema-info">
            <strong>${bloque.nombre}</strong>
            ${bloque.descripcion ? `<span class="meta">${bloque.descripcion}</span>` : ""}
          </div>
          <div class="row" style="flex-shrink:0; gap:.4rem;">
            <button class="btn btn-secondary btn-sm" onclick="editarNodo(${bloque.id})">Editar</button>
            <button class="btn btn-danger btn-sm"    onclick="eliminarNodo(${bloque.id}, '${_esc(bloque.nombre)}', 1)">Borrar</button>
          </div>
        </div>`;

      // Temas dentro del bloque
      const temasEl = document.createElement("div");
      temasEl.className = "hijos-lista nivel-2-lista";

      (bloque.temas || []).forEach(tema => {
        const temaEl = document.createElement("div");
        temaEl.className = "nodo-item nivel-2";
        temaEl.innerHTML = `
          <div class="nivel-header" style="border-left: 2px solid ${tema.color}">
            <span class="nivel-badge">Tema</span>
            <div class="tema-info">
              <span>${tema.nombre}</span>
              ${tema.descripcion ? `<span class="meta">${tema.descripcion}</span>` : ""}
            </div>
            <div class="row" style="flex-shrink:0; gap:.4rem;">
              <button class="btn btn-secondary btn-sm" onclick="editarNodo(${tema.id})">Editar</button>
              <button class="btn btn-danger btn-sm"    onclick="eliminarNodo(${tema.id}, '${_esc(tema.nombre)}', 2)">Borrar</button>
            </div>
          </div>`;
        temasEl.appendChild(temaEl);
      });

      // Botón + Agregar tema
      const btnTema = document.createElement("button");
      btnTema.className = "btn btn-secondary btn-sm agregar-hijo";
      btnTema.textContent = "+ Agregar tema";
      btnTema.onclick = () => abrirModal(null, bloque.id, 2, bloque.color);
      temasEl.appendChild(btnTema);

      bloqueEl.appendChild(temasEl);
      bloquesEl.appendChild(bloqueEl);
    });

    // Botón + Agregar bloque
    const btnBloque = document.createElement("button");
    btnBloque.className = "btn btn-secondary btn-sm agregar-hijo";
    btnBloque.textContent = "+ Agregar bloque";
    btnBloque.onclick = () => abrirModal(null, curso.id, 1, curso.color);
    bloquesEl.appendChild(btnBloque);

    cursoEl.appendChild(bloquesEl);
    lista.appendChild(cursoEl);
  });
}

function _esc(str) {
  return str.replace(/'/g, "\\'").replace(/"/g, "&quot;");
}

// ── Modal ────────────────────────────────────────────────────────
function abrirModal(nodo = null, parentId = null, nivel = 0, colorHeredado = "#6366f1") {
  _editandoId     = nodo ? nodo.id : null;
  _parentIdActual = nodo ? nodo.parent_id : parentId;
  _nivelActual    = nivel;

  const accion = nodo ? "Editar" : "Nuevo";
  document.getElementById("modal-tema-titulo").textContent = `${accion} ${LABELS[nivel]}`;

  document.getElementById("mt-nombre").value      = nodo?.nombre      ?? "";
  document.getElementById("mt-descripcion").value = nodo?.descripcion ?? "";

  const color = nodo?.color ?? colorHeredado;
  document.getElementById("mt-color").value = color;
  _renderColorPicker(color);

  document.getElementById("modal-tema").classList.add("open");
  setTimeout(() => document.getElementById("mt-nombre").focus(), 50);
}

function cerrarModalTema() {
  document.getElementById("modal-tema").classList.remove("open");
  _editandoId = null;
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

  if (_editandoId) {
    await api("PUT", `/topics/${_editandoId}`, body);
    toast(`${LABELS[_nivelActual]} actualizado`);
  } else {
    await api("POST", "/topics", body);
    toast(`${LABELS[_nivelActual]} creado`);
  }
  cerrarModalTema();
  await cargarTopics();
  cargarTemas();
}

async function editarNodo(id) {
  const todos = await api("GET", "/topics");
  const por_id = Object.fromEntries(todos.map(t => [t.id, t]));
  const nodo   = por_id[id];
  if (!nodo) return;
  const nivel = nodo.parent_id === null ? 0
    : por_id[nodo.parent_id]?.parent_id === null ? 1 : 2;
  abrirModal(nodo, nodo.parent_id, nivel);
}

async function eliminarNodo(id, nombre, nivel) {
  const avisos = [
    `¿Eliminar el curso "${nombre}"?\nSe eliminarán también todos sus bloques y temas.`,
    `¿Eliminar el bloque "${nombre}"?\nSe eliminarán también todos sus temas.`,
    `¿Eliminar el tema "${nombre}"?`,
  ];
  if (!confirm(avisos[nivel])) return;
  await api("DELETE", `/topics/${id}`);
  toast("Eliminado");
  await cargarTopics();
  cargarTemas();
}

// ── Eventos ──────────────────────────────────────────────────────
document.getElementById("btn-nuevo-tema").addEventListener("click", () => abrirModal(null, null, 0));
