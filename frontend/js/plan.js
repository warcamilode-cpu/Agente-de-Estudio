// Módulo Planificador — plan por tema + Q&A + Evaluador

let _planActivo   = null;   // { id, tema, plan_texto }
let _planHistorial = [];    // conversación Q&A en memoria
let _modoEval     = false;  // true = agente Evaluador activo
let _planGenerando = false;

// ── Generar plan ─────────────────────────────────────────────────

async function generarPlan() {
  if (_planGenerando) return;

  const tema      = document.getElementById("plan-tema-input").value.trim();
  const materiaId = document.getElementById("plan-materia-sel").value || null;

  if (!tema) { toast("Escribí el tema que querés estudiar."); return; }

  _planGenerando = true;
  const btn = document.getElementById("btn-generar-plan");
  btn.disabled    = true;
  btn.textContent = "Generando…";

  // Ocultar historial si estaba visible
  ocultarHistorial();

  // Mostrar estado de carga
  document.getElementById("plan-resultado").style.display = "none";
  const formArea = document.getElementById("plan-form-area");
  formArea.insertAdjacentHTML("afterend",
    '<p id="plan-loading" style="color:var(--text-muted); font-size:.875rem; margin:.5rem 0;">⏳ Shaula está generando los 4 módulos… (puede tardar ~20 s)</p>'
  );

  try {
    const data = await api("POST", "/plan/planificador", {
      tema,
      materia_id: materiaId ? +materiaId : null,
    });

    _planActivo   = data;
    _planHistorial = [];
    _modoEval     = false;

    _mostrarPlan(data);

  } catch (e) {
    toast(`Error al generar el plan: ${e.message}`, 5000);
  } finally {
    document.getElementById("plan-loading")?.remove();
    btn.disabled    = false;
    btn.textContent = "Generar plan completo";
    _planGenerando  = false;
  }
}

function _mostrarPlan(data) {
  const resultado = document.getElementById("plan-resultado");
  const contenido = document.getElementById("plan-contenido");
  const fecha     = document.getElementById("plan-fecha");

  contenido.innerHTML = marked.parse(data.plan_texto);
  fecha.textContent   = "Generado el " + new Date().toLocaleDateString("es-CO", {
    weekday: "long", year: "numeric", month: "long", day: "numeric",
  }) + (data.materia_nombre && data.materia_nombre !== "—" ? ` · ${data.materia_nombre}` : "");

  // Limpiar chat Q&A
  document.getElementById("plan-chat-messages").innerHTML = "";
  _planHistorial = [];
  _modoEval      = false;

  resultado.style.display = "block";
  resultado.scrollIntoView({ behavior: "smooth", block: "start" });
}

// ── Nuevo plan ───────────────────────────────────────────────────

function nuevoPlan() {
  _planActivo    = null;
  _planHistorial = [];
  _modoEval      = false;
  document.getElementById("plan-resultado").style.display = "none";
  document.getElementById("plan-tema-input").value = "";
  document.getElementById("plan-tema-input").focus();
}

// ── Evaluador ────────────────────────────────────────────────────

function activarEvaluador() {
  if (!_planActivo) return;
  _modoEval = true;

  const msgArea = document.getElementById("plan-chat-messages");
  const header  = document.getElementById("plan-chat-area").querySelector("h3");
  header.textContent  = "🎯 Agente Evaluador";
  header.style.color  = "var(--brand)";

  // Mensaje de activación
  const div = document.createElement("div");
  div.className = "msg assistant";
  div.style.cssText = "font-size:.875rem; line-height:1.7;";
  div.innerHTML = "<em>Activando el agente Evaluador… Escribí <strong>empezar</strong> para iniciar la evaluación.</em>";
  msgArea.appendChild(div);
  msgArea.scrollTop = msgArea.scrollHeight;

  document.getElementById("plan-chat-input").focus();
}

// ── Chat Q&A ─────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("btn-generar-plan");
  if (btn) btn.addEventListener("click", generarPlan);

  const form = document.getElementById("plan-chat-form");
  if (form) form.addEventListener("submit", _enviarPregunta);
});

async function _enviarPregunta(e) {
  e.preventDefault();
  if (!_planActivo) return;

  const input   = document.getElementById("plan-chat-input");
  const texto   = input.value.trim();
  if (!texto) return;
  input.value   = "";

  const msgArea = document.getElementById("plan-chat-messages");

  // Burbuja usuario
  const userDiv = document.createElement("div");
  userDiv.className = "msg user";
  userDiv.style.cssText = "font-size:.875rem;";
  userDiv.textContent   = texto;
  msgArea.appendChild(userDiv);
  msgArea.scrollTop = msgArea.scrollHeight;

  // Burbuja asistente (vacía con cursor)
  const asstDiv = document.createElement("div");
  asstDiv.className = "msg assistant";
  asstDiv.style.cssText = "font-size:.875rem; line-height:1.7;";
  const cursor = document.createElement("span");
  cursor.className  = "cursor-blink";
  cursor.textContent = "▍";
  asstDiv.appendChild(cursor);
  msgArea.appendChild(asstDiv);
  msgArea.scrollTop = msgArea.scrollHeight;

  let acumulado = "";

  try {
    const resp = await fetch("/plan/planificador/chat/stream", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        plan_id:   _planActivo.id,
        mensaje:   texto,
        historial: _planHistorial.slice(-14),  // últimos 7 turnos
        modo:      _modoEval ? "evaluador" : "chat",
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
        try {
          acumulado += JSON.parse(payload);
          asstDiv.textContent = acumulado;
          asstDiv.appendChild(cursor);
          msgArea.scrollTop = msgArea.scrollHeight;
        } catch (_) {}
      }
    }
  } catch (err) {
    acumulado = "Error al conectar con Shaula.";
    console.error(err);
  }

  cursor.remove();
  asstDiv.innerHTML = marked.parse(acumulado);
  msgArea.scrollTop = msgArea.scrollHeight;

  // Actualizar historial en memoria
  _planHistorial.push(
    { role: "user",      content: texto },
    { role: "assistant", content: acumulado },
  );
}

// ── Historial de planes guardados ────────────────────────────────

async function verHistorialPlanes() {
  const area  = document.getElementById("plan-historial-area");
  const lista = document.getElementById("plan-historial-lista");

  area.style.display  = "block";
  lista.innerHTML     = '<p style="color:var(--text-muted); font-size:.85rem;">Cargando…</p>';

  try {
    const planes = await api("GET", "/plan/planificador/planes");
    if (!planes.length) {
      lista.innerHTML = '<p style="color:var(--text-muted); font-size:.85rem;">Sin planes guardados todavía.</p>';
      return;
    }
    lista.innerHTML = planes.map(p => `
      <div class="card" style="display:flex; align-items:center; gap:.75rem; padding:.6rem .8rem; cursor:pointer;"
           onclick="restaurarPlan(${p.id})">
        <div style="flex:1; min-width:0;">
          <div style="font-weight:600; font-size:.875rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${p.tema}</div>
          <div style="font-size:.75rem; color:var(--text-muted);">${p.materia_nombre} · ${p.creado_at.slice(0,10)}</div>
        </div>
        <span style="font-size:.75rem; color:var(--accent);">Ver ›</span>
      </div>`).join("");
  } catch (e) {
    lista.innerHTML = `<p style="color:var(--danger); font-size:.85rem;">Error: ${e.message}</p>`;
  }
}

function ocultarHistorial() {
  document.getElementById("plan-historial-area").style.display = "none";
}

async function restaurarPlan(planId) {
  ocultarHistorial();
  try {
    const data = await api("GET", `/plan/planificador/planes/${planId}`);
    _planActivo    = data;
    _planHistorial = [];
    _modoEval      = false;

    // Resetear header del chat
    const header = document.getElementById("plan-chat-area")?.querySelector("h3");
    if (header) {
      header.textContent = "Preguntale al Planificador sobre este tema";
      header.style.color = "var(--accent)";
    }

    _mostrarPlan(data);
  } catch (e) {
    toast(`Error al cargar el plan: ${e.message}`, 4000);
  }
}
