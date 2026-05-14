// ── Cuaderno — Sistema Cornell ────────────────────────────────────

let _estructura  = [];    // programas → semestres → materias
let _matActiva   = null;
let _claseActiva = null;
let _apuntesTimer = null;
let _tabActiva   = "acciones";

const TIPO_ICON = { pregrado: "🎓", posgrado: "🏛️", otro: "📋" };

// ── Punto de entrada ─────────────────────────────────────────────

async function cargarCuaderno() {
  _estructura = await api("GET", "/cuaderno/estructura");
  _renderNav();
  if (!_matActiva && !_claseActiva) _renderBienvenida();
}

// ── Navegación lateral ────────────────────────────────────────────

function _renderNav() {
  const nav = document.getElementById("cn-nav-scroll");
  nav.innerHTML = "";

  if (!_estructura.length) {
    nav.innerHTML = '<p style="padding:.75rem; font-size:.8rem; color:var(--text-muted);">Creá tu primer programa de estudio.</p>';
    return;
  }

  _estructura.forEach(prog => {
    const progEl = document.createElement("div");
    progEl.className = "cn-programa";

    const icon = TIPO_ICON[prog.tipo] || "📚";
    progEl.innerHTML = `
      <div class="cn-programa-header">
        <span class="cn-programa-icon">${icon}</span>
        <span class="cn-programa-nombre">${_esc(prog.nombre)}</span>
        <span class="cn-programa-tipo">${prog.tipo}</span>
        ${prog.id ? `<div class="cn-semestre-acciones">
          <button class="cn-btn-icon" title="Agregar semestre" onclick="_abrirModalSemestre(${prog.id})">+</button>
          <button class="cn-btn-icon" title="Editar programa" onclick="_editarPrograma(${prog.id})">✏</button>
          <button class="cn-btn-icon" title="Eliminar programa" onclick="_eliminarPrograma(${prog.id})">✕</button>
        </div>` : ""}
      </div>`;

    const semsEl = document.createElement("div");
    semsEl.className = "cn-semestres-lista";

    (prog.semestres || []).forEach(sem => {
      const semEl = document.createElement("div");
      semEl.className = "cn-semestre";
      semEl.innerHTML = `
        <div class="cn-semestre-header">
          <span class="cn-semestre-nombre">📅 ${_esc(sem.nombre)}</span>
          <div class="cn-semestre-acciones">
            <button class="cn-btn-icon" title="Editar" onclick="_editarSemestre(${sem.id},'${_esc(sem.nombre)}',${sem.programa_id ?? "null"})">✏</button>
            <button class="cn-btn-icon" title="Eliminar" onclick="_eliminarSemestre(${sem.id})">✕</button>
          </div>
        </div>`;

      const matsEl = document.createElement("div");
      matsEl.className = "cn-materias-lista";
      matsEl.id = `cn-materias-${sem.id}`;

      (sem.materias || []).forEach(mat => {
        const item = document.createElement("div");
        item.className = "cn-materia-item" + (_matActiva?.id === mat.id ? " activa" : "");
        item.dataset.materiaId = mat.id;
        item.innerHTML = `
          <span style="font-size:.95rem">${mat.emoji}</span>
          <span class="cn-materia-dot" style="background:${mat.color}"></span>
          <span class="cn-materia-nombre">${_esc(mat.nombre)}</span>
          <div class="cn-materia-acciones">
            <button class="cn-btn-icon" title="Editar" onclick="event.stopPropagation();_editarMateria(${mat.id})">✏</button>
            <button class="cn-btn-icon" title="Eliminar" onclick="event.stopPropagation();_eliminarMateria(${mat.id})">✕</button>
          </div>`;
        item.addEventListener("click", () => _abrirMateria(mat));
        matsEl.appendChild(item);
      });

      const btnAdd = document.createElement("button");
      btnAdd.className = "cn-add-materia";
      btnAdd.textContent = "+ Agregar materia";
      btnAdd.onclick = () => _abrirModalMateria(sem.id);
      matsEl.appendChild(btnAdd);

      semEl.appendChild(matsEl);
      semsEl.appendChild(semEl);
    });

    progEl.appendChild(semsEl);
    nav.appendChild(progEl);
  });
}

function _renderBienvenida() {
  document.getElementById("cn-contenido").innerHTML = `
    <div class="cuaderno-vacia">
      <div class="icon">📖</div>
      <p>Seleccioná una materia para ver sus clases<br>o creá tu primer programa de estudio.</p>
    </div>`;
}

// ── Vista de materia ──────────────────────────────────────────────

async function _abrirMateria(mat) {
  _matActiva   = mat;
  _claseActiva = null;
  _renderNav();
  const clases = await api("GET", `/cuaderno/materias/${mat.id}/clases`);
  _renderVistaMateria(mat, clases);
}

function _renderVistaMateria(mat, clases) {
  const cont = document.getElementById("cn-contenido");
  cont.innerHTML = `
    <div class="vista-materia">
      <div class="materia-header">
        <div class="materia-titulo">
          <span style="font-size:1.6rem">${mat.emoji}</span>
          <h2>${_esc(mat.nombre)}</h2>
          <span class="cn-materia-dot" style="background:${mat.color}; width:14px; height:14px;"></span>
        </div>
        <div class="materia-info-grid">
          <div class="materia-info-campo">
            <span>👨‍🏫</span>
            <input id="mi-docente" value="${_esc(mat.docente||'')}" placeholder="Docente" data-campo="docente">
          </div>
          <div class="materia-info-campo">
            <span>📧</span>
            <input id="mi-email" value="${_esc(mat.email_docente||'')}" placeholder="Correo" data-campo="email_docente">
          </div>
          <div class="materia-info-campo">
            <span>🏛️</span>
            <input id="mi-salon" value="${_esc(mat.salon||'')}" placeholder="Salón" data-campo="salon">
          </div>
        </div>
      </div>
      <div class="materia-clases-header">
        <span style="font-weight:600; font-size:.9rem;">Clases</span>
        <button class="btn btn-primary btn-sm" onclick="_abrirModalClase(${mat.id})">+ Nueva clase</button>
      </div>
      <div class="materia-clases-scroll" id="cn-clases-lista"></div>
    </div>`;

  ["mi-docente", "mi-email", "mi-salon"].forEach(id => {
    const inp = document.getElementById(id);
    let t;
    inp.addEventListener("input", () => { clearTimeout(t); t = setTimeout(() => _guardarInfoMateria(mat.id), 900); });
  });

  _renderClases(clases, mat);
}

function _renderClases(clases, mat) {
  const lista = document.getElementById("cn-clases-lista");
  if (!clases.length) {
    lista.innerHTML = '<p style="color:var(--text-muted); font-size:.875rem; padding:.5rem 0;">Sin clases aún. Agregá la primera.</p>';
    return;
  }
  lista.innerHTML = clases.map(c => `
    <div class="clase-card" onclick="_abrirClase(${c.id},'${_esc(c.titulo)}','${c.fecha}',${mat.id})">
      <div class="clase-fecha">${_formatFecha(c.fecha)}</div>
      <div class="clase-info">
        <div class="clase-titulo">${_esc(c.titulo)}</div>
        ${c.temas ? `<div class="clase-temas">${_esc(c.temas)}</div>` : ""}
      </div>
      <div class="clase-dots">
        ${c.tiene_dudas      ? '<span class="clase-dot duda"       title="Dudas pendientes"></span>'  : ""}
        ${c.tiene_importantes? '<span class="clase-dot importante"  title="Puntos importantes"></span>': ""}
        ${c.tiene_tareas     ? '<span class="clase-dot tarea"       title="Tareas pendientes"></span>' : ""}
      </div>
      <div class="clase-card-acciones" onclick="event.stopPropagation()">
        <button class="cn-btn-icon" onclick="_eliminarClase(${c.id},${mat.id})">✕</button>
      </div>
    </div>`).join("");
}

async function _guardarInfoMateria(matId) {
  const body = {
    docente:       document.getElementById("mi-docente")?.value || "",
    email_docente: document.getElementById("mi-email")?.value   || "",
    salon:         document.getElementById("mi-salon")?.value   || "",
  };
  const updated = await api("PATCH", `/cuaderno/materias/${matId}/info`, body);
  _matActiva = { ..._matActiva, ...updated };
}

// ── Vista de clase — Cornell ──────────────────────────────────────

async function _abrirClase(claseId, titulo, fecha, materiaId) {
  _claseActiva = { id: claseId, titulo, fecha, materia_id: materiaId };
  const apuntes = await api("GET", `/cuaderno/clases/${claseId}/apuntes`);
  _renderCornell(apuntes);
}

function _renderCornell(apuntes) {
  const cont = document.getElementById("cn-contenido");
  cont.innerHTML = `
    <div class="cornell-shell">
      <div class="cornell-header">
        <button class="btn-back" onclick="_volverAMateria()" title="Volver">← Volver</button>
        <div class="cornell-meta">
          <div class="cornell-titulo-clase">${_esc(_claseActiva.titulo)}</div>
          <div class="cornell-fecha-clase">${_formatFecha(_claseActiva.fecha)}</div>
        </div>
        <span class="cornell-guardar-badge" id="cn-guardado">✓ Guardado</span>
      </div>
      <div class="cornell-main">
        <div class="cornell-indicios">
          <div class="cornell-col-label">Indicios / Pistas</div>
          <textarea id="cn-indicios" placeholder="Palabras clave, preguntas de repaso…">${_esc(apuntes.indicios||'')}</textarea>
        </div>
        <div class="cornell-notas-col">
          <div class="cornell-col-label">Notas principales</div>
          <textarea id="cn-notas" placeholder="Apuntes detallados de la clase…">${_esc(apuntes.notas_principales||'')}</textarea>
        </div>
      </div>
      <div class="cornell-resumen">
        <div class="cornell-col-label" style="color:rgba(13,148,136,.7)">Resumen (2-3 ideas clave)</div>
        <textarea id="cn-resumen" placeholder="Resumí la clase en 2 o 3 oraciones clave…">${_esc(apuntes.resumen||'')}</textarea>
      </div>
      <div class="cornell-tabs-bar">
        <button class="cornell-tab-btn ${_tabActiva==='acciones'?'active':''}" onclick="_cambiarTab('acciones')">⚡ Acciones</button>
        <button class="cornell-tab-btn ${_tabActiva==='referencias'?'active':''}" onclick="_cambiarTab('referencias')">📖 Referencia rápida</button>
      </div>
      <div id="cn-tab-acciones"   class="cornell-tab-panel ${_tabActiva==='acciones'?'active':''}"></div>
      <div id="cn-tab-referencias" class="cornell-tab-panel ${_tabActiva==='referencias'?'active':''}"></div>
    </div>`;

  ["cn-indicios", "cn-notas", "cn-resumen"].forEach(id => {
    document.getElementById(id).addEventListener("input", _debounceGuardarApuntes);
  });

  _cargarAcciones();
  _cargarReferencias();
}

function _debounceGuardarApuntes() {
  clearTimeout(_apuntesTimer);
  _apuntesTimer = setTimeout(_guardarApuntes, 1400);
}

async function _guardarApuntes() {
  if (!_claseActiva) return;
  const body = {
    indicios:          document.getElementById("cn-indicios")?.value || "",
    notas_principales: document.getElementById("cn-notas")?.value    || "",
    resumen:           document.getElementById("cn-resumen")?.value  || "",
  };
  await api("PUT", `/cuaderno/clases/${_claseActiva.id}/apuntes`, body);
  const badge = document.getElementById("cn-guardado");
  if (badge) { badge.classList.add("visible"); setTimeout(() => badge.classList.remove("visible"), 2000); }
}

function _volverAMateria() {
  clearTimeout(_apuntesTimer);
  _guardarApuntes();
  if (_matActiva) _abrirMateria(_matActiva);
  else _renderBienvenida();
}

// ── Tabs ─────────────────────────────────────────────────────────

function _cambiarTab(nombre) {
  _tabActiva = nombre;
  document.querySelectorAll(".cornell-tab-btn").forEach((b, i) =>
    b.classList.toggle("active", (i === 0 && nombre === "acciones") || (i === 1 && nombre === "referencias"))
  );
  document.querySelectorAll(".cornell-tab-panel").forEach(p =>
    p.classList.toggle("active", p.id === `cn-tab-${nombre}`)
  );
}

// ── Acciones ──────────────────────────────────────────────────────

async function _cargarAcciones() {
  if (!_claseActiva) return;
  const acciones = await api("GET", `/cuaderno/clases/${_claseActiva.id}/acciones`);
  _renderAcciones(acciones);
}

function _renderAcciones(acciones) {
  const panel = document.getElementById("cn-tab-acciones");
  if (!panel) return;
  const grupos = { "?": [], "*": [], "T": [] };
  acciones.forEach(a => grupos[a.tipo]?.push(a));
  const labels = {
    "?": ["tipo-duda",       "[ ? ] Dudas"],
    "*": ["tipo-importante", "[ * ] Importantes"],
    "T": ["tipo-tarea",      "[ T ] Tareas"],
  };

  let html = `<div style="display:flex; gap:.4rem; flex-wrap:wrap; margin-bottom:.4rem;">`;
  ["?","*","T"].forEach(t => {
    const [cls, lbl] = labels[t];
    html += `<button class="btn btn-secondary btn-sm" onclick="_agregarAccion('${t}')">+ <span class="accion-badge ${cls}">${t}</span> ${lbl}</button>`;
  });
  html += `</div>`;

  ["?","*","T"].forEach(t => {
    const [cls, lbl] = labels[t];
    if (!grupos[t].length) return;
    html += `<div style="margin-bottom:.4rem;"><div style="font-size:.65rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase; color:var(--text-muted); margin-bottom:.25rem;">${lbl}</div>`;
    grupos[t].forEach(a => {
      html += `<div class="accion-item${a.resuelto ? " resuelto" : ""}" style="margin-bottom:.25rem;">
        <span class="accion-badge ${cls}">${t}</span>
        <span class="accion-texto">${_esc(a.contenido)}</span>
        <div style="display:flex; gap:.15rem; flex-shrink:0; margin-left:.35rem;">
          <button class="cn-btn-icon" title="${a.resuelto?"Reabrir":"Marcar resuelto"}" onclick="_toggleAccion(${a.id})">${a.resuelto?"↩":"✓"}</button>
          <button class="cn-btn-icon" onclick="_eliminarAccion(${a.id})">✕</button>
        </div>
      </div>`;
    });
    html += `</div>`;
  });
  panel.innerHTML = html;
}

async function _agregarAccion(tipo) {
  const texto = prompt(`Nueva acción [ ${tipo} ]:`);
  if (!texto?.trim()) return;
  await api("POST", "/cuaderno/acciones", { clase_id: _claseActiva.id, tipo, contenido: texto.trim() });
  _cargarAcciones();
}

async function _toggleAccion(id) {
  await api("PATCH", `/cuaderno/acciones/${id}/toggle`);
  _cargarAcciones();
}

async function _eliminarAccion(id) {
  await api("DELETE", `/cuaderno/acciones/${id}`);
  _cargarAcciones();
}

// ── Referencias rápidas ───────────────────────────────────────────

async function _cargarReferencias() {
  if (!_matActiva) return;
  const refs = await api("GET", `/cuaderno/materias/${_matActiva.id}/referencias`);
  _renderReferencias(refs);
}

function _renderReferencias(refs) {
  const panel = document.getElementById("cn-tab-referencias");
  if (!panel) return;
  let html = `<div style="display:flex; gap:.4rem; margin-bottom:.4rem; flex-wrap:wrap;">
    <input id="cn-ref-termino" type="text" placeholder="Término" style="flex:1; min-width:90px;">
    <input id="cn-ref-def" type="text" placeholder="Definición" style="flex:2; min-width:140px;">
    <button class="btn btn-primary btn-sm" onclick="_agregarReferencia()">Agregar</button>
  </div>`;
  if (!refs.length) {
    html += '<p style="color:var(--text-muted); font-size:.8rem;">Agregá conceptos clave de esta materia.</p>';
  } else {
    refs.forEach(r => {
      html += `<div class="ref-item">
        <span class="ref-termino">${_esc(r.termino)}</span>
        <span class="ref-definicion">${_esc(r.definicion)}</span>
        <button class="cn-btn-icon" style="flex-shrink:0" onclick="_eliminarReferencia(${r.id})">✕</button>
      </div>`;
    });
  }
  panel.innerHTML = html;
}

async function _agregarReferencia() {
  const termino = document.getElementById("cn-ref-termino")?.value.trim();
  const def     = document.getElementById("cn-ref-def")?.value.trim();
  if (!termino || !def) { toast("Completá término y definición"); return; }
  await api("POST", "/cuaderno/referencias", { materia_id: _matActiva.id, termino, definicion: def });
  _cargarReferencias();
}

async function _eliminarReferencia(id) {
  await api("DELETE", `/cuaderno/referencias/${id}`);
  _cargarReferencias();
}

// ── Modales: Programa ─────────────────────────────────────────────

function _abrirModalPrograma(id = null) {
  document.getElementById("prog-id").value          = id || "";
  document.getElementById("prog-nombre").value      = "";
  document.getElementById("prog-tipo").value        = "pregrado";
  document.getElementById("prog-descripcion").value = "";
  document.getElementById("modal-prog-titulo").textContent = id ? "Editar programa" : "Nuevo programa";

  if (id) {
    const prog = _estructura.find(p => p.id === id);
    if (prog) {
      document.getElementById("prog-nombre").value      = prog.nombre;
      document.getElementById("prog-tipo").value        = prog.tipo;
      document.getElementById("prog-descripcion").value = prog.descripcion || "";
    }
  }
  document.getElementById("modal-programa").classList.add("open");
}

function cerrarModalPrograma() {
  document.getElementById("modal-programa").classList.remove("open");
}

async function guardarPrograma() {
  const nombre      = document.getElementById("prog-nombre").value.trim();
  const tipo        = document.getElementById("prog-tipo").value;
  const descripcion = document.getElementById("prog-descripcion").value.trim();
  const editId      = document.getElementById("prog-id").value;
  if (!nombre) { toast("Escribí el nombre del programa"); return; }

  if (editId) {
    await api("PUT", `/cuaderno/programas/${editId}`, { nombre, tipo, descripcion });
  } else {
    await api("POST", "/cuaderno/programas", { nombre, tipo, descripcion });
  }
  cerrarModalPrograma();
  await cargarCuaderno();
  await cargarEstructura();
}

function _editarPrograma(id) { _abrirModalPrograma(id); }

async function _eliminarPrograma(id) {
  if (!confirm("¿Eliminar este programa y todos sus semestres y materias?")) return;
  await api("DELETE", `/cuaderno/programas/${id}`);
  if (_matActiva) {
    const sigue = _estructura.find(p => p.id === id)?.semestres
      ?.flatMap(s => s.materias)?.some(m => m.id === _matActiva.id);
    if (sigue) { _matActiva = null; _claseActiva = null; }
  }
  await cargarCuaderno();
  await cargarEstructura();
  if (!_matActiva) _renderBienvenida();
}

// ── Modales: Semestre ─────────────────────────────────────────────

function _abrirModalSemestre(programaId, id = null, nombreActual = "") {
  document.getElementById("sem-programa-id").value = programaId;
  document.getElementById("sem-id").value          = id || "";
  document.getElementById("sem-nombre").value      = nombreActual;
  document.getElementById("modal-sem-titulo").textContent = id ? "Editar semestre" : "Nuevo semestre";
  document.getElementById("modal-semestre").classList.add("open");
  setTimeout(() => document.getElementById("sem-nombre").focus(), 100);
}

function cerrarModalSemestre() {
  document.getElementById("modal-semestre").classList.remove("open");
}

async function guardarSemestre() {
  const nombre     = document.getElementById("sem-nombre").value.trim();
  const programaId = document.getElementById("sem-programa-id").value;
  const editId     = document.getElementById("sem-id").value;
  if (!nombre) { toast("Escribí el nombre del semestre"); return; }

  const body = { nombre, orden: 0, programa_id: programaId ? parseInt(programaId) : null };
  if (editId) {
    await api("PUT", `/cuaderno/semestres/${editId}`, body);
  } else {
    await api("POST", "/cuaderno/semestres", body);
  }
  cerrarModalSemestre();
  await cargarCuaderno();
  await cargarEstructura();
}

function _editarSemestre(id, nombreActual, programaId) {
  _abrirModalSemestre(programaId, id, nombreActual);
}

async function _eliminarSemestre(id) {
  if (!confirm("¿Eliminar este semestre y todas sus materias?")) return;
  await api("DELETE", `/cuaderno/semestres/${id}`);
  if (_matActiva) {
    const enSem = _estructura.flatMap(p => p.semestres || [])
      .find(s => s.id === id)?.materias?.some(m => m.id === _matActiva.id);
    if (enSem) { _matActiva = null; _claseActiva = null; }
  }
  await cargarCuaderno();
  await cargarEstructura();
  if (!_matActiva) _renderBienvenida();
}

// ── Modales: Materia ──────────────────────────────────────────────

function _abrirModalMateria(semestreId) {
  document.getElementById("cm-semestre-id").value = semestreId;
  document.getElementById("cm-nombre").value      = "";
  document.getElementById("cm-emoji").value       = "📚";
  document.getElementById("cm-id").value          = "";
  document.getElementById("modal-cm-titulo").textContent = "Nueva materia";
  _selColorMateria("#0d9488");
  document.getElementById("modal-cuaderno-materia").classList.add("open");
}

async function _editarMateria(id) {
  let mat = null;
  _estructura.forEach(p => (p.semestres || []).forEach(s =>
    s.materias.forEach(m => { if (m.id === id) mat = m; })
  ));
  if (!mat) return;
  document.getElementById("cm-semestre-id").value = mat.semestre_id;
  document.getElementById("cm-nombre").value      = mat.nombre;
  document.getElementById("cm-emoji").value       = mat.emoji;
  document.getElementById("cm-id").value          = mat.id;
  document.getElementById("modal-cm-titulo").textContent = "Editar materia";
  _selColorMateria(mat.color);
  document.getElementById("modal-cuaderno-materia").classList.add("open");
}

function _selColorMateria(color) {
  document.getElementById("cm-color").value = color;
  document.querySelectorAll("#cm-color-picker .color-swatch").forEach(s =>
    s.classList.toggle("active", s.dataset.color === color)
  );
}

function cerrarModalCuadernoMateria() {
  document.getElementById("modal-cuaderno-materia").classList.remove("open");
}

async function guardarMateria() {
  const nombre     = document.getElementById("cm-nombre").value.trim();
  const emoji      = document.getElementById("cm-emoji").value.trim() || "📚";
  const color      = document.getElementById("cm-color").value;
  const semestreId = parseInt(document.getElementById("cm-semestre-id").value);
  const editId     = document.getElementById("cm-id").value;
  if (!nombre) { toast("Escribí el nombre de la materia"); return; }

  const mat = { semestre_id: semestreId, nombre, emoji, color, docente: "", email_docente: "", salon: "" };
  if (editId) {
    await api("PUT", `/cuaderno/materias/${editId}`, mat);
  } else {
    await api("POST", "/cuaderno/materias", mat);
  }
  cerrarModalCuadernoMateria();
  await cargarCuaderno();
  await cargarEstructura();
}

async function _eliminarMateria(id) {
  if (!confirm("¿Eliminar esta materia y todas sus clases?")) return;
  await api("DELETE", `/cuaderno/materias/${id}`);
  if (_matActiva?.id === id) { _matActiva = null; _claseActiva = null; }
  await cargarCuaderno();
  await cargarEstructura();
  if (!_matActiva) _renderBienvenida();
}

// ── Modales: Clase ────────────────────────────────────────────────

function _abrirModalClase(materiaId) {
  document.getElementById("cc-materia-id").value = materiaId;
  document.getElementById("cc-titulo").value     = "";
  document.getElementById("cc-temas").value      = "";
  document.getElementById("cc-fecha").value      = new Date().toISOString().slice(0, 10);
  document.getElementById("modal-cuaderno-clase").classList.add("open");
}

function cerrarModalCuadernoClase() {
  document.getElementById("modal-cuaderno-clase").classList.remove("open");
}

async function guardarClase() {
  const titulo    = document.getElementById("cc-titulo").value.trim();
  const temas     = document.getElementById("cc-temas").value.trim();
  const fecha     = document.getElementById("cc-fecha").value;
  const materiaId = parseInt(document.getElementById("cc-materia-id").value);
  if (!titulo || !fecha) { toast("Título y fecha son obligatorios"); return; }
  const clase = await api("POST", "/cuaderno/clases", { materia_id: materiaId, fecha, titulo, temas });
  cerrarModalCuadernoClase();
  await _abrirClase(clase.id, clase.titulo, clase.fecha, materiaId);
}

async function _eliminarClase(claseId, materiaId) {
  if (!confirm("¿Eliminar esta clase?")) return;
  await api("DELETE", `/cuaderno/clases/${claseId}`);
  const mat    = _matActiva;
  const clases = await api("GET", `/cuaderno/materias/${materiaId}/clases`);
  _renderVistaMateria(mat, clases);
}

// ── Utilidades ────────────────────────────────────────────────────

function _esc(str) {
  return String(str || "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function _formatFecha(fecha) {
  if (!fecha) return "";
  const [y, m, d] = fecha.split("-");
  return `${d}/${m}/${y}`;
}

// ── Inicialización ───────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  const COLORES = ["#0d9488","#3b82f6","#8b5cf6","#ec4899","#ef4444","#f59e0b","#22c55e","#06b6d4","#64748b","#f97316"];
  const picker = document.getElementById("cm-color-picker");
  if (picker) {
    COLORES.forEach(c => {
      const sw = document.createElement("div");
      sw.className = "color-swatch";
      sw.dataset.color = c;
      sw.style.background = c;
      sw.onclick = () => _selColorMateria(c);
      picker.appendChild(sw);
    });
  }

  const btnProg = document.getElementById("btn-nuevo-programa");
  if (btnProg) btnProg.addEventListener("click", () => _abrirModalPrograma());
});
