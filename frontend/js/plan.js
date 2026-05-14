// Módulo de plan de estudio — dos agentes: Evaluador + Planificador

let _planGenerando = false;

async function generarPlan() {
  if (_planGenerando) return;
  _planGenerando = true;

  const contenedor = document.getElementById("plan-contenido");
  const btn        = document.getElementById("btn-generar-plan");
  btn.disabled     = true;
  btn.textContent  = "Generando…";

  // El Evaluador corre en el servidor antes de abrir el stream.
  // Mostramos un spinner mientras esperamos la primera respuesta.
  contenedor.innerHTML = `
    <p style="color:var(--text-muted); font-size:.85rem;">
      ⚙️ Analizando tu dominio en cada materia… (puede tardar ~15 s)
    </p>`;

  let planAcumulado = "";
  let evalMostrado  = false;

  try {
    const resp = await fetch("/plan/generar", { method: "POST" });
    if (!resp.ok) throw new Error(`Error ${resp.status}`);

    // Preparar estructura de dos bloques (se insertan al recibir el primer evento)
    contenedor.innerHTML = `
      <div id="plan-eval-bloque">
        <h3 style="font-size:.82rem; font-weight:700; text-transform:uppercase;
                   letter-spacing:.06em; color:var(--accent); margin-bottom:.5rem;">
          Diagnóstico de dominio
        </h3>
        <div id="plan-eval-contenido" class="card"
             style="font-size:.875rem; line-height:1.7; margin-bottom:1.25rem;">
          <p style="color:var(--text-muted)">Cargando evaluación…</p>
        </div>
      </div>
      <div id="plan-plan-bloque" style="display:none;">
        <h3 style="font-size:.82rem; font-weight:700; text-transform:uppercase;
                   letter-spacing:.06em; color:var(--brand); margin-bottom:.5rem;">
          📅 Plan semanal
        </h3>
        <div id="plan-plan-contenido"></div>
      </div>`;

    const evalCont = document.getElementById("plan-eval-contenido");
    const planBloq = document.getElementById("plan-plan-bloque");
    const planCont = document.getElementById("plan-plan-contenido");

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
            // Chunk del plan (streaming)
            if (!evalMostrado) {
              // Primera vez: asegurar que el bloque plan es visible
              planBloq.style.display = "block";
              evalMostrado = true;
            }
            planAcumulado += dato;
            planCont.innerHTML = marked.parse(planAcumulado);
          } else if (dato.type === "eval") {
            evalCont.innerHTML = marked.parse(dato.contenido);
            planBloq.style.display = "block";
            evalMostrado = true;
          }
        } catch (_) { /* chunk SSE parcial */ }
      }
    }

    document.getElementById("plan-fecha").textContent =
      "Generado el " + new Date().toLocaleDateString("es-CO", {
        weekday: "long", year: "numeric", month: "long", day: "numeric",
      });

  } catch (e) {
    contenedor.innerHTML =
      `<p style="color:var(--danger)">Error al generar el plan: ${e.message}</p>`;
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
