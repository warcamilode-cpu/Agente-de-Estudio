// Módulo de flashcards

let _cardEditandoId = null;
let _pendientes = [];
let _pendienteIdx = 0;

// ── Carga lista ──────────────────────────────────────────────────
async function cargarFlashcards() {
  const materiaId = document.getElementById("fc-filtro-materia").value;
  const params = materiaId ? `?materia_id=${materiaId}` : "";
  const cards = await api("GET", `/flashcards${params}`);

  const lista = document.getElementById("fc-lista");
  lista.innerHTML = "";

  if (!cards.length) {
    lista.innerHTML = '<p style="color:var(--text-muted); text-align:center; padding:2rem;">Sin flashcards todavía.</p>';
    return;
  }

  cards.forEach(c => {
    const div = document.createElement("div");
    div.className = "card";
    div.style.display = "flex";
    div.style.justifyContent = "space-between";
    div.style.alignItems = "center";
    div.style.gap = ".5rem";
    div.innerHTML = `
      <div>
        <strong>${c.pregunta.substring(0, 80)}${c.pregunta.length > 80 ? "…" : ""}</strong>
        <div style="font-size:.78rem;color:var(--text-muted);">Próximo repaso: ${c.proximo_repaso} · Intervalo: ${c.intervalo}d</div>
      </div>
      <div class="row">
        <button class="btn btn-secondary btn-sm" onclick="editarCard(${c.id})">Editar</button>
        <button class="btn btn-danger btn-sm" onclick="eliminarCard(${c.id})">Borrar</button>
      </div>`;
    lista.appendChild(div);
  });
}

document.getElementById("fc-filtro-materia").addEventListener("change", cargarFlashcards);
document.getElementById("btn-nueva-card").addEventListener("click", () => abrirModalCard());

// ── Modal flashcard ──────────────────────────────────────────────
function abrirModalCard(card = null) {
  _cardEditandoId = card ? card.id : null;
  document.getElementById("modal-card-titulo").textContent = card ? "Editar flashcard" : "Nueva flashcard";
  document.getElementById("mc-pregunta").value  = card?.pregunta   ?? "";
  document.getElementById("mc-respuesta").value = card?.respuesta  ?? "";
  document.getElementById("mc-materia").value   = card?.materia_id ?? "";
  document.getElementById("modal-card").classList.add("open");
}

function cerrarModalCard() {
  document.getElementById("modal-card").classList.remove("open");
  _cardEditandoId = null;
}

async function guardarCard() {
  const body = {
    pregunta:   document.getElementById("mc-pregunta").value.trim(),
    respuesta:  document.getElementById("mc-respuesta").value.trim(),
    materia_id: document.getElementById("mc-materia").value || null,
  };
  if (!body.pregunta || !body.respuesta) { toast("Pregunta y respuesta son obligatorias"); return; }

  if (_cardEditandoId) {
    await api("PUT", `/flashcards/${_cardEditandoId}`, body);
    toast("Flashcard actualizada");
  } else {
    await api("POST", "/flashcards", body);
    toast("Flashcard creada");
  }
  cerrarModalCard();
  cargarFlashcards();
}

async function editarCard(id) {
  const cards = await api("GET", "/flashcards");
  const card  = cards.find(c => c.id === id);
  if (card) abrirModalCard(card);
}

async function eliminarCard(id) {
  if (!confirm("¿Eliminar esta flashcard?")) return;
  await api("DELETE", `/flashcards/${id}`);
  toast("Flashcard eliminada");
  cargarFlashcards();
}

// ── Modo repaso ──────────────────────────────────────────────────
document.getElementById("btn-modo-repaso").addEventListener("click", iniciarRepaso);

async function iniciarRepaso() {
  const materiaId = document.getElementById("fc-filtro-materia").value;
  const params    = materiaId ? `?materia_id=${materiaId}` : "";
  _pendientes     = await api("GET", `/flashcards/pendientes${params}`);

  if (!_pendientes.length) { toast("No hay cards pendientes hoy 🎉"); return; }

  _pendienteIdx = 0;
  document.getElementById("fc-lista").style.display = "none";
  document.getElementById("fc-repaso").style.display = "flex";
  mostrarCardActual();
}

function mostrarCardActual() {
  if (_pendienteIdx >= _pendientes.length) {
    fcSalirRepaso();
    toast("¡Repaso completado! 🎉");
    return;
  }
  const card = _pendientes[_pendienteIdx];
  const flip = document.getElementById("fc-flip");
  flip.classList.remove("flipped");
  document.getElementById("fc-pregunta").textContent  = card.pregunta;
  document.getElementById("fc-respuesta").textContent = card.respuesta;
  document.getElementById("fc-rating-row").style.display = "none";
  document.getElementById("fc-repaso-contador").textContent =
    `Card ${_pendienteIdx + 1} de ${_pendientes.length}`;
}

function fcFlip() {
  document.getElementById("fc-flip").classList.toggle("flipped");
  document.getElementById("fc-rating-row").style.display = "flex";
}

async function fcCalificar(cal) {
  const card = _pendientes[_pendienteIdx];
  await api("POST", `/flashcards/${card.id}/respuesta`, { calificacion: cal });
  _pendienteIdx++;
  mostrarCardActual();
}

function fcSalirRepaso() {
  document.getElementById("fc-repaso").style.display = "none";
  document.getElementById("fc-lista").style.display  = "flex";
  cargarFlashcards();
}
