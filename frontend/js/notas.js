// Módulo de notas

let _notaEditandoId = null;

async function cargarNotas() {
  const q       = document.getElementById("notas-busqueda").value;
  const topicId = document.getElementById("notas-filtro-topic").value;
  const params  = new URLSearchParams();
  if (q)       params.set("q", q);
  if (topicId) params.set("topic_id", topicId);

  const notas = await api("GET", `/notas?${params}`);
  const lista = document.getElementById("notas-lista");
  lista.innerHTML = "";

  if (!notas.length) {
    lista.innerHTML = '<p style="color:var(--text-muted); text-align:center; padding:2rem;">Sin notas todavía.</p>';
    return;
  }

  notas.forEach(n => {
    const div = document.createElement("div");
    div.className = "nota-item";
    const tags = n.tags ? n.tags.split(",").map(t => `<span class="tag">${t.trim()}</span>`).join("") : "";
    div.innerHTML = `
      <div>
        <div class="titulo">${n.titulo}</div>
        <div class="meta">${tags}</div>
      </div>
      <div class="row">
        <button class="btn btn-secondary btn-sm" onclick="editarNota(${n.id})">Editar</button>
        <button class="btn btn-danger btn-sm" onclick="eliminarNota(${n.id})">Borrar</button>
      </div>`;
    lista.appendChild(div);
  });
}

document.getElementById("notas-busqueda").addEventListener("input", () => cargarNotas());
document.getElementById("notas-filtro-topic").addEventListener("change", () => cargarNotas());
document.getElementById("btn-nueva-nota").addEventListener("click", () => abrirModalNota());

function abrirModalNota(nota = null) {
  _notaEditandoId = nota ? nota.id : null;
  document.getElementById("modal-nota-titulo").textContent = nota ? "Editar nota" : "Nueva nota";
  document.getElementById("mn-titulo").value    = nota?.titulo    ?? "";
  document.getElementById("mn-tags").value      = nota?.tags      ?? "";
  document.getElementById("mn-contenido").value = nota?.contenido ?? "";
  document.getElementById("mn-topic").value     = nota?.topic_id  ?? "";
  document.getElementById("modal-nota").classList.add("open");
}

function cerrarModalNota() {
  document.getElementById("modal-nota").classList.remove("open");
  _notaEditandoId = null;
}

async function guardarNota() {
  const body = {
    titulo:    document.getElementById("mn-titulo").value.trim(),
    contenido: document.getElementById("mn-contenido").value.trim(),
    tags:      document.getElementById("mn-tags").value.trim(),
    topic_id:  document.getElementById("mn-topic").value || null,
  };
  if (!body.titulo || !body.contenido) { toast("Título y contenido son obligatorios"); return; }

  if (_notaEditandoId) {
    await api("PUT", `/notas/${_notaEditandoId}`, body);
    toast("Nota actualizada");
  } else {
    await api("POST", "/notas", body);
    toast("Nota creada");
  }
  cerrarModalNota();
  cargarNotas();
}

async function editarNota(id) {
  const nota = await api("GET", `/notas/${id}`);
  abrirModalNota(nota);
}

async function eliminarNota(id) {
  if (!confirm("¿Eliminar esta nota?")) return;
  await api("DELETE", `/notas/${id}`);
  toast("Nota eliminada");
  cargarNotas();
}
