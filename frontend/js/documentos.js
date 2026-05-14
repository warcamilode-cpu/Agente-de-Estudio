// Módulo de repositorio de documentos

let _docActivoId = null;

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

function abrirModalSubirDoc() {
  document.getElementById("modal-doc").classList.add("open");
  document.getElementById("md-titulo").value  = "";
  document.getElementById("md-archivo").value = "";
  document.getElementById("md-tags").value    = "";
}

function cerrarModalDoc() {
  document.getElementById("modal-doc").classList.remove("open");
}

async function subirDocumento() {
  const archivo   = document.getElementById("md-archivo").files[0];
  const titulo    = document.getElementById("md-titulo").value.trim();
  const materiaId = document.getElementById("docs-materia").value;
  const tags      = document.getElementById("md-tags").value.trim();

  if (!archivo) { toast("Seleccioná un archivo"); return; }
  if (!titulo)  { toast("Escribí un título"); return; }

  const formData = new FormData();
  formData.append("archivo",    archivo);
  formData.append("titulo",     titulo);
  formData.append("materia_id", materiaId);
  formData.append("tags",       tags);

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

// ── Listeners ────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("docs-filtro-materia")?.addEventListener("change", cargarDocumentos);
  document.getElementById("btn-subir-archivo")?.addEventListener("click", abrirModalSubirDoc);
});
