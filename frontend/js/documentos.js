// Módulo de repositorio de documentos + Análisis (Maia)

let _docActivoId   = null;
let _docsTabActual = "repo";
let _maiaHistorial = [];
let _maiaToksAcum  = 0;
let _maiaUltimaPregunta  = "";
let _maiaUltimaRespuesta = "";

async function cargarDocumentos() {
  const materiaId = document.getElementById("docs-filtro-materia")?.value || "";
  const ruta = materiaId ? `/documentos?materia_id=${materiaId}` : "/documentos";
  const docs = await api("GET", ruta);
  _renderDocumentos(docs);
}

function _renderDocumentos(docs) {
  const lista = document.getElementById("docs-lista");
  if (!docs.length) {
    lista.innerHTML = '<p style="color:var(--text-muted); font-size:.8rem; padding:.5rem .25rem;">Sin documentos todavía.</p>';
    return;
  }
  lista.innerHTML = docs.map(d => `
    <div class="doc-item${_docActivoId === d.id ? ' activo' : ''}" data-id="${d.id}"
         onclick="verDocumento(${d.id},'${_escDoc(d.titulo)}','${d.tipo}')">
      <span class="doc-item-icon">${_iconTipo(d.tipo)}</span>
      <div class="doc-item-info">
        <div class="doc-item-titulo">${d.titulo}</div>
        <div class="doc-item-meta">${d.tipo.toUpperCase()}${d.tags ? ' · ' + d.tags : ''} · ${_fechaCorta(d.creado_at)}</div>
      </div>
      <button class="cn-btn-icon" title="Eliminar" onclick="event.stopPropagation();eliminarDoc(${d.id})">✕</button>
    </div>`).join("");
}

function _iconTipo(tipo) {
  return { pdf: "📄", txt: "📃", md: "📝", json: "🔧" }[tipo] || "📁";
}

function _fechaCorta(ts) { return ts ? ts.slice(0, 10) : ""; }
function _escDoc(str)    { return String(str||"").replace(/'/g,"\\'").replace(/"/g,'&quot;'); }

// ── Visor inline ─────────────────────────────────────────────────

async function verDocumento(id, titulo, tipo) {
  _docActivoId = id;

  // Marca item activo en la lista
  document.querySelectorAll(".doc-item").forEach(el =>
    el.classList.toggle("activo", parseInt(el.dataset.id) === id)
  );

  const visor = document.getElementById("docs-visor");
  visor.innerHTML = `
    <div class="docs-visor-header">
      <span class="docs-visor-titulo">${titulo}</span>
    </div>
    <div class="docs-visor-cuerpo" id="docs-visor-cuerpo">
      <p style="color:var(--text-muted); padding:1rem;">Cargando…</p>
    </div>`;

  const cuerpo = document.getElementById("docs-visor-cuerpo");

  if (tipo === "pdf") {
    cuerpo.innerHTML = `<iframe src="/documentos/${id}/archivo"
      style="width:100%; height:100%; border:none; display:block;"></iframe>`;
  } else {
    try {
      const resp  = await fetch(`/documentos/${id}/archivo`);
      const texto = await resp.text();
      if (tipo === "md") {
        cuerpo.innerHTML = `<div class="docs-texto-render">${marked.parse(texto)}</div>`;
      } else if (tipo === "json") {
        let fmt;
        try { fmt = JSON.stringify(JSON.parse(texto), null, 2); } catch { fmt = texto; }
        cuerpo.innerHTML = `<pre class="docs-pre">${_htmlEsc(fmt)}</pre>`;
      } else {
        cuerpo.innerHTML = `<pre class="docs-pre">${_htmlEsc(texto)}</pre>`;
      }
    } catch (e) {
      cuerpo.innerHTML = `<p style="color:var(--danger); padding:1rem;">Error al cargar: ${e.message}</p>`;
    }
  }
}

function _htmlEsc(str) {
  return str.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

// ── Subida ───────────────────────────────────────────────────────

function _docCambiarNivel(nivel) {
  document.getElementById("md-programa-sel").style.display = nivel === "programa"  ? "" : "none";
  document.getElementById("md-semestre-sel").style.display = nivel === "semestre"  ? "" : "none";
  document.getElementById("docs-materia").style.display    = nivel === "materia"   ? "" : "none";
}

function abrirModalSubirDoc() {
  document.getElementById("modal-doc").classList.add("open");
  document.getElementById("md-titulo").value  = "";
  document.getElementById("md-archivo").value = "";
  document.getElementById("md-tags").value    = "";
  document.getElementById("md-nivel").value   = "ninguno";
  _docCambiarNivel("ninguno");
  _poblarSelectsDocModal();
}

function _poblarSelectsDocModal() {
  const selProg = document.getElementById("md-programa-sel");
  const selSem  = document.getElementById("md-semestre-sel");
  selProg.innerHTML = '<option value="">— Seleccioná programa —</option>';
  selSem.innerHTML  = '<option value="">— Seleccioná semestre —</option>';
  (_estructura || []).forEach(prog => {
    if (prog.id) {
      const o = document.createElement("option");
      o.value = prog.id; o.textContent = prog.nombre;
      selProg.appendChild(o);
    }
    (prog.semestres || []).forEach(sem => {
      const o = document.createElement("option");
      o.value = sem.id; o.textContent = `${prog.nombre} › ${sem.nombre}`;
      selSem.appendChild(o);
    });
  });
}

function cerrarModalDoc() {
  document.getElementById("modal-doc").classList.remove("open");
}

async function subirDocumento() {
  const archivo = document.getElementById("md-archivo").files[0];
  const titulo  = document.getElementById("md-titulo").value.trim();
  const nivel   = document.getElementById("md-nivel").value;
  const tags    = document.getElementById("md-tags").value.trim();

  let programaId = "", semestreId = "", materiaId = "";
  if (nivel === "programa")  programaId = document.getElementById("md-programa-sel").value;
  if (nivel === "semestre")  semestreId = document.getElementById("md-semestre-sel").value;
  if (nivel === "materia")   materiaId  = document.getElementById("docs-materia").value;

  if (!archivo) { toast("Seleccioná un archivo"); return; }
  if (!titulo)  { toast("Escribí un título"); return; }

  const formData = new FormData();
  formData.append("archivo",     archivo);
  formData.append("titulo",      titulo);
  formData.append("materia_id",  materiaId);
  formData.append("semestre_id", semestreId);
  formData.append("programa_id", programaId);
  formData.append("tags",        tags);

  const btn = document.getElementById("btn-subir-doc");
  btn.disabled = true; btn.textContent = "Subiendo…";

  try {
    const r = await fetch("/documentos", { method: "POST", body: formData });
    if (!r.ok) {
      const err = await r.json().catch(() => ({ detail: r.statusText }));
      throw new Error(err.detail || r.statusText);
    }
    cerrarModalDoc();
    toast("Documento subido correctamente");
    cargarDocumentos();
  } catch (e) {
    toast(`Error: ${e.message}`, 4500);
  } finally {
    btn.disabled = false; btn.textContent = "Subir";
  }
}

// ── Eliminar ─────────────────────────────────────────────────────

async function eliminarDoc(id) {
  if (!confirm("¿Eliminar este documento?")) return;
  await api("DELETE", `/documentos/${id}`);
  if (_docActivoId === id) {
    _docActivoId = null;
    document.getElementById("docs-visor").innerHTML = `
      <div class="docs-visor-vacio">
        <div style="font-size:2.5rem">📄</div>
        <p>Seleccioná un documento para verlo aquí.</p>
      </div>`;
  }
  toast("Documento eliminado");
  cargarDocumentos();
}

// ── Sub-pestañas: Repositorio / Análisis ─────────────────────────

function _docsTab(tab) {
  _docsTabActual = tab;
  ["repo", "maia", "biblioteca"].forEach(t => {
    const panel = document.getElementById(`docs-tab-${t}`);
    const btn   = document.getElementById(`docs-stab-${t}`);
    if (panel) panel.style.display = t !== tab ? "none" : (t === "maia" ? "flex" : "flex");
    if (btn)   btn.classList.toggle("active", t === tab);
  });
  if (tab === "maia")       _poblarSelectMaia();
  if (tab === "biblioteca") _cargarBiblioteca();
}

async function _poblarSelectMaia() {
  const sel = document.getElementById("maia-doc-sel");
  if (!sel) return;
  const docs = await api("GET", "/documentos").catch(() => []);
  sel.innerHTML = '<option value="">— Todos los documentos —</option>' +
    docs.map(d => `<option value="${d.id}">${d.titulo}</option>`).join("");
}

// ── Chat con Maia ────────────────────────────────────────────────

async function _enviarMaia(e) {
  e.preventDefault();
  const input  = document.getElementById("maia-input");
  const texto  = input.value.trim();
  if (!texto) return;
  input.value  = "";
  _maiaUltimaPregunta = texto;

  const docId   = document.getElementById("maia-doc-sel")?.value || null;
  const msgArea = document.getElementById("maia-messages");

  _maiaMsg(msgArea, "user", texto);
  const asstDiv = _maiaMsg(msgArea, "assistant", "");
  const cursor  = document.createElement("span");
  cursor.className  = "cursor-blink";
  cursor.textContent = "▍";
  asstDiv.appendChild(cursor);

  let acumulado = "";

  try {
    const resp = await fetch("/documentos/analisis/stream", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        doc_id:    docId ? +docId : null,
        mensaje:   texto,
        historial: _maiaHistorial.slice(-10),
      }),
    });

    const reader  = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer    = "";
    let terminado = false;

    while (!terminado) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lineas = buffer.split("\n");
      buffer = lineas.pop();
      for (const linea of lineas) {
        if (!linea.startsWith("data: ")) continue;
        const payload = linea.slice(6).trim();
        if (payload === "[DONE]") { terminado = true; break; }
        try { acumulado += JSON.parse(payload); } catch { acumulado += payload; }
        asstDiv.textContent = acumulado;
        asstDiv.appendChild(cursor);
        msgArea.scrollTop = msgArea.scrollHeight;
      }
    }
  } catch (err) {
    acumulado = "Error al conectar con Maia.";
    console.error(err);
  }

  cursor.remove();
  asstDiv.innerHTML = marked.parse(acumulado);
  msgArea.scrollTop = msgArea.scrollHeight;

  _maiaHistorial.push(
    { role: "user",      content: texto },
    { role: "assistant", content: acumulado },
  );

  _maiaUltimaRespuesta = acumulado;
  _mostrarBotonGuardar();

  // Contador de tokens persistente
  _maiaToksAcum += Math.round((texto.length + acumulado.length) / 4);
  const tokEl = document.getElementById("maia-tok-count");
  if (tokEl) tokEl.textContent = "";
  const sesEl = document.getElementById("maia-tok-session");
  if (sesEl && _maiaToksAcum > 0) sesEl.textContent = `Sesión: ~${_maiaToksAcum} tokens`;
}

function _maiaMsg(msgArea, rol, contenido) {
  const row = document.createElement("div");
  row.className = `msg-row ${rol}`;

  const avatar = document.createElement("div");
  avatar.className = "msg-avatar";
  avatar.innerHTML = rol === "user"
    ? _avatarImg("aldebaran", "fi-rr-user")
    : _avatarImg("maia", "fi-rr-search");

  const div = document.createElement("div");
  div.className = `msg ${rol}`;
  if (contenido) div.innerHTML = rol === "assistant" ? marked.parse(contenido) : _htmlEsc(contenido);

  row.appendChild(avatar);
  row.appendChild(div);
  msgArea.appendChild(row);
  msgArea.scrollTop = msgArea.scrollHeight;
  return div;
}

// ── Listeners ────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("docs-filtro-materia")?.addEventListener("change", cargarDocumentos);
  document.getElementById("btn-subir-archivo")?.addEventListener("click", abrirModalSubirDoc);
  document.getElementById("maia-form")?.addEventListener("submit", _enviarMaia);

  // Contador de tokens en vivo para Maia
  const maiaInput    = document.getElementById("maia-input");
  const maiaTokCount = document.getElementById("maia-tok-count");
  if (maiaInput && maiaTokCount) {
    maiaInput.addEventListener("input", () => {
      const est = Math.round(maiaInput.value.length / 4);
      maiaTokCount.textContent = est > 0 ? `~${est} tok` : "";
    });
  }
});

// ── Biblioteca de Maia ───────────────────────────────────────────

function _mostrarBotonGuardar() {
  const existing = document.getElementById("maia-btn-guardar-wrap");
  if (existing) existing.remove();

  const wrap = document.createElement("div");
  wrap.id = "maia-btn-guardar-wrap";
  wrap.style.cssText = "padding:.3rem var(--gap) 0; flex-shrink:0;";
  wrap.innerHTML = `<button class="btn btn-secondary btn-sm" onclick="_guardarEnBiblioteca()" style="font-size:.75rem;">
    <i class="fi fi-rr-bookmark"></i> Guardar en Biblioteca
  </button>`;

  const form = document.getElementById("maia-form");
  if (form) form.parentNode.insertBefore(wrap, form);
}

async function _guardarEnBiblioteca() {
  if (!_maiaUltimaPregunta || !_maiaUltimaRespuesta) return;
  const docId    = document.getElementById("maia-doc-sel")?.value || null;
  const titulo   = _maiaUltimaPregunta.length > 80
    ? _maiaUltimaPregunta.slice(0, 77) + "…"
    : _maiaUltimaPregunta;

  try {
    await api("POST", "/documentos/biblioteca", {
      titulo,
      pregunta:   _maiaUltimaPregunta,
      respuesta:  _maiaUltimaRespuesta,
      doc_id:     docId ? +docId : null,
    });
    document.getElementById("maia-btn-guardar-wrap")?.remove();
    toast("Guardado en Biblioteca");
  } catch (e) {
    toast(`Error al guardar: ${e.message}`, 4000);
  }
}

async function _cargarBiblioteca() {
  const lista = document.getElementById("maia-biblioteca-lista");
  if (!lista) return;
  lista.innerHTML = '<p style="color:var(--text-muted); font-size:.875rem; text-align:center;">Cargando…</p>';
  try {
    const items = await api("GET", "/documentos/biblioteca");
    if (!items.length) {
      lista.innerHTML = '<p style="color:var(--text-muted); font-size:.875rem; text-align:center; padding-top:1.5rem;">Sin análisis guardados aún.<br>Hacé una consulta a Maia y guardala.</p>';
      return;
    }
    lista.innerHTML = items.map(it => `
      <div class="card" style="padding:.7rem .9rem;">
        <div style="display:flex; align-items:flex-start; gap:.5rem; margin-bottom:.45rem;">
          <div style="flex:1; min-width:0;">
            <div style="font-weight:700; font-size:.875rem; margin-bottom:.1rem;">${_htmlEsc(it.titulo)}</div>
            <div style="font-size:.72rem; color:var(--text-muted);">
              ${it.doc_titulo ? it.doc_titulo + ' · ' : ''}${it.creado_at ? it.creado_at.slice(0,10) : ''}
            </div>
          </div>
          <button class="cn-btn-icon" title="Eliminar" onclick="_eliminarBiblioteca(${it.id})">✕</button>
        </div>
        <details style="font-size:.84rem;">
          <summary style="cursor:pointer; color:var(--accent-h); font-size:.8rem; margin-bottom:.4rem;">Ver análisis completo</summary>
          <div style="margin-top:.4rem; padding:.5rem; background:var(--surface2); border-radius:var(--radius); border-left:3px solid var(--accent);">
            <div style="font-size:.75rem; color:var(--text-muted); margin-bottom:.3rem; font-weight:600;">PREGUNTA</div>
            <div style="margin-bottom:.6rem;">${_htmlEsc(it.pregunta)}</div>
            <div style="font-size:.75rem; color:var(--text-muted); margin-bottom:.3rem; font-weight:600;">RESPUESTA</div>
            <div>${marked.parse(it.respuesta)}</div>
          </div>
        </details>
      </div>`).join("");
  } catch (e) {
    lista.innerHTML = `<p style="color:var(--danger); font-size:.875rem;">Error: ${e.message}</p>`;
  }
}

async function _eliminarBiblioteca(id) {
  if (!confirm("¿Eliminar este análisis?")) return;
  await api("DELETE", `/documentos/biblioteca/${id}`);
  _cargarBiblioteca();
}

function _avatarImg(nombre, icon) {
  return `<img src="/static/img/${nombre}.png" class="msg-avatar-img" alt="${nombre}" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'"><i class="fi ${icon}" style="display:none;"></i>`;
}
