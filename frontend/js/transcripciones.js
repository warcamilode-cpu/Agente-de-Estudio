// Módulo de transcripciones de audio/video (Whisper)

let _transActual = null;

// ── Inicialización ──────────────────────────────────────────────
document.addEventListener('tabchange', e => {
  if (e.detail === 'transcripciones') cargarTranscripciones();
});

document.getElementById('trans-filtro-materia').addEventListener('change', cargarTranscripciones);

// ── Listar ──────────────────────────────────────────────────────
async function cargarTranscripciones() {
  const lista  = document.getElementById('trans-lista');
  const filtro = document.getElementById('trans-filtro-materia').value;
  lista.innerHTML = '<p style="color:var(--text-muted); text-align:center; padding:2rem 0;">Cargando…</p>';
  try {
    const url  = filtro ? `/transcripciones?materia_id=${filtro}` : '/transcripciones';
    const data = await fetch(url).then(r => r.json());
    if (!data.length) {
      lista.innerHTML = `
        <div style="text-align:center; padding:3rem 1rem; color:var(--text-muted); line-height:1.8;">
          <div style="font-size:2.5rem; margin-bottom:.5rem;">🎙</div>
          <p>No hay transcripciones todavía.<br>Subí un audio o video de clase para comenzar.</p>
        </div>`;
      return;
    }
    lista.innerHTML = '';
    data.forEach(t => {
      const div = document.createElement('div');
      div.className = 'card';
      div.style.cssText = 'display:flex; align-items:center; gap:.75rem; cursor:pointer; padding:.65rem .85rem;';
      div.onclick = () => verTranscripcion(t.id);
      const mat = t.materia_nombre && t.materia_nombre !== '—' ? t.materia_nombre : '';
      div.innerHTML = `
        <div style="font-size:1.4rem; flex-shrink:0; line-height:1;">🎙</div>
        <div style="flex:1; min-width:0;">
          <div style="font-weight:600; font-size:.875rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${_tEsc(t.titulo)}</div>
          <div style="font-size:.75rem; color:var(--text-muted); display:flex; gap:.65rem; flex-wrap:wrap; margin-top:.15rem;">
            ${mat ? `<span>${_tEsc(mat)}</span>` : ''}
            <span>${t.idioma.toUpperCase()}</span>
            <span>${(t.chars || 0).toLocaleString('es-CO')} chars</span>
            <span>${_tFecha(t.creado_at)}</span>
          </div>
        </div>
        <button class="btn btn-danger btn-sm"
                onclick="event.stopPropagation(); eliminarTranscripcion(${t.id})"
                title="Eliminar" style="flex-shrink:0; padding:.25rem .55rem;">✕</button>
      `;
      lista.appendChild(div);
    });
  } catch(e) {
    lista.innerHTML = `<p style="color:var(--c-error,#ef4444); text-align:center;">Error al cargar: ${_tEsc(e.message)}</p>`;
  }
}

// ── Subir audio ─────────────────────────────────────────────────
function abrirModalSubirAudio() {
  document.getElementById('ta-titulo').value  = '';
  document.getElementById('ta-archivo').value = '';
  document.getElementById('ta-idioma').value  = 'es';
  document.getElementById('ta-materia').value = '';
  const btn = document.getElementById('btn-trans-subir');
  btn.disabled    = false;
  btn.textContent = 'Transcribir';
  document.getElementById('modal-subir-audio').classList.add('open');
}

function cerrarModalSubirAudio() {
  document.getElementById('modal-subir-audio').classList.remove('open');
}

async function subirAudio() {
  const archivo = document.getElementById('ta-archivo').files[0];
  const titulo  = document.getElementById('ta-titulo').value.trim();
  const idioma  = document.getElementById('ta-idioma').value;
  const materia = document.getElementById('ta-materia').value;

  if (!archivo) { toast('Seleccioná un archivo de audio o video.'); return; }
  if (!titulo)  { toast('Escribí un título para identificar la clase.'); return; }

  const btn = document.getElementById('btn-trans-subir');
  btn.disabled    = true;
  btn.textContent = 'Procesando… (puede tardar varios minutos)';

  const fd = new FormData();
  fd.append('archivo', archivo);
  fd.append('titulo',  titulo);
  fd.append('idioma',  idioma);
  if (materia) fd.append('materia_id', parseInt(materia));

  try {
    const r = await fetch('/transcripciones', { method: 'POST', body: fd });
    if (!r.ok) {
      const err = await r.json().catch(() => ({ detail: 'Error desconocido' }));
      throw new Error(err.detail || 'Error al transcribir');
    }
    const resultado = await r.json();
    cerrarModalSubirAudio();
    toast('Transcripción completada ✓');
    cargarTranscripciones();
    verTranscripcion(resultado.id);
  } catch(e) {
    toast('Error: ' + e.message, 5000);
  } finally {
    btn.disabled    = false;
    btn.textContent = 'Transcribir';
  }
}

// ── Ver transcripción ────────────────────────────────────────────
async function verTranscripcion(id) {
  try {
    const t = await fetch(`/transcripciones/${id}`).then(r => r.json());
    _transActual = t;

    document.getElementById('mtv-titulo').textContent = t.titulo;

    const matEl = document.getElementById('mtv-materia');
    if (t.materia_nombre && t.materia_nombre !== '—') {
      matEl.textContent   = t.materia_nombre;
      matEl.style.display = '';
    } else {
      matEl.style.display = 'none';
    }

    document.getElementById('mtv-idioma').textContent = t.idioma.toUpperCase();
    document.getElementById('mtv-fecha').textContent  = _tFecha(t.creado_at);

    const cuerpo = document.getElementById('mtv-cuerpo');
    cuerpo.innerHTML = `<pre style="white-space:pre-wrap; font-family:inherit; font-size:.875rem; line-height:1.75;">${_tEsc(t.texto || '')}</pre>`;
    cuerpo.scrollTop = 0;

    document.getElementById('modal-trans-visor').classList.add('open');
  } catch(e) {
    toast('No se pudo cargar la transcripción.');
  }
}

function cerrarVisorTrans() {
  document.getElementById('modal-trans-visor').classList.remove('open');
  _transActual = null;
}

function _transEnviarMaia() {
  if (!_transActual) return;
  const titulo = _transActual.titulo;
  const texto  = _transActual.texto || '';
  cerrarVisorTrans();
  cambiarTab('documentos');
  setTimeout(() => {
    _docsTab('maia');
    const input = document.getElementById('maia-input');
    if (input) {
      input.value = `Analizá esta transcripción de clase "${titulo}":\n\n${texto.substring(0, 3000)}${texto.length > 3000 ? '\n…[continúa]' : ''}`;
      input.focus();
    }
  }, 150);
}

// ── Eliminar ─────────────────────────────────────────────────────
async function eliminarTranscripcion(id) {
  if (!confirm('¿Eliminás esta transcripción? No se puede deshacer.')) return;
  try {
    const r = await fetch(`/transcripciones/${id}`, { method: 'DELETE' });
    if (!r.ok && r.status !== 204) throw new Error('Error al eliminar');
    toast('Transcripción eliminada.');
    cargarTranscripciones();
  } catch(e) {
    toast('Error al eliminar.');
  }
}

// ── Utilidades ────────────────────────────────────────────────────
function _tEsc(s) {
  return String(s || '').replace(/[&<>"']/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])
  );
}

function _tFecha(iso) {
  if (!iso) return '';
  const d = new Date(iso.includes('T') ? iso : iso + 'T00:00:00Z');
  return d.toLocaleDateString('es-CO', { day: '2-digit', month: 'short', year: 'numeric' });
}
