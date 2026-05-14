// Módulo de plan de estudio — dos agentes: Evaluador + Planificador

let _planGenerando = false;

async function generarPlan() {
  if (_planGenerando) return;
  _planGenerando = true;

  const contenedor = document.getElementById("plan-contenido");
  const btn        = document.getElementById("btn-generar-plan");
  btn.disabled     = true;
  btn.textContent  = "Generando…";

  contenedor.innerHTML = `
    <div id="plan-fase-indicator" style="color:var(--text-muted); font-size:.85rem; margin-bottom:.75rem;"></div>
    <div id="plan-eval-bloque" style="display:none;">
      <h3 style="font-size:.85rem; font-weight:700; text-transform:uppercase;
                 letter-spacing:.06em; color:var(--accent); margin-bottom:.5rem;">
        Diagnóstico de dominio
      </h3>
      <div id="plan-eval-contenido" class="card" style="font-size:.875rem; line-height:1.7; margin-bottom:1rem;"></div>
    </div>
    <div id="plan-plan-bloque" style="display:none;">
      <h3 style="font-size:.85rem; font-weight:700; text-transform:uppercase;
                 letter-spacing:.06em; color:var(--brand); margin-bottom:.5rem;">
        Plan semanal
      </h3>
      <div id="plan-plan-contenido"></div>
    </div>`;

  const faseEl    = document.getElementById("plan-fase-indicator");
  const evalBloq  = document.getElementById("plan-eval-bloque");
  const evalCont  = document.getElementById("plan-eval-contenido");
  const planBloq  = document.getElementById("plan-plan-bloque");
  const planCont  = document.getElementById("plan-plan-contenido");

  let planAcumulado = "";

  try {
    const resp = await fetch("/plan/generar", { method: "POST" });
    if (!resp.ok) throw new Error(`Error ${resp.status}`);

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
          const dato = JSON.parse(payload);

          if (typeof dato === "string") {
            // Chunk del plan
            planAcumulado += dato;
            planCont.innerHTML = marked.parse(planAcumulado);
          } else if (dato.type === "fase") {
            faseEl.textContent = dato.msg;
          } else if (dato.type === "eval") {
            evalBloq.style.display = "block";
            evalCont.innerHTML = marked.parse(dato.contenido);
            planBloq.style.display = "block";
          }
        } catch (_) { /* chunk parcial */ }
      }
    }

    faseEl.textContent = "✅ Plan generado";
    document.getElementById("plan-fecha").textContent =
      "Generado el " + new Date().toLocaleDateString("es-CO", {
        weekday: "long", year: "numeric", month: "long", day: "numeric",
      });

  } catch (e) {
    contenedor.innerHTML = `<p style="color:var(--danger)">Error al generar el plan: ${e.message}</p>`;
  } finally {
    _planGenerando  = false;
    btn.disabled    = false;
    btn.textContent = "Regenerar plan";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("btn-generar-plan");
  if (btn) btn.addEventListener("click", generarPlan);
});
