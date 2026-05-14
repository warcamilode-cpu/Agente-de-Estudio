// Módulo de plan de estudio generado por Shaula

let _planGenerando = false;

async function generarPlan() {
  if (_planGenerando) return;
  _planGenerando = true;

  const contenedor = document.getElementById("plan-contenido");
  const btn        = document.getElementById("btn-generar-plan");
  btn.disabled     = true;
  btn.textContent  = "Generando plan…";
  contenedor.innerHTML = '<p style="color:var(--text-muted)">Shaula está analizando tu material de estudio…</p>';

  try {
    const resp = await fetch("/plan/generar", { method: "POST" });
    if (!resp.ok) throw new Error(`Error ${resp.status}`);

    const reader  = resp.body.getReader();
    const decoder = new TextDecoder();
    let acumulado = "";
    contenedor.innerHTML = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const lineas = decoder.decode(value).split("\n");
      for (const linea of lineas) {
        if (!linea.startsWith("data: ")) continue;
        const dato = linea.slice(6);
        if (dato === "[DONE]") break;
        try {
          acumulado += JSON.parse(dato);
          contenedor.innerHTML = marked.parse(acumulado);
        } catch (_) { /* chunk parcial */ }
      }
    }

    document.getElementById("plan-fecha").textContent =
      "Generado el " + new Date().toLocaleDateString("es-CO", { weekday: "long", year: "numeric", month: "long", day: "numeric" });

  } catch (e) {
    contenedor.innerHTML = `<p style="color:var(--danger)">Error al generar el plan: ${e.message}</p>`;
  } finally {
    _planGenerando = false;
    btn.disabled    = false;
    btn.textContent = "Regenerar plan";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("btn-generar-plan");
  if (btn) btn.addEventListener("click", generarPlan);
});
