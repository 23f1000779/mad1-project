// app/static/js/main.js
// Central JS helpers for the Hospital app

// Read CSRF token from meta tag or hidden input
function getCSRFToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  if (meta) return meta.content;
  const hidden = document.querySelector('input[name="csrf_token"]');
  return hidden ? hidden.value : null;
}

/* ---------- Simple toaster ---------- */
function showToast(message, type='info', timeout=3500) {
  const containerId = 'toastContainer';
  let container = document.getElementById(containerId);
  if (!container) {
    container = document.createElement('div');
    container.id = containerId;
    container.style.position = 'fixed';
    container.style.right = '20px';
    container.style.top = '20px';
    container.style.zIndex = 1080;
    document.body.appendChild(container);
  }
  const toast = document.createElement('div');
  toast.className = `toast align-items-center text-bg-${type} border-0 show`;
  toast.style.minWidth = '200px';
  toast.style.marginTop = '8px';
  toast.innerHTML = `<div class="d-flex"><div class="toast-body">${message}</div>
    <button type="button" class="btn-close btn-close-white me-2 m-auto" onclick="this.closest('.toast').remove()"></button></div>`;
  container.appendChild(toast);
  setTimeout(()=> toast.remove(), timeout);
}

/* ---------- Delete modal helpers (Bootstrap) ---------- */
let deleteFormToSubmit = null;
function showDeleteModal(type, name, form) {
  deleteFormToSubmit = form;
  const msg = document.getElementById('deleteMessage');
  if (msg) msg.innerText = `Are you sure you want to delete the ${type} "${name}"? This will deactivate their account.`;
  const modalEl = document.getElementById('confirmDeleteModal');
  if (!modalEl) {
    if (confirm(`Delete ${type} ${name}?`)) form.submit();
    return;
  }
  const modal = new bootstrap.Modal(modalEl);
  modal.show();
}
document.addEventListener('DOMContentLoaded', function () {
  const btn = document.getElementById('confirmDeleteBtn');
  if (btn) btn.addEventListener('click', function () {
    if (deleteFormToSubmit) deleteFormToSubmit.submit();
  });
});

/* ---------- AJAX utilities ---------- */
async function ajaxPostJson(url, jsonObj, method='POST') {
  const csrf = getCSRFToken();
  const headers = {'Content-Type': 'application/json'};
  if (csrf) headers['X-CSRF-Token'] = csrf;
  const resp = await fetch(url, {
    method: method,
    headers: headers,
    body: JSON.stringify(jsonObj),
    credentials: 'same-origin'
  });
  const text = await resp.text();
  try { return {ok: resp.ok, status: resp.status, data: JSON.parse(text)}; }
  catch(e){ return {ok: resp.ok, status: resp.status, data: text}; }
}

async function ajaxPostForm(url, formDataObj, method='POST') {
  const csrf = getCSRFToken();
  const headers = {};
  if (csrf) headers['X-CSRF-Token'] = csrf;
  const resp = await fetch(url, {
    method: method,
    headers: headers,
    body: formDataObj,
    credentials: 'same-origin'
  });
  return { ok: resp.ok, status: resp.status, text: await resp.text() };
}

/* ajax delete by POST and remove row element */
async function ajaxDeleteRow(url, rowEl, successMsg='Deleted') {
  const csrf = getCSRFToken();
  if (!csrf) { showToast('No CSRF token', 'danger'); return; }
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: {'X-CSRF-Token': csrf},
      credentials: 'same-origin'
    });
    if (res.ok) {
      if (rowEl && rowEl.parentNode) rowEl.remove();
      showToast(successMsg, 'success');
    } else {
      const t = await res.text();
      showToast('Delete failed: ' + (t || res.status), 'danger');
    }
  } catch(e) {
    showToast('Network error during delete', 'danger');
  }
}

/* ---------- Debounce ---------- */
function debounce(fn, wait=300){
  let t = null;
  return (...args)=>{
    clearTimeout(t);
    t = setTimeout(()=> fn.apply(this, args), wait);
  };
}

/* ---------- Live search binder ---------- */
function bindLiveSearch(inputEl, resultsEl, fetchUrl) {
  const doSearch = debounce(async () => {
    const q = inputEl.value.trim();
    if (!q) { resultsEl.innerHTML = ''; return; }
    try {
      const resp = await fetch(`${fetchUrl}?q=${encodeURIComponent(q)}`, {credentials:'same-origin'});
      if (resp.ok) {
        const html = await resp.text();
        resultsEl.innerHTML = html;
      } else {
        resultsEl.innerHTML = '<div class="text-muted">Search failed</div>';
      }
    } catch(e) {
      resultsEl.innerHTML = '<div class="text-muted">Network error</div>';
    }
  }, 350);
  inputEl.addEventListener('input', doSearch);
}

/* ---------- Check appointment availability (calls /api/check_slot) ---------- */
async function checkAvailability(doctorId, dateStr, timeStr) {
  if (!doctorId || !dateStr || !timeStr) return {ok:false, conflict:false};
  const url = `/api/check_slot?doctor_id=${doctorId}&date=${encodeURIComponent(dateStr)}&time=${encodeURIComponent(timeStr)}`;
  try {
    const resp = await fetch(url, {credentials:'same-origin'});
    if (!resp.ok) return {ok:false};
    const data = await resp.json();
    return {ok:true, conflict: data.conflict};
  } catch(e) {
    return {ok:false};
  }
}

/* ---------- Client-side form validation enhancer ---------- */
function enhanceFormValidation(formEl) {
  if (!formEl) return;
  formEl.addEventListener('submit', function (e) {
    if (!formEl.checkValidity()) {
      e.preventDefault();
      e.stopPropagation();
      formEl.classList.add('was-validated');
      showToast('Please fix errors in the form', 'warning');
    }
  }, false);
}

/* ---------- Exports to global for inline use ---------- */
window.hospitalApp = {
  getCSRFToken, showToast, showDeleteModal, ajaxDeleteRow, debounce,
  bindLiveSearch, checkAvailability, enhanceFormValidation
};
