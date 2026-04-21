// CRM Helpers compartidos entre todos los paneles del CRM completo
// Requiere que API_BASE y showNotif() estén definidos globalmente en crm.html

window.crmFetch = async function(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
  return await res.json();
};

window.crmCreate = async function(recurso, campos) {
  return await crmFetch(`/crm/${recurso}`, { method: 'POST', body: JSON.stringify(campos) });
};

window.crmUpdate = async function(recurso, id, campos) {
  return await crmFetch(`/crm/${recurso}/${id}`, { method: 'PATCH', body: JSON.stringify(campos) });
};

window.crmDelete = async function(recurso, id) {
  return await crmFetch(`/crm/${recurso}/${id}`, { method: 'DELETE' });
};

window.crmList = async function(recurso) {
  return await crmFetch(`/crm/${recurso}`);
};

// Notificación simple (fallback si showNotif no existe)
window.notif = function(title, body = '') {
  if (typeof showNotif === 'function') showNotif(title, body);
  else console.log(`[NOTIF] ${title} ${body}`);
};

// Helpers de modal compatibles con dev (hidden) y prod (show)
window.abrirModal = function(id) {
  const el = document.getElementById(id);
  if (!el) return;
  if (typeof openModal === 'function') { openModal(id); }
  else { el.classList.remove('hidden'); el.classList.add('show'); }
};

window.cerrarModal = function(id) {
  const el = document.getElementById(id);
  if (!el) return;
  if (typeof closeModal === 'function') { closeModal(id); }
  else { el.classList.add('hidden'); el.classList.remove('show'); }
};
