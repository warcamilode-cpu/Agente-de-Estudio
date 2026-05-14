// Módulo de chat con sesiones persistentes + streaming SSE + Markdown

let _sessionId  = null;
let _primerMensaje = true;

const chatForm   = document.getElementById("chat-form");
const chatInput  = document.getElementById("chat-input");
const mensajesEl = document.getElementById("chat-messages");

// Arranca con una sesión nueva
nuevaSesionChat();

// ── Sesiones ─────────────────────────────────────────────────────

async function nuevaSesionChat() {
  const data = await api("POST", "/ai/chat/nueva-sesion");
  _sessionId        = data.session_id;
  _primerMensaje    = true;
  _tokensAcumulados = 0;
  mensajesEl.innerHTML = `
    <div class="msg-row assistant">
      <div class="msg-avatar">🌟</div>
      <div class="msg assistant shaula-intro">
        Hola, soy <strong>Shaula</strong>, tu tutora de estudio.
        Seleccioná un tema y preguntame lo que necesites.
      </div>
    </div>`;
  document.getElementById("chat-sesion-titulo").textContent = "Nueva sesión";
}

async function abrirSesiones() {
  const sesiones = await api("GET", "/ai/sesiones");
  const lista    = document.getElementById("sesiones-lista");
  lista.innerHTML = "";

  if (!sesiones.length) {
    lista.innerHTML = '<p style="color:var(--text-muted); text-align:center; padding:1rem;">Sin sesiones guardadas.</p>';
  } else {
    sesiones.forEach(s => {
      const div = document.createElement("div");
      div.className = "sesion-item";
      const fecha = new Date(s.actualizado_at + "Z").toLocaleString("es-CO", {
        day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
      });
      div.innerHTML = `
        <div class="sesion-info" onclick="cargarSesion('${s.session_id}', '${_esc(s.titulo)}')">
          <span class="sesion-titulo-item">${s.titulo}</span>
          <span class="sesion-meta">${fecha} · ${s.total_mensajes} mensajes</span>
        </div>
        <button class="btn btn-danger btn-sm" onclick="eliminarSesion('${s.session_id}')">✕</button>`;
      lista.appendChild(div);
    });
  }

  document.getElementById("modal-sesiones").classList.add("open");
}

async function cargarSesion(sessionId, titulo) {
  document.getElementById("modal-sesiones").classList.remove("open");

  const data = await api("GET", `/ai/chat/${sessionId}/historial`);
  _sessionId     = sessionId;
  _primerMensaje = false;

  document.getElementById("chat-sesion-titulo").textContent = titulo;
  mensajesEl.innerHTML = "";

  if (!data.mensajes.length) {
    mensajesEl.innerHTML = '<p style="color:var(--text-muted); text-align:center; padding:1rem;">Sesión vacía.</p>';
    return;
  }

  data.mensajes.forEach(m => _agregarMensaje(m.rol, m.contenido));
  mensajesEl.scrollTop = mensajesEl.scrollHeight;
}

async function eliminarSesion(sessionId) {
  if (!confirm("¿Eliminar esta sesión?")) return;
  await api("DELETE", `/ai/sesiones/${sessionId}`);
  if (sessionId === _sessionId) nuevaSesionChat();
  abrirSesiones();
}

// ── Enviar mensaje ────────────────────────────────────────────────

chatForm.addEventListener("submit", async e => {
  e.preventDefault();
  const texto = chatInput.value.trim();
  if (!texto || !_sessionId) return;
  chatInput.value = "";

  _agregarMensaje("user", texto);

  const materiaId = document.getElementById("chat-materia").value || null;
  const burbuja = _agregarMensaje("assistant", "");

  const cursor = document.createElement("span");
  cursor.className = "cursor-blink";
  cursor.textContent = "▍";
  burbuja.appendChild(cursor);

  let acumulado = "";

  try {
    const resp = await fetch("/ai/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: _sessionId,
        message:    texto,
        materia_id: materiaId ? +materiaId : null,
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
        burbuja.textContent = acumulado;
        burbuja.appendChild(cursor);
        mensajesEl.scrollTop = mensajesEl.scrollHeight;
      }
    }
  } catch (err) {
    acumulado = "Error al conectar con el servidor.";
    console.error(err);
  }

  cursor.remove();
  burbuja.innerHTML = marked.parse(acumulado);
  mensajesEl.scrollTop = mensajesEl.scrollHeight;

  _registrarTokens(texto, acumulado);
  document.getElementById("chat-token-count").textContent = "";

  // Actualiza el título de la barra con el primer mensaje
  if (_primerMensaje) {
    _primerMensaje = false;
    document.getElementById("chat-sesion-titulo").textContent =
      texto.length > 60 ? texto.slice(0, 60) + "…" : texto;
  }
});

// ── Contador de tokens ────────────────────────────────────────────

let _tokensAcumulados = 0;

(function _initTokenCounter() {
  const counter = document.getElementById("chat-token-count");
  if (!counter) return;

  chatInput.addEventListener("input", () => {
    const estimado = Math.round(chatInput.value.length / 4);
    counter.textContent = estimado > 0 ? `~${estimado} tok` : "";
  });
})();

function _registrarTokens(textoUsuario, textoAsistente) {
  const tokUser = Math.round(textoUsuario.length / 4);
  const tokAsis = Math.round(textoAsistente.length / 4);
  _tokensAcumulados += tokUser + tokAsis;
  const counter = document.getElementById("chat-token-count");
  if (counter && _tokensAcumulados > 0) {
    counter.title = `Sesión: ~${_tokensAcumulados} tokens acumulados`;
  }
}

// ── Helpers ──────────────────────────────────────────────────────

const _AVATARES_CHAT = { user: "👤", assistant: "🌟" };

function _agregarMensaje(rol, contenido) {
  const row = document.createElement("div");
  row.className = `msg-row ${rol}`;

  const avatar = document.createElement("div");
  avatar.className = "msg-avatar";
  avatar.textContent = _AVATARES_CHAT[rol] || "👤";

  const div = document.createElement("div");
  div.className = `msg ${rol}`;
  if (contenido) {
    div.innerHTML = rol === "assistant"
      ? marked.parse(contenido)
      : _escaparHTML(contenido);
  }

  row.appendChild(avatar);
  row.appendChild(div);
  mensajesEl.appendChild(row);
  mensajesEl.scrollTop = mensajesEl.scrollHeight;
  return div;
}

function _escaparHTML(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function _esc(str) {
  return str.replace(/'/g, "\\'").replace(/"/g, "&quot;");
}
