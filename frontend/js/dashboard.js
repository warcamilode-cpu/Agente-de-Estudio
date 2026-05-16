// Módulo dashboard

async function cargarDashboard() {
  const [resumen, racha] = await Promise.all([
    api("GET", "/dashboard/resumen"),
    api("GET", "/dashboard/racha"),
  ]);

  const grid = document.getElementById("dash-stats");
  grid.innerHTML = "";

  const stats = [
    { valor: racha.racha_dias,              etiqueta: "días de racha 🔥" },
    { valor: resumen.cards_pendientes_hoy,  etiqueta: "cards pendientes hoy" },
    { valor: resumen.cards_revisadas_hoy,   etiqueta: "cards revisadas hoy" },
    { valor: resumen.cards_correctas_hoy,   etiqueta: "cards correctas hoy" },
    { valor: resumen.total_flashcards,      etiqueta: "flashcards totales" },
    { valor: _formatearTiempo(resumen.tiempo_estudiado_seg), etiqueta: "tiempo hoy" },
  ];

  stats.forEach(({ valor, etiqueta }) => {
    const div = document.createElement("div");
    div.className = "stat-card";
    div.innerHTML = `<div class="valor">${valor}</div><div class="etiqueta">${etiqueta}</div>`;
    grid.appendChild(div);
  });

  // Progreso por materia
  const materiasEl = document.getElementById("dash-topics");
  materiasEl.innerHTML = "";

  if (!_materias.length) {
    materiasEl.innerHTML = '<p style="color:var(--text-muted);">Sin materias registradas. Creá tu primera materia en el Cuaderno.</p>';
    return;
  }

  await Promise.all(_materias.map(async m => {
    try {
      const prog = await api("GET", `/dashboard/progreso/${m.id}`);
      const div = document.createElement("div");
      div.className = "card";
      div.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:.5rem;">
          <strong>${prog.materia_emoji} ${prog.materia_nombre}</strong>
          <span style="font-size:.85rem; color:var(--text-muted);">${prog.porcentaje_dominio}% dominado</span>
        </div>
        <div style="background:var(--surface2); border-radius:4px; height:8px; overflow:hidden;">
          <div style="background:var(--accent); width:${prog.porcentaje_dominio}%; height:100%; border-radius:4px;"></div>
        </div>
        <div style="font-size:.78rem; color:var(--text-muted); margin-top:.4rem;">
          ${prog.clases} clases · ${prog.documentos} docs · ${prog.flashcards_total} cards · ${prog.flashcards_dominadas} dominadas
        </div>`;
      materiasEl.appendChild(div);
    } catch { /* materia sin progreso */ }
  }));
}

async function registrarSesion(tipo, duracion_seg, cards_revisadas = 0, cards_correctas = 0, materia_id = null) {
  try {
    await api("POST", "/dashboard/sesion", { tipo, duracion_seg, cards_revisadas, cards_correctas, materia_id });
  } catch { /* no interrumpir el flujo si falla el registro */ }
}

function _formatearTiempo(seg) {
  if (seg < 60) return `${seg}s`;
  const min = Math.floor(seg / 60);
  if (min < 60) return `${min}min`;
  return `${Math.floor(min / 60)}h ${min % 60}min`;
}
