// Módulo de repositorio de documentos

async function cargarDocumentos() {
  const topicId = document.getElementById("docs-filtro-topic")?.value || "";
  const ruta = topicId ? `/documentos?topic_id=${topicId}` : "/documentos";
  const docs = await api("GET", ruta);
  _renderDocumentos(docs);
}

function _renderDocumentos(docs) {
  const lista = document.getElementById("docs-lista");
  if (!docs.length) {
    lista.innerHTML = '<p style="color:var(--text-muted)">No hay documentos todavía. Subí una lectura, guía o presentación en PDF, TXT, MD o JSON.</p>';
    return;
  }
  lista.innerHTML = docs.map(d => `
    <div class="card" style="display:flex; align-items:center; gap:1rem;">
      <span style="font-size:1.6rem">${_iconTipo(d.tipo)}</span>
      <div style="flex:1; min-width:0;">
        <div style="font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${d.titulo}</div>
        <div style="font-size:.8rem; color:var(--text-muted);">
          ${d.tipo.toUpperCase()}${d.tags ? ' · ' + d.tags : ''} · ${_fechaCorta(d.creado_at)}
        </div>
      </div>
      <div style="display:flex; gap:.4rem; flex-shrink:0;">
        <button class="btn btn-secondary btn-sm" onclick="verDocumento(${d.id},'${_escDoc(d.titulo)}','${d.tipo}')">👁 Ver</button>
        <button class="btn btn-danger btn-sm" onclick="eliminarDoc(${d.id})">Eliminar</button>
      </div>
    </div>`).join("");
}

function _iconTipo(tipo) {
  return { pdf: "📄", txt: "📃", md: "📝", json: "🔧" }[tipo] || "📁";
}

function _fechaCorta(ts) { return ts ? ts.slice(0, 10) : ""; }
function _escDoc(str)    { return String(str||"").replace(/'/g,"\\'").replace(/"/g,'&quot;'); }

// ── Visor embebido ───────────────────────────────────────────────

async function verDocumento(id, titulo, tipo) {
  const modal   = document.getElementById("modal-doc-visor");
  const tituloEl = document.getElementById("mdv-titulo");
  const cuerpo  = document.getElementById("mdv-cuerpo");

  tituloEl.textContent = titulo;
  cuerpo.innerHTML = '<p style="color:var(--text-muted)">Cargando…</p>';
  modal.classList.add("open");

  if (tipo === "pdf") {
    cuerpo.innerHTML = `<iframe src="/documentos/${id}/archivo" style="width:100%; height:70dvh; border:none; border-radius:8px;"></iframe>`;
  } else {
    try {
      const resp = await fetch(`/documentos/${id}/archivo`);
      const texto = await resp.text();
      if (tipo === "md") {
        cuerpo.innerHTML = `<div class="msg assistant" style="max-width:100%; background:var(--surface2);">${marked.parse(texto)}</div>`;
      } else if (tipo === "json") {
        let formateado;
        try { formateado = JSON.stringify(JSON.parse(texto), null, 2); } catch { formateado = texto; }
        cuerpo.innerHTML = `<pre style="white-space:pre-wrap; font-family:ui-monospace,monospace; font-size:.82rem; line-height:1.6;">${_htmlEsc(formateado)}</pre>`;
      } else {
        cuerpo.innerHTML = `<pre style="white-space:pre-wrap; font-size:.875rem; line-height:1.7;">${_htmlEsc(texto)}</pre>`;
      }
    } catch (e) {
      cuerpo.innerHTML = `<p style="color:var(--danger)">Error al cargar: ${e.message}</p>`;
    }
  }
}

function _htmlEsc(str) {
  return str.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

function cerrarVisorDoc() {
  document.getElementById("modal-doc-visor").classList.remove("open");
  document.getElementById("mdv-cuerpo").innerHTML = "";
}

// ── Subida ───────────────────────────────────────────────────────

function abrirModalSubirDoc() {
  document.getElementById("modal-doc").classList.add("open");
  document.getElementById("md-titulo").value  = "";
  document.getElementById("md-archivo").value = "";
  document.getElementById("md-tags").value    = "";
  _poblarSelectDocs();
}

function cerrarModalDoc() {
  document.getElementById("modal-doc").classList.remove("open");
}

function _poblarSelectDocs() {
  const sel = document.getElementById("md-topic");
  if (!sel) return;
  sel.innerHTML = '<option value="">— Sin tema —</option>';
  _topics.forEach(t => {
    const opt = document.createElement("option");
    opt.value = t.id;
    opt.textContent = t.nombre;
    sel.appendChild(opt);
  });
}

async function subirDocumento() {
  const archivo = document.getElementById("md-archivo").files[0];
  const titulo  = document.getElementById("md-titulo").value.trim();
  const topicId = document.getElementById("md-topic").value;
  const tags    = document.getElementById("md-tags").value.trim();

  if (!archivo) { toast("Seleccioná un archivo"); return; }
  if (!titulo)  { toast("Escribí un título"); return; }

  const formData = new FormData();
  formData.append("archivo", archivo);
  formData.append("titulo", titulo);
  formData.append("topic_id", topicId);
  formData.append("tags", tags);

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
  toast("Documento eliminado");
  cargarDocumentos();
}

// ── Listeners ────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("docs-filtro-topic")?.addEventListener("change", cargarDocumentos);
  document.getElementById("btn-subir-archivo")?.addEventListener("click", abrirModalSubirDoc);
});
