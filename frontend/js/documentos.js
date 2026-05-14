// Módulo de repositorio de documentos

let _docEditandoId = null;

async function cargarDocumentos() {
  const topicId = document.getElementById("docs-filtro-topic")?.value || "";
  const ruta = topicId ? `/documentos?topic_id=${topicId}` : "/documentos";
  const docs = await api("GET", ruta);
  _renderDocumentos(docs);
}

function _renderDocumentos(docs) {
  const lista = document.getElementById("docs-lista");
  if (!docs.length) {
    lista.innerHTML = '<p style="color:var(--text-muted)">No hay documentos todavía. Subí una lectura, guía o presentación.</p>';
    return;
  }
  lista.innerHTML = docs.map(d => `
    <div class="card" style="display:flex; align-items:center; gap:1rem;">
      <span style="font-size:1.6rem">${_iconTipo(d.tipo)}</span>
      <div style="flex:1; min-width:0;">
        <div style="font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${d.titulo}</div>
        <div style="font-size:.8rem; color:var(--text-muted);">
          ${d.tipo.toUpperCase()}
          ${d.tags ? ' · ' + d.tags : ''}
          · ${_fechaCorta(d.creado_at)}
        </div>
      </div>
      <div style="display:flex; gap:.4rem; flex-shrink:0;">
        <button class="btn btn-secondary btn-sm" onclick="verTextoDoc(${d.id}, '${_esc(d.titulo)}')">Ver texto</button>
        <button class="btn btn-danger btn-sm" onclick="eliminarDoc(${d.id})">Eliminar</button>
      </div>
    </div>
  `).join("");
}

function _iconTipo(tipo) {
  return { pdf: "📄", docx: "📝", doc: "📝", txt: "📃" }[tipo] || "📁";
}

function _fechaCorta(ts) {
  return ts ? ts.slice(0, 10) : "";
}

function _esc(str) {
  return str.replace(/'/g, "\\'");
}

// ── Subida ──────────────────────────────────────────────────────

function abrirModalSubirDoc() {
  document.getElementById("modal-doc").classList.add("open");
  document.getElementById("md-titulo").value = "";
  document.getElementById("md-archivo").value = "";
  document.getElementById("md-tags").value = "";
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
  btn.disabled = true;
  btn.textContent = "Subiendo…";

  try {
    const r = await fetch("/documentos", { method: "POST", body: formData });
    if (!r.ok) {
      const err = await r.json().catch(() => ({ detail: r.statusText }));
      throw new Error(err.detail || r.statusText);
    }
    cerrarModalDoc();
    toast("Documento subido y texto extraído");
    cargarDocumentos();
  } catch (e) {
    toast(`Error: ${e.message}`, 4000);
  } finally {
    btn.disabled = false;
    btn.textContent = "Subir";
  }
}

// ── Ver texto extraído ───────────────────────────────────────────

async function verTextoDoc(id, titulo) {
  const doc = await api("GET", `/documentos/${id}`);
  const modal = document.getElementById("modal-doc-texto");
  document.getElementById("mdt-titulo").textContent = titulo;
  document.getElementById("mdt-contenido").textContent = doc.contenido_texto || "(Sin texto extraído)";
  modal.classList.add("open");
}

function cerrarModalDocTexto() {
  document.getElementById("modal-doc-texto").classList.remove("open");
}

// ── Eliminar ─────────────────────────────────────────────────────

async function eliminarDoc(id) {
  if (!confirm("¿Eliminar este documento?")) return;
  await api("DELETE", `/documentos/${id}`);
  toast("Documento eliminado");
  cargarDocumentos();
}

// ── Filtro por tema ──────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  const filtro = document.getElementById("docs-filtro-topic");
  if (filtro) filtro.addEventListener("change", cargarDocumentos);

  const btnSubir = document.getElementById("btn-subir-archivo");
  if (btnSubir) btnSubir.addEventListener("click", abrirModalSubirDoc);
});
