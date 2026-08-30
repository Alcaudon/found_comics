const STATUS_CLASSES = {
  disponible: 'badge-available',
  posible: 'badge-maybe',
  no_encontrado: 'badge-missing',
  error: 'badge-error',
};
const STATUS_ICONS = {
  disponible: '✅', posible: '⚠️', no_encontrado: '🔍', error: '❌',
};
const STATUS_LABELS = {
  disponible: 'Disponible', posible: 'Posible',
  no_encontrado: 'No encontrado', error: 'Error',
};
const FIELDS = ['title', 'volume', 'publisher', 'last_number', 'notes'];

let allSeries = [];
let importFileCached = null;

async function api(path, options = {}) {
  const res = await fetch(path, options);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

function setStatus(html) {
  document.getElementById('statusBar').innerHTML = html;
}

function showLoading(show) {
  document.getElementById('loading').classList.toggle('d-none', !show);
  document.getElementById('seriesGrid').classList.toggle('d-none', show);
}

async function loadSeries() {
  setStatus('');
  showLoading(true);
  document.getElementById('emptyState').classList.add('d-none');
  try {
    allSeries = await api('/api/series');
    renderCards(allSeries);
    updateStats(allSeries);
  } catch (e) {
    setStatus(`<div class="alert alert-danger">${e.message}</div>`);
  } finally {
    showLoading(false);
  }
}

function updateStats(seriesList) {
  document.getElementById('statTotal').textContent = seriesList.length;
  const counts = { disponible: 0, posible: 0, pending: 0 };
  seriesList.forEach(s => {
    const st = s.last_check?.status;
    if (st === 'disponible') counts.disponible++;
    else if (st === 'posible') counts.posible++;
    else counts.pending++;
  });
  document.getElementById('statOk').textContent = counts.disponible;
  document.getElementById('statMaybe').textContent = counts.posible;
  document.getElementById('statPending').textContent = counts.pending;
}

function filterSeries() {
  const q = document.getElementById('searchInput').value.toLowerCase();
  const filtered = allSeries.filter(s =>
    (s.title || '').toLowerCase().includes(q) ||
    (s.publisher || '').toLowerCase().includes(q) ||
    (s.notes || '').toLowerCase().includes(q)
  );
  renderCards(filtered);
}

function renderCards(seriesList) {
  const grid = document.getElementById('seriesGrid');
  const empty = document.getElementById('emptyState');

  if (seriesList.length === 0) {
    grid.innerHTML = '';
    empty.classList.remove('d-none');
    return;
  }
  empty.classList.add('d-none');

  grid.innerHTML = seriesList.map(s => {
    const c = s.last_check;
    const status = c?.status || 'pending';
    const badgeClass = STATUS_CLASSES[status] || 'badge-pending';
    const icon = STATUS_ICONS[status] || '⏳';
    const label = STATUS_LABELS[status] || 'Sin comprobar';

    const checkedDate = c
      ? `<small class="text-muted">${new Date(c.checked_at).toLocaleString('es-ES', {dateStyle:'short', timeStyle:'short'})}</small>`
      : '';

    const resultLink = c?.url
      ? `<a href="${esc(c.url)}" target="_blank" class="btn btn-sm btn-outline-primary stretched-link-none"
             title="${esc(c.result_title || '')}">ver en Amazon</a>` : '';

    const price = c?.price ? `<span class="text-muted small">${c.price.toFixed(2)} €</span>` : '';

    return `
    <div class="col-md-6 col-xl-4">
      <div class="card card-comic h-100">
        <div class="card-header d-flex justify-content-between align-items-start">
          <div>
            <h5 class="card-title mb-1">${esc(s.title)}</h5>
            <div class="meta-line">
              <span>${esc(s.publisher || 'Sin editorial')}</span>
              ${s.volume ? `<span class="badge bg-light text-dark border">Vol. ${s.volume}</span>` : ''}
            </div>
          </div>
        </div>
        <div class="card-body">
          <div class="d-flex gap-2 mb-3">
            <span class="issue-pill owned" title="Último que tengo">Tengo #${s.last_number}</span>
            <span class="issue-pill next" title="Siguiente a buscar">Busco #${s.next_number}</span>
          </div>

          ${s.notes ? `<p class="text-muted small mb-2">${esc(s.notes)}</p>` : ''}

          <div class="status-line mb-2">
            <span class="badge ${badgeClass}">${icon} ${label}</span>
            ${resultLink} ${price}
          </div>
          ${checkedDate ? `<div>${checkedDate}</div>` : ''}
          ${c?.message && status === 'error' ? `<div class="text-danger small">${esc(c.message)}</div>` : ''}
          ${status === 'posible' && c ? `
          <div class="d-flex gap-2 mt-2">
            <button class="btn btn-sm btn-success" onclick="setCheckStatus(${c.id}, 'disponible')"
                    title="Confirmar que es el número que buscas">✓ Es este</button>
            <button class="btn btn-sm btn-outline-secondary" onclick="setCheckStatus(${c.id}, 'no_encontrado')"
                    title="Descartar: no es el número que buscas">✗ No es</button>
          </div>` : ''}
        </div>
        <div class="card-footer bg-white border-0 pt-0 pb-3 px-4">
          <div class="action-btns">
            <button class="btn btn-sm btn-success" onclick="checkOne(${s.id})">Comprobar</button>
            <button class="btn btn-sm btn-outline-primary" onclick='openEdit(${JSON.stringify(s)})'>Editar</button>
            <button class="btn btn-sm btn-outline-danger" onclick="deleteSeries(${s.id}, '${esc(s.title)}')">Borrar</button>
          </div>
        </div>
      </div>
    </div>`;
  }).join('');
}

function esc(text) {
  const div = document.createElement('div');
  div.textContent = String(text ?? '');
  return div.innerHTML;
}

function numOrNull(id) {
  const v = document.getElementById(id).value;
  return v === '' ? null : parseInt(v, 10);
}

// --- CRUD ---
function openCreate() {
  document.getElementById('seriesModalTitle').textContent = 'Nueva serie';
  document.getElementById('seriesForm').reset();
  document.getElementById('seriesId').value = '';
}

function openEdit(s) {
  document.getElementById('seriesModalTitle').textContent = 'Editar serie';
  document.getElementById('seriesId').value = s.id;
  document.getElementById('fTitle').value = s.title;
  document.getElementById('fVolume').value = s.volume ?? '';
  document.getElementById('fLastNumber').value = s.last_number;
  document.getElementById('fPublisher').value = s.publisher || '';
  document.getElementById('fNotes').value = s.notes || '';
  new bootstrap.Modal('#seriesModal').show();
}

async function saveSeries() {
  const id = document.getElementById('seriesId').value;
  const payload = {
    title: document.getElementById('fTitle').value.trim(),
    volume: numOrNull('fVolume'),
    last_number: parseInt(document.getElementById('fLastNumber').value) || 1,
    publisher: document.getElementById('fPublisher').value.trim() || null,
    notes: document.getElementById('fNotes').value.trim() || null,
  };
  if (!payload.title) return alert('El título es obligatorio');
  try {
    if (id) {
      await api(`/api/series/${id}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    } else {
      await api('/api/series', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    }
    bootstrap.Modal.getInstance('#seriesModal').hide();
    loadSeries();
  } catch (e) {
    alert(e.message);
  }
}

async function deleteSeries(id, title) {
  if (!confirm(`¿Eliminar "${title}" y su historial?`)) return;
  try {
    await api(`/api/series/${id}`, { method: 'DELETE' });
    loadSeries();
  } catch (e) {
    alert(e.message);
  }
}

// --- Comprobaciones ---
async function checkOne(id) {
  setStatus('<div class="alert alert-info">Consultando Amazon…</div>');
  try {
    await api(`/api/checks/${id}`, { method: 'POST' });
    loadSeries();
  } catch (e) {
    setStatus(`<div class="alert alert-danger">${e.message}</div>`);
  }
}

async function setCheckStatus(checkId, status) {
  try {
    await api(`/api/checks/${checkId}`, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    });
    loadSeries();
  } catch (e) {
    setStatus(`<div class="alert alert-danger">${e.message}</div>`);
  }
}

async function checkAll() {
  const btn = document.getElementById('checkAllBtn');
  const spinner = document.getElementById('checkAllSpinner');
  btn.disabled = true;
  spinner.classList.remove('d-none');
  try {
    const res = await api('/api/checks/all', { method: 'POST' });
    setStatus(`<div class="alert alert-info">${res.errors[0]}. Recarga en unos segundos para ver los resultados.</div>`);
    setTimeout(loadSeries, 10000);
  } catch (e) {
    setStatus(`<div class="alert alert-danger">${e.message}</div>`);
  } finally {
    btn.disabled = false;
    spinner.classList.add('d-none');
  }
}

// --- Importación ---
document.getElementById('importFile').addEventListener('change', async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  importFileCached = file;
  const fd = new FormData();
  fd.append('file', file);
  try {
    const preview = await api('/api/import/preview', { method: 'POST', body: fd });
    renderImportPreview(preview);
    document.getElementById('importConfirmBtn').disabled = false;
  } catch (err) {
    document.getElementById('importPreview').innerHTML =
      `<div class="alert alert-danger">${err.message}</div>`;
    document.getElementById('importConfirmBtn').disabled = true;
  }
});

const FIELD_LABELS = {
  title: 'Título', volume: 'Volumen', publisher: 'Editorial',
  last_number: 'Último número', notes: 'Notas', '': '(ignorar)',
};

function renderImportPreview(preview) {
  const selects = preview.columns.map(col => {
    const selected = preview.suggested_mapping[col] || '';
    const options = [''].concat(FIELDS).map(f =>
      `<option value="${f}" ${f === selected ? 'selected' : ''}>${FIELD_LABELS[f]}</option>`
    ).join('');
    return `<div class="row align-items-center mb-2">
      <div class="col-5"><code>${esc(col)}</code></div>
      <div class="col-7"><select class="form-select form-select-sm" data-col="${esc(col)}">${options}</select></div>
    </div>`;
  }).join('');

  const rows = preview.rows.map(r =>
    `<tr>${preview.columns.map(c => `<td>${esc(String(r[c] ?? ''))}</td>`).join('')}</tr>`
  ).join('');

  document.getElementById('importPreview').innerHTML = `
    <div class="mb-3"><h6 class="fw-bold">Mapeo de columnas</h6>${selects}</div>
    <h6 class="fw-bold">Vista previa</h6>
    <div class="table-responsive" style="max-height: 220px; overflow-y: auto; border-radius:0.5rem; border:1px solid #e2e8f0;">
      <table class="table table-sm table-hover mb-0">
        <thead class="table-light"><tr>${preview.columns.map(c => `<th>${esc(c)}</th>`).join('')}</tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

async function confirmImport() {
  if (!importFileCached) return;
  const mapping = {};
  document.querySelectorAll('#importPreview select').forEach(sel => {
    if (sel.value) mapping[sel.dataset.col] = sel.value;
  });
  if (!Object.values(mapping).includes('title')) {
    return alert('Debes mapear al menos la columna de "Título"');
  }
  const fd = new FormData();
  fd.append('file', importFileCached);
  fd.append('mapping', JSON.stringify(mapping));
  try {
    const res = await api('/api/import/confirm-file', { method: 'POST', body: fd });
    let html = `<div class="alert alert-success">${res.created} series importadas.</div>`;
    if (res.skipped.length) {
      html += `<div class="alert alert-warning"><strong>${res.skipped.length} filas omitidas:</strong><ul>${res.skipped.map(s => `<li>${esc(s)}</li>`).join('')}</ul></div>`;
    }
    document.getElementById('importPreview').innerHTML = html;
    document.getElementById('importConfirmBtn').disabled = true;
    importFileCached = null;
    document.getElementById('importFile').value = '';
    loadSeries();
  } catch (e) {
    document.getElementById('importPreview').innerHTML =
      `<div class="alert alert-danger">${e.message}</div>`;
  }
}

loadSeries();