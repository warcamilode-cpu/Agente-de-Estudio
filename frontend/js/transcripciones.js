// Módulo de transcripciones — Audio→Texto (Whisper) y Texto→Audio (Kokoro TTS)

let _transActual  = null;
let _cargaActiva  = false;
let _cargaTimer   = null;
let _cargaInicio  = null;
let _ttsAudioUrl  = null;   // Blob URL del último WAV generado

// ── Inicialización ──────────────────────────────────────────────
document.addEventListener('tabchange', e => {
  if (e.detail === 'transcripciones') {
    cargarTranscripciones();
    _poblarMateriasModales();
  }
});

document.addEventListener('DOMContentLoaded', () => {
  const txtArea = document.getElementById('tts-texto');
  if (txtArea) {
    txtArea.addEventListener('input', () => {
      const n = txtArea.value.length;
      document.getElementById('tts-char-count').textContent = n.toLocaleString('es-CO');
      if (n > 4000) txtArea.value = txtArea.value.slice(0, 4000);
    });
  }
});

// ── Sub-tabs ─────────────────────────────────────────────────────
function _transTab(tab) {
  const asr    = document.getElementById('trans-panel-asr');
  const tts    = document.getElementById('trans-panel-tts');
  const btnAsr = document.getElementById('btn-trans-tab-asr');
  const btnTts = document.getElementById('btn-trans-tab-tts');
  if (tab === 'asr') {
    asr.style.display = ''; tts.style.display = 'none';
    btnAsr.className = 'btn btn-primary btn-sm';
    btnTts.className = 'btn btn-secondary btn-sm';
  } else {
    asr.style.display = 'none'; tts.style.display = '';
    btnAsr.className = 'btn btn-secondary btn-sm';
    btnTts.className = 'btn btn-primary btn-sm';
  }
}

// ── Poblar selects de materia ────────────────────────────────────
async function _poblarMateriasModales() {
  try {
    const materias = await fetch('/cuaderno/materias').then(r => r.json());
    const selects  = ['trans-filtro-materia', 'ta-materia'];
    selects.forEach(sid => {
      const sel = document.getElementById(sid);
      if (!sel) return;
      const val    = sel.value;
      const prefix = sid === 'trans-filtro-materia'
        ? '<option value="">Todas las materias</option>'
        : '<option value="">— Sin materia —</option>';
      sel.innerHTML = prefix + materias.map(m => `<option value="${m.id}">${_tEsc(m.nombre)}</option>`).join('');
      sel.value = val;
    });
  } catch(_) {}
}

document.getElementById('trans-filtro-materia').addEventListener('change', cargarTranscripciones);

// ── Listar transcripciones ───────────────────────────────────────
async function cargarTranscripciones() {
  if (_cargaActiva) return;
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

  const fd = new FormData();
  fd.append('archivo', archivo);
  fd.append('titulo',  titulo);
  fd.append('idioma',  idioma);
  if (materia) fd.append('materia_id', parseInt(materia));

  cerrarModalSubirAudio();
  _iniciarCarga(titulo);

  try {
    const r = await fetch('/transcripciones', { method: 'POST', body: fd });
    if (!r.ok) {
      const err = await r.json().catch(() => ({ detail: 'Error desconocido' }));
      throw new Error(err.detail || 'Error al transcribir');
    }
    const resultado = await r.json();
    _detenerCarga();
    toast('Transcripción completada ✓');
    cargarTranscripciones();
    verTranscripcion(resultado.id);
  } catch(e) {
    _detenerCarga();
    toast('Error: ' + e.message, 5000);
    cargarTranscripciones();
  }
}

function _iniciarCarga(titulo) {
  _cargaActiva = true;
  _cargaInicio = Date.now();

  if (!document.getElementById('_trans-anim-style')) {
    const s = document.createElement('style');
    s.id = '_trans-anim-style';
    s.textContent = '@keyframes _tshimmer{0%{left:-35%}100%{left:110%}}';
    document.head.appendChild(s);
  }

  const fmt   = s => `${String(Math.floor(s/60)).padStart(2,'0')}:${String(s%60).padStart(2,'0')}`;
  const lista = document.getElementById('trans-lista');
  lista.innerHTML = `
    <div id="trans-card-carga" class="card" style="padding:.75rem .85rem;">
      <div style="display:flex;align-items:center;gap:.75rem;margin-bottom:.6rem;">
        <div style="font-size:1.4rem;flex-shrink:0;">🎙</div>
        <div style="flex:1;min-width:0;">
          <div style="font-weight:600;font-size:.875rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${_tEsc(titulo)}</div>
          <div style="font-size:.75rem;color:var(--text-muted);">Transcribiendo… <span id="_trans-elapsed">00:00</span></div>
        </div>
      </div>
      <div style="height:4px;background:var(--border,#e2e8f0);border-radius:2px;overflow:hidden;position:relative;">
        <div style="position:absolute;top:0;height:100%;width:35%;background:var(--accent,#6366f1);border-radius:2px;animation:_tshimmer 1.5s linear infinite;"></div>
      </div>
    </div>`;

  _cargaTimer = setInterval(() => {
    const el = document.getElementById('_trans-elapsed');
    if (el) el.textContent = fmt(Math.floor((Date.now() - _cargaInicio) / 1000));
  }, 1000);
}

function _detenerCarga() {
  _cargaActiva = false;
  if (_cargaTimer) { clearInterval(_cargaTimer); _cargaTimer = null; }
  _cargaInicio = null;
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
  window._maiaTransId     = _transActual.id;
  window._maiaTransTitulo = _transActual.titulo;
  const _titulo = _transActual.titulo;
  cerrarVisorTrans();
  cambiarTab('documentos');
  setTimeout(() => {
    _docsTab('maia');
    if (typeof _actualizarIndicadorTrans === 'function') _actualizarIndicadorTrans();
    const input = document.getElementById('maia-input');
    if (input) {
      input.value = `Analizá esta transcripción de clase "${_titulo}"`;
      input.focus();
    }
  }, 150);
}

function _transLeerEnVozAlta() {
  if (!_transActual || !_transActual.texto) return;
  cerrarVisorTrans();
  cambiarTab('transcripciones');
  setTimeout(() => {
    _transTab('tts');
    const txtArea = document.getElementById('tts-texto');
    if (txtArea) {
      txtArea.value = _transActual.texto.slice(0, 4000);
      document.getElementById('tts-char-count').textContent = txtArea.value.length.toLocaleString('es-CO');
      const idiomaMap = { es: 'es', en: 'en-us', pt: 'pt-br', fr: 'fr-fr', it: 'it' };
      const selIdioma = document.getElementById('tts-idioma');
      if (selIdioma && _transActual.idioma) {
        selIdioma.value = idiomaMap[_transActual.idioma] || 'es';
      }
      txtArea.focus();
    }
  }, 150);
}

// ── TTS ─────────────────────────────────────────────────────────
async function generarAudio() {
  const texto     = document.getElementById('tts-texto').value.trim();
  const voz       = document.getElementById('tts-voz').value;
  const velocidad = parseFloat(document.getElementById('tts-velocidad').value);
  const idioma    = document.getElementById('tts-idioma').value;

  if (!texto) { toast('Escribí o pegá un texto antes de generar.'); return; }

  const btn  = document.getElementById('btn-tts-generar');
  const wrap = document.getElementById('tts-player-wrap');

  btn.disabled       = true;
  btn.innerHTML      = '<i class="fi fi-rr-spinner"></i> Generando…';
  wrap.style.display = 'none';

  if (_ttsAudioUrl) { URL.revokeObjectURL(_ttsAudioUrl); _ttsAudioUrl = null; }

  try {
    const r = await fetch('/transcripciones/tts/sintetizar', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ texto, voz, velocidad, idioma }),
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({ detail: 'Error desconocido' }));
      throw new Error(err.detail || 'Error al sintetizar');
    }
    const blob  = await r.blob();
    _ttsAudioUrl = URL.createObjectURL(blob);

    const audio = document.getElementById('tts-audio');
    audio.src   = _ttsAudioUrl;
    wrap.style.display = 'flex';
    audio.play().catch(() => {});
    toast('Audio generado ✓');
  } catch(e) {
    toast('Error: ' + e.message, 5000);
  } finally {
    btn.disabled  = false;
    btn.innerHTML = '<i class="fi fi-rr-volume"></i> Generar audio';
  }
}

function descargarAudioTTS() {
  if (!_ttsAudioUrl) return;
  const a    = document.createElement('a');
  a.href     = _ttsAudioUrl;
  a.download = `tts_${Date.now()}.wav`;
  a.click();
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
