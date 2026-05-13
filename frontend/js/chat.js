// Módulo de chat con streaming SSE + renderizado Markdown

let _sessionId = null;

async function _iniciarSesion() {
  const data = await api("POST", "/ai/chat/nueva-sesion");
  _sessionId = data.session_id;
}

_iniciarSesion();

const chatForm   = document.getElementById("chat-form");
const chatInput  = document.getElementById("chat-input");
const mensajesEl = document.getElementById("chat-messages");

chatForm.addEventListener("submit", async e => {
  e.preventDefault();
  const texto = chatInput.value.trim();
  if (!texto) return;
  chatInput.value = "";

  if (!_sessionId) await _iniciarSesion();

  _agregarMensaje("user", texto);

  const topicId  = document.getElementById("chat-topic").value || null;
  const burbuja  = _agregarMensaje("assistant", "");
  const cursor   = document.createElement("span");
  cursor.className = "cursor-blink";
  cursor.textContent = "▍";
  burbuja.appendChild(cursor);

  let acumulado = "";
  let terminado = false;

  try {
    const resp = await fetch("/ai/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: _sessionId,
        message: texto,
        topic_id: topicId ? +topicId : null,
      }),
    });

    const reader  = resp.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const lineas = decoder.decode(value).split("\n");
      for (const linea of lineas) {
        if (!linea.startsWith("data: ")) continue;
        const chunk = linea.slice(6);
        if (chunk === "[DONE]") { terminado = true; break; }
        acumulado += chunk;
        // Durante el streaming: texto plano para no romper markdown parcial
        burbuja.textContent = acumulado;
        burbuja.appendChild(cursor);
        mensajesEl.scrollTop = mensajesEl.scrollHeight;
      }
      if (terminado) break;
    }
  } catch (err) {
    acumulado = "Error al conectar con el servidor.";
    console.error(err);
  }

  // Al terminar: renderiza Markdown completo
  cursor.remove();
  burbuja.innerHTML = marked.parse(acumulado);
  mensajesEl.scrollTop = mensajesEl.scrollHeight;
});

function _agregarMensaje(rol, texto) {
  const div = document.createElement("div");
  div.className = `msg ${rol}`;
  if (texto) {
    div.innerHTML = rol === "assistant" ? marked.parse(texto) : _escaparHTML(texto);
  }
  mensajesEl.appendChild(div);
  mensajesEl.scrollTop = mensajesEl.scrollHeight;
  return div;
}

function _escaparHTML(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
