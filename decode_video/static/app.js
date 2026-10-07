const $ = s => document.querySelector(s);
const fmt = n => n > 1e9 ? (n/1e9).toFixed(2)+' GB' : n > 1e6 ? (n/1e6).toFixed(1)+' MB' : (n/1e3).toFixed(0)+' KB';
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const api = async (u, body) => { const r = await fetch(u, body ? {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)} : {}); return r.json(); };
let files = [];   // {path,name,size,analysis}
let openLogs = new Set();

(async () => {
  const i = await api('/api/info');
  $('#outdir').value = i.default_out;
  const p = $('#ffstatus'); p.textContent = i.ffmpeg ? 'ffmpeg listo' : 'ffmpeg NO encontrado'; p.className = 'pill ' + (i.ffmpeg ? 'ok' : 'bad');
})();

function renderFiles() {
  $('#files').innerHTML = files.map((f, i) => `<li><div class="nm"><b title="${esc(f.path)}">${esc(f.name)}</b>
    <span class="muted small">${fmt(f.size)}</span><div>${f.analysis ? f.analysis.issues.map(x => `<span class="chip ${x.level}" title="${esc(x.msg)}">${esc(x.code)}</span>`).join('') : '<span class="chip">analizando…</span>'}</div>
    ${f.analysis && f.analysis.issues[0].level === 'fatal' ? `<div class="small" style="color:var(--bad)">${esc(f.analysis.issues[0].msg)}</div>` : ''}</div>
    <button class="ghost" onclick="rm(${i})">✕</button></li>`).join('');
  $('#btnStart').disabled = !files.length;
  $('#startHint').textContent = files.length ? files.length + ' archivo(s) en cola' : '';
}
window.rm = i => { files.splice(i, 1); renderFiles(); };

async function addPaths(paths) {
  for (const p of paths) {
    if (files.some(f => f.path === p)) continue;
    const f = {path: p, name: p.split('/').pop(), size: 0, analysis: null}; files.push(f); renderFiles();
    api('/api/analyze', {path: p}).then(a => { if (!a.error) { f.analysis = a; f.size = a.size; } else f.analysis = {issues:[{level:'error',code:'error',msg:a.error}]}; renderFiles(); });
  }
}

// drag & drop / subida
const drop = $('#drop');
['dragenter','dragover'].forEach(e => drop.addEventListener(e, ev => { ev.preventDefault(); drop.classList.add('over'); }));
['dragleave','drop'].forEach(e => drop.addEventListener(e, ev => { ev.preventDefault(); drop.classList.remove('over'); }));
drop.addEventListener('drop', ev => upload(ev.dataTransfer.files));
$('#btnUpload').onclick = () => $('#fileInput').click();
$('#fileInput').onchange = e => upload(e.target.files);
async function upload(list) {
  if (!list.length) return;
  const fd = new FormData(); [...list].forEach(f => fd.append('files', f));
  $('#startHint').textContent = 'Subiendo…';
  const r = await (await fetch('/api/upload', {method:'POST', body: fd})).json();
  addPaths(r.paths);
}

// navegador de archivos
let fsCb = null, fsMode = 'files', fsSel = new Set(), fsCur = '';
async function openFs(mode, title, cb, start) {
  fsMode = mode; fsCb = cb; fsSel = new Set(); $('#mTitle').textContent = title; $('#modal').hidden = false; await loadDir(start || fsCur || '~');
}
async function loadDir(p) {
  const r = await api('/api/fs?path=' + encodeURIComponent(p));
  if (r.error) { alert(r.error); return; }
  fsCur = r.path; $('#mPath').value = r.path; fsSel.clear(); updSel();
  $('#places').innerHTML = r.places.map(x => `<a data-p="${esc(x.path)}">${esc(x.name)}</a>`).join('');
  $('#places').querySelectorAll('a').forEach(a => a.onclick = () => loadDir(a.dataset.p));
  $('#mUp').onclick = () => loadDir(r.parent);
  const ul = $('#mItems'); ul.innerHTML = '';
  r.items.forEach(it => {
    const li = document.createElement('li');
    if (it.dir) { li.innerHTML = `<span>📁 ${esc(it.name)}</span>`; li.ondblclick = () => loadDir(r.path + '/' + it.name); li.onclick = () => { if (fsMode === 'dir') { fsSel.clear(); ul.querySelectorAll('.sel').forEach(x => x.classList.remove('sel')); fsSel.add(r.path + '/' + it.name); li.classList.add('sel'); updSel(); } else loadDir(r.path + '/' + it.name); }; }
    else {
      li.innerHTML = `<span>🎞 ${esc(it.name)}</span><span class="muted small">${fmt(it.size)}</span>`; if (fsMode === 'dir') li.classList.add('dim');
      li.onclick = () => { const fp = r.path + '/' + it.name; if (fsMode === 'file') fsSel.clear(), ul.querySelectorAll('.sel').forEach(x => x.classList.remove('sel'));
        if (fsSel.has(fp)) { fsSel.delete(fp); li.classList.remove('sel'); } else { fsSel.add(fp); li.classList.add('sel'); } updSel(); };
    }
    ul.appendChild(li);
  });
}
const updSel = () => $('#mSel').textContent = fsMode === 'dir' ? (fsSel.size ? [...fsSel][0] : 'Se usará la carpeta actual') : fsSel.size + ' seleccionado(s) (clic para marcar, doble clic en carpeta para entrar)';
$('#mPath').onkeydown = e => { if (e.key === 'Enter') loadDir(e.target.value); };
$('#mClose').onclick = $('#mCancel').onclick = () => $('#modal').hidden = true;
$('#mOk').onclick = () => { const sel = fsMode === 'dir' ? [fsSel.size ? [...fsSel][0] : fsCur] : [...fsSel]; $('#modal').hidden = true; fsCb(sel); };
$('#btnBrowse').onclick = () => openFs('files', 'Selecciona videos (varios con clic)', addPaths);
$('#btnOut').onclick = () => openFs('dir', 'Carpeta de salida', s => $('#outdir').value = s[0], $('#outdir').value);
$('#btnRef').onclick = () => openFs('file', 'Video de referencia', s => $('#ref').value = s[0] || '');

// trabajos
$('#btnStart').onclick = async () => {
  const body = {paths: files.map(f => f.path), outdir: $('#outdir').value, fps: $('#fps').value, reference: $('#ref').value,
    force: $('#force').checked, force_reencode: $('#reenc').checked};
  await api('/api/jobs', body); files = []; renderFiles(); poll();
};
$('#btnClear').onclick = async () => { await api('/api/jobs/clear', {}); poll(); };
const LBL = {queued:'En cola', running:'Reparando', ok:'Reparado', partial:'Parcial', healthy:'Sano', failed:'Fallido', unrecoverable:'Sin datos', cancelled:'Cancelado'};
window.cancelJob = id => api(`/api/jobs/${id}/cancel`, {});
window.reveal = p => api('/api/reveal', {path: p});
window.play = (p, n) => { $('#pTitle').textContent = n; $('#pVideo').src = '/api/media?path=' + encodeURIComponent(p); $('#player').hidden = false; };
$('#pClose').onclick = () => { $('#pVideo').pause(); $('#pVideo').removeAttribute('src'); $('#player').hidden = true; };
window.toggleLog = id => { openLogs.has(id) ? openLogs.delete(id) : openLogs.add(id); poll(); };

async function poll() {
  const jobs = await api('/api/jobs');
  $('#jobs').innerHTML = jobs.length ? jobs.slice().reverse().map(j => {
    const r = j.result || {}, active = j.status === 'queued' || j.status === 'running';
    const bad = ['failed','unrecoverable'].includes(j.status);
    return `<div class="job"><div class="top"><div><b>${esc(j.name)}</b> <span class="muted small">${fmt(j.size)}</span></div>
      <span class="badge ${j.status}">${LBL[j.status] || j.status}</span></div>
      ${active ? `<div class="bar"><i style="width:${Math.round(j.pct*100)}%"></i></div>` : ''}
      ${r.message ? `<div class="msg ${bad ? 'bad' : ''}">${esc(r.message)}</div>` : ''}
      ${r.output ? `<div class="muted small">${esc(r.output)} · ${fmt(r.out_size)}</div>` : ''}
      <div class="row wrap" style="margin:8px 0 0">
        ${r.output ? `<button class="primary" onclick="play('${esc(r.output).replace(/'/g,"\\'")}','${esc(j.name)}')">▶ Reproducir</button><button onclick="reveal('${esc(r.output).replace(/'/g,"\\'")}')">Mostrar en carpeta</button>` : ''}
        ${active ? `<button onclick="cancelJob('${j.id}')">Cancelar</button>` : ''}
        <button class="ghost" onclick="toggleLog('${j.id}')">${openLogs.has(j.id) ? 'Ocultar' : 'Ver'} registro</button></div>
      ${openLogs.has(j.id) ? `<pre class="log">${esc(j.log.join('\n'))}</pre>` : ''}</div>`;
  }).join('') : '<p class="muted">Aún no hay trabajos.</p>';
  clearTimeout(window._t); if (jobs.some(j => j.status === 'queued' || j.status === 'running')) window._t = setTimeout(poll, 1000);
}
poll();
