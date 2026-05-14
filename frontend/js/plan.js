// Módulo Planificador — plan por tema + Q&A + Evaluador

let _planActivo      = null;   // { id, tema, plan_texto }
let _planHistorial   = [];     // conversación Q&A en memoria
let _modoEval        = false;  // true = agente Evaluador activo
let _planGenerando   = false;
let _examenIniciado  = false;  // Electra: no volver a disparar si ya inició
let _planToksAcum    = 0;      // tokens acumulados en el chat del plan

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

    _planActivo     = data;
    _planHistorial  = [];
    _modoEval       = false;
    _examenIniciado = false;
    _planToksAcum   = 0;

    _mostrarPlan(data);

    // Si hay cronograma habilitado, guardarlo
    if (document.getElementById("plan-sched-toggle")?.checked) {
      _guardarCronograma(tema);
    }

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

  // Limpiar chat Q&A y resetear agente
  document.getElementById("plan-chat-messages").innerHTML = "";
  _planHistorial = [];
  _modoEval      = false;
  _actualizarIndicadorAgente();

  // Ocultar formulario de generación — el plan ocupa el espacio
  document.getElementById("plan-form-area").style.display = "none";

  resultado.style.display = "flex";
}

// ── Nuevo plan ───────────────────────────────────────────────────

function nuevoPlan() {
  _planActivo     = null;
  _planHistorial  = [];
  _modoEval       = false;
  _examenIniciado = false;
  _planToksAcum   = 0;
  document.getElementById("plan-resultado").style.display = "none";
  document.getElementById("plan-form-area").style.display = "";
  document.getElementById("plan-tema-input").value = "";
  // Resetear cronograma
  const toggle = document.getElementById("plan-sched-toggle");
  if (toggle) { toggle.checked = false; toggleCronograma(); }
  document.getElementById("plan-tema-input").focus();
}

// ── Indicador de agente activo ───────────────────────────────────

function _actualizarIndicadorAgente() {
  const badge = document.getElementById("plan-agente-badge");
  const desc  = document.getElementById("plan-agente-desc");
  const btn   = document.getElementById("btn-toggle-evaluador");
  const input = document.getElementById("plan-chat-input");
  if (!badge) return;

  if (_modoEval) {
    badge.textContent = "⚡ Agente Electra";
    badge.className   = "plan-agente-badge plan-agente-eval";
    desc.textContent  = "Evaluadora — verificando tu comprensión del tema";
    btn.textContent   = "🗺️ Volver a Atlas";
    input.placeholder = "Respondé las preguntas de Electra…";
  } else {
    badge.textContent = "🗺️ Agente Atlas";
    badge.className   = "plan-agente-badge plan-agente-plan";
    desc.textContent  = "Planificador — responde dudas sobre el plan";
    btn.textContent   = "⚡ Activar Electra";
    input.placeholder = "¿Tenés dudas sobre algún paso del plan?";
  }
}

function toggleEvaluador() {
  if (!_planActivo) return;
  _modoEval = !_modoEval;
  _actualizarIndicadorAgente();

  const msgArea = document.getElementById("plan-chat-messages");
  const aviso   = document.createElement("div");
  aviso.style.cssText = "font-size:.78rem; color:var(--text-muted); text-align:center; padding:.3rem 0;";
  aviso.textContent   = _modoEval
    ? "— Agente Electra (evaluadora) activada —"
    : "— Volviste al Agente Atlas (planificador) —";
  msgArea.appendChild(aviso);
  msgArea.scrollTop = msgArea.scrollHeight;

  // Solo dispara el examen la primera vez que se activa Electra
  if (_modoEval && !_examenIniciado) {
    _examenIniciado = true;
    _dispararMensajeEvaluador();
  }

  document.getElementById("plan-chat-input").focus();
}

async function _dispararMensajeEvaluador() {
  // Envía un mensaje silencioso para que el Evaluador se presente y empiece
  const evento = new Event("submit");
  const inputReal = document.getElementById("plan-chat-input");
  const valAnterior = inputReal.value;
  inputReal.value = "Comenzá la evaluación.";
  document.getElementById("plan-chat-form").dispatchEvent(evento);
  // el form limpia el input; restauramos nada (era vacío antes)
  void valAnterior;
}

// ── Chat Q&A ─────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("btn-generar-plan");
  if (btn) btn.addEventListener("click", generarPlan);

  const form = document.getElementById("plan-chat-form");
  if (form) form.addEventListener("submit", _enviarPregunta);

  // Contador de tokens del chat del plan
  const planInput    = document.getElementById("plan-chat-input");
  const planTokCount = document.getElementById("plan-tok-count");
  if (planInput && planTokCount) {
    planInput.addEventListener("input", () => {
      const est = Math.round(planInput.value.length / 4);
      planTokCount.textContent = est > 0 ? `~${est} tok` : "";
    });
  }

  // Iniciar notificaciones programadas (si hay permiso)
  _iniciarNotificaciones();
});

async function _enviarPregunta(e) {
  e.preventDefault();
  if (!_planActivo) return;

  const input   = document.getElementById("plan-chat-input");
  const texto   = input.value.trim();
  if (!texto) return;
  input.value   = "";

  const msgArea = document.getElementById("plan-chat-messages");

  // Burbuja usuario con avatar
  _planBurbuja(msgArea, "user", texto);

  // Burbuja asistente (vacía con cursor)
  const asstDiv = _planBurbuja(msgArea, "assistant", "");
  const cursor = document.createElement("span");
  cursor.className  = "cursor-blink";
  cursor.textContent = "▍";
  asstDiv.appendChild(cursor);
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

  // Historial en memoria
  _planHistorial.push(
    { role: "user",      content: texto },
    { role: "assistant", content: acumulado },
  );

  // Contador de tokens
  _planToksAcum += Math.round((texto.length + acumulado.length) / 4);
  const tokEl = document.getElementById("plan-tok-count");
  if (tokEl) { tokEl.textContent = ""; tokEl.title = `~${_planToksAcum} tokens en esta sesión`; }
}

// ── Helper burbuja con avatar para el chat del plan ───────────────

function _planBurbuja(msgArea, rol, contenido) {
  const row = document.createElement("div");
  row.className = `msg-row ${rol}`;

  const avatar = document.createElement("div");
  avatar.className = "msg-avatar";
  if (rol === "user") {
    avatar.textContent = "👤";
  } else {
    avatar.textContent = _modoEval ? "⚡" : "🗺️";
  }

  const div = document.createElement("div");
  div.className = `msg ${rol}`;
  if (contenido) div.textContent = contenido;

  row.appendChild(avatar);
  row.appendChild(div);
  msgArea.appendChild(row);
  msgArea.scrollTop = msgArea.scrollHeight;
  return div;
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
    _planActivo     = data;
    _planHistorial  = [];
    _modoEval       = false;
    _examenIniciado = false;
    _planToksAcum   = 0;
    _actualizarIndicadorAgente();
    _mostrarPlan(data);
  } catch (e) {
    toast(`Error al cargar el plan: ${e.message}`, 4000);
  }
}

// ── Cronograma y notificaciones web ──────────────────────────────

function toggleCronograma() {
  const checked = document.getElementById("plan-sched-toggle")?.checked;
  const fields  = document.getElementById("plan-sched-fields");
  if (fields) fields.style.display = checked ? "" : "none";
  if (checked) _solicitarPermisoNotif();
}

async function _solicitarPermisoNotif() {
  if (!("Notification" in window)) {
    toast("Tu navegador no soporta notificaciones web"); return;
  }
  if (Notification.permission === "granted") return;
  const perm = await Notification.requestPermission();
  if (perm !== "granted")
    toast("Habilitá las notificaciones en la configuración del navegador", 4000);
}

function _guardarCronograma(tema) {
  const dias     = parseInt(document.getElementById("plan-sched-dias")?.value) || 7;
  const horaIni  = document.getElementById("plan-sched-hora-ini")?.value || "08:00";
  const horaFin  = document.getElementById("plan-sched-hora-fin")?.value || "09:00";
  const diasSem  = [...document.querySelectorAll("[name='plan-sched-dia']:checked")]
                     .map(el => parseInt(el.value));

  if (!diasSem.length) { toast("Seleccioná al menos un día de la semana"); return; }

  const cronos = JSON.parse(localStorage.getItem("atalaya-cronogramas") || "[]");
  const nuevo  = { id: Date.now(), tema, dias, horaIni, horaFin, diasSem, creado: new Date().toISOString() };
  cronos.push(nuevo);
  localStorage.setItem("atalaya-cronogramas", JSON.stringify(cronos));
  _programarNotifHoy(nuevo);
  toast(`Cronograma guardado. Notificación a las ${horaIni}`, 3000);
}

function _programarNotifHoy(c) {
  if (!("Notification" in window) || Notification.permission !== "granted") return;
  const ahora = new Date();
  if (!c.diasSem.includes(ahora.getDay())) return;
  const [h, m]  = c.horaIni.split(":").map(Number);
  const hora    = new Date(); hora.setHours(h, m, 0, 0);
  const delay   = hora - ahora;
  if (delay <= 0) return;
  setTimeout(() => {
    new Notification("📚 Atalaya Pléyades", {
      body: `Es hora de estudiar: ${c.tema}`,
      tag:  `atalaya-${c.id}`,
    });
  }, delay);
}

function _iniciarNotificaciones() {
  if (!("Notification" in window) || Notification.permission !== "granted") return;
  const cronos = JSON.parse(localStorage.getItem("atalaya-cronogramas") || "[]");
  cronos.forEach(_programarNotifHoy);
}
