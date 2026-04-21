// Panel Inquilinos — CRUD real conectado a /crm/inquilinos
(function () {
  let _items = [];
  let _inmueblesCache = [];

  window.cargarInquilinos = async function () {
    const cont = document.getElementById('inquilinosBody');
    if (!cont) return;
    cont.innerHTML = _skeletonRow(4);
    try {
      const [dataInq, dataInm] = await Promise.all([
        crmFetch('/crm/inquilinos'),
        crmFetch('/crm/inmuebles-renta').catch(() => ({ items: [] })),
      ]);
      _items = dataInq.items || [];
      _inmueblesCache = dataInm.items || [];
      _renderTablaInquilinos();
    } catch (e) {
      console.error('[INQUILINOS]', e);
      notif('Error cargando inquilinos', e.message);
      if (cont) cont.innerHTML = `<tr><td colspan="4" style="text-align:center;padding:20px;color:var(--txt-2)">Error: ${e.message}</td></tr>`;
    }
  };

  function _inmuebleName(id) {
    const i = _inmueblesCache.find(x => String(x.id) === String(id));
    return i ? (i.titulo || 'Inmueble #' + id) : '—';
  }

  const ESTADO_COLORS = {
    activo:    { bg: 'rgba(16,185,129,.14)', color: '#6ee7b7' },
    deuda:     { bg: 'rgba(245,158,11,.14)', color: '#fcd34d' },
    finalizado:{ bg: 'rgba(139,139,167,.14)', color: '#cbd5e1' },
  };

  function _renderTablaInquilinos() {
    const cont = document.getElementById('inquilinosBody');
    if (!cont) return;
    if (_items.length === 0) {
      cont.innerHTML = `<tr><td colspan="4" style="text-align:center;padding:30px;color:var(--txt-2)">Sin inquilinos registrados.</td></tr>`;
      return;
    }
    cont.innerHTML = _items.map(i => {
      const nombre = [i.nombre || '', i.apellido || ''].join(' ').trim() || '—';
      const inmueble = _inmuebleName(i.inmueble_renta_id);
      const est = i.estado || 'activo';
      const sc = ESTADO_COLORS[est] || ESTADO_COLORS.activo;
      const estadoBadge = `<span style="background:${sc.bg};color:${sc.color};padding:2px 8px;border-radius:5px;font-size:10.5px;font-weight:600">${est}</span>`;
      return `<tr>
        <td style="font-weight:600">${nombre}</td>
        <td style="color:var(--txt-2)">${inmueble}</td>
        <td>${estadoBadge}</td>
        <td>
          <div style="display:flex;gap:5px">
            <button class="cd-icon-btn" title="Editar" data-id="${i.id}" onclick="abrirModalInquilino(this.dataset.id)">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
            </button>
            <button class="cd-icon-btn danger" title="Eliminar" data-id="${i.id}" data-nombre="${nombre.replace(/"/g, '&quot;')}" onclick="_eliminarInquilino(this.dataset.id, this.dataset.nombre)">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"></path></svg>
            </button>
          </div>
        </td>
      </tr>`;
    }).join('');
  }

  window.abrirModalInquilino = function (id) {
    const item = id ? _items.find(x => String(x.id) === String(id)) : null;
    const m = item || {};
    const modal = document.getElementById('modalInquilino');
    if (!modal) return;
    document.getElementById('inquilinoId').value = m.id || '';
    document.getElementById('inquilinoNombre').value = m.nombre || '';
    document.getElementById('inquilinoApellido').value = m.apellido || '';
    document.getElementById('inquilinoTel').value = m.telefono || '';
    document.getElementById('inquilinoEmail').value = m.email || '';
    document.getElementById('inquilinoDoc').value = m.documento || '';
    document.getElementById('inquilinoEstado').value = m.estado || 'activo';
    document.getElementById('inquilinoFechaInicio').value = (m.fecha_inicio || '').slice(0, 10);
    document.getElementById('inquilinoFechaFin').value = (m.fecha_fin || '').slice(0, 10);
    document.getElementById('inquilinoMonto').value = m.monto_alquiler_actual || '';
    document.getElementById('inquilinoGaranteNombre').value = m.garante_nombre || '';
    document.getElementById('inquilinoGaranteTel').value = m.garante_telefono || '';
    document.getElementById('inquilinoNotas').value = m.notas || '';
    // Dropdown inmuebles
    const selInm = document.getElementById('inquilinoInmueble');
    selInm.innerHTML = '<option value="">— Sin inmueble —</option>' +
      _inmueblesCache.map(inm => `<option value="${inm.id}"${m.inmueble_renta_id == inm.id ? ' selected' : ''}>${inm.titulo || 'Inmueble #' + inm.id}</option>`).join('');
    modal.classList.add('show');
  };

  window.guardarInquilino = async function () {
    const id = document.getElementById('inquilinoId').value;
    const btn = document.getElementById('btnGuardarInquilino');
    if (btn) { btn.disabled = true; btn.textContent = 'Guardando...'; }
    const campos = {
      nombre: document.getElementById('inquilinoNombre').value,
      apellido: document.getElementById('inquilinoApellido').value,
      telefono: document.getElementById('inquilinoTel').value || null,
      email: document.getElementById('inquilinoEmail').value || null,
      documento: document.getElementById('inquilinoDoc').value || null,
      inmueble_renta_id: parseInt(document.getElementById('inquilinoInmueble').value) || null,
      estado: document.getElementById('inquilinoEstado').value,
      fecha_inicio: document.getElementById('inquilinoFechaInicio').value || null,
      fecha_fin: document.getElementById('inquilinoFechaFin').value || null,
      monto_alquiler_actual: parseFloat(document.getElementById('inquilinoMonto').value) || null,
      garante_nombre: document.getElementById('inquilinoGaranteNombre').value || null,
      garante_telefono: document.getElementById('inquilinoGaranteTel').value || null,
      notas: document.getElementById('inquilinoNotas').value || null,
    };
    try {
      if (id) await crmUpdate('inquilinos', id, campos);
      else await crmCreate('inquilinos', campos);
      document.getElementById('modalInquilino').classList.remove('show');
      notif('Inquilino guardado', [campos.nombre, campos.apellido].join(' ').trim());
      cargarInquilinos();
    } catch (e) {
      notif('Error al guardar', e.message);
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = 'Guardar'; }
    }
  };

  window._eliminarInquilino = async function (id, nombre) {
    if (!confirm('Eliminar "' + nombre + '"?')) return;
    try {
      await crmDelete('inquilinos', id);
      notif('Inquilino eliminado', nombre);
      cargarInquilinos();
    } catch (e) {
      notif('Error', e.message);
    }
  };

  function _skeletonRow(n) {
    return Array(n).fill(0).map(() =>
      `<tr>${Array(4).fill('<td><div style="background:rgba(255,255,255,.05);height:14px;border-radius:4px;margin:4px 0"></div></td>').join('')}</tr>`
    ).join('');
  }

})();
