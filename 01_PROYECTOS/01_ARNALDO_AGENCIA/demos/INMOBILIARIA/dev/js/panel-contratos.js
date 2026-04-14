// Panel Contratos — reservas, ventas, alquileres con PDFs
(function(){
  let CONTRATOS = [];

  window.cargarContratos = async function() {
    try {
      const data = await crmList('contratos');
      CONTRATOS = data.items || [];
      renderContratos();
    } catch (e) {
      console.error('[CONTRATOS]', e);
      notif('❌ Error cargando contratos', e.message);
    }
  };

  function estadoBadge(estado) {
    const colores = {
      pendiente: 'bg-yellow-500/20 text-yellow-400',
      firmado: 'bg-green-500/20 text-green-400',
      vencido: 'bg-red-500/20 text-red-400',
      cancelado: 'bg-gray-500/20 text-gray-400'
    };
    return `<span class="text-xs px-2 py-1 rounded ${colores[estado] || 'bg-surface-alt'}">${estado || 'pendiente'}</span>`;
  }

  function renderContratos() {
    const cont = document.getElementById('contratosLista');
    if (!cont) return;
    if (CONTRATOS.length === 0) {
      cont.innerHTML = `<div class="p-8 text-center text-txt-2">
        <div class="text-4xl mb-2">📄</div>
        <p class="text-sm">Aún no hay contratos cargados.</p>
        <button onclick="abrirModalContrato()" class="mt-3 btn-primary">+ Agregar primer contrato</button>
      </div>`;
      return;
    }
    cont.innerHTML = `
      <div class="overflow-auto">
        <table class="w-full text-sm">
          <thead class="bg-surface-alt text-txt-2 text-xs uppercase">
            <tr>
              <th class="text-left p-2">Título</th>
              <th class="text-left p-2">Tipo</th>
              <th class="text-left p-2">Monto</th>
              <th class="text-left p-2">Firma</th>
              <th class="text-left p-2">Estado</th>
              <th class="text-left p-2">PDF</th>
              <th class="text-right p-2">Acciones</th>
            </tr>
          </thead>
          <tbody>
            ${CONTRATOS.map(c => `
              <tr class="border-b border-brd hover:bg-surface-alt">
                <td class="p-2 font-medium">${c.titulo || '(sin título)'}</td>
                <td class="p-2 text-xs capitalize">${c.tipo || ''}</td>
                <td class="p-2 text-xs">${c.monto ? (c.moneda || 'USD') + ' ' + Number(c.monto).toLocaleString() : '—'}</td>
                <td class="p-2 text-xs">${c.fecha_firma ? c.fecha_firma.substring(0,10) : '—'}</td>
                <td class="p-2">${estadoBadge(c.estado)}</td>
                <td class="p-2 text-xs">${c.archivo_url ? `<a href="${c.archivo_url}" target="_blank" class="text-primary hover:underline">📎 Ver</a>` : '—'}</td>
                <td class="p-2 text-right">
                  <button onclick='abrirModalContrato(${JSON.stringify(c).replace(/'/g, "&apos;")})' class="text-xs px-2 py-1 bg-primary/20 text-primary rounded">Editar</button>
                  <button onclick="eliminarContrato(${c.id})" class="text-xs px-2 py-1 bg-red-500/20 text-red-400 rounded">🗑</button>
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    `;
  }

  window.abrirModalContrato = function(data = null) {
    const c = data || {};
    const modal = document.getElementById('modalContrato');
    if (!modal) return;
    document.getElementById('contratoId').value = c.id || '';
    document.getElementById('contratoTitulo').value = c.titulo || '';
    document.getElementById('contratoTipo').value = c.tipo || 'reserva';
    document.getElementById('contratoMonto').value = c.monto || '';
    document.getElementById('contratoMoneda').value = c.moneda || 'USD';
    document.getElementById('contratoFechaFirma').value = (c.fecha_firma || '').substring(0,10);
    document.getElementById('contratoFechaVenc').value = (c.fecha_vencimiento || '').substring(0,10);
    document.getElementById('contratoEstado').value = c.estado || 'pendiente';
    document.getElementById('contratoArchivoUrl').value = c.archivo_url || '';
    document.getElementById('contratoNotas').value = c.notas || '';
    modal.classList.remove('hidden');
  };

  window.subirPdfContrato = async function(fileInput) {
    const file = fileInput.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async () => {
      try {
        notif('📤 Subiendo PDF...', 'Esto puede tardar unos segundos');
        const data = await crmFetch('/crm/upload-pdf', { method: 'POST', body: JSON.stringify({ file: reader.result }) });
        if (data.url) {
          document.getElementById('contratoArchivoUrl').value = data.url;
          notif('✅ PDF subido');
        } else throw new Error('No se recibió URL');
      } catch (e) { notif('❌ Error subiendo', e.message); }
    };
    reader.readAsDataURL(file);
  };

  window.guardarContrato = async function() {
    const id = document.getElementById('contratoId').value;
    const campos = {
      titulo: document.getElementById('contratoTitulo').value,
      tipo: document.getElementById('contratoTipo').value,
      monto: parseFloat(document.getElementById('contratoMonto').value) || null,
      moneda: document.getElementById('contratoMoneda').value,
      fecha_firma: document.getElementById('contratoFechaFirma').value || null,
      fecha_vencimiento: document.getElementById('contratoFechaVenc').value || null,
      estado: document.getElementById('contratoEstado').value,
      archivo_url: document.getElementById('contratoArchivoUrl').value,
      notas: document.getElementById('contratoNotas').value,
    };
    try {
      if (id) await crmUpdate('contratos', id, campos);
      else await crmCreate('contratos', campos);
      document.getElementById('modalContrato').classList.add('hidden');
      notif('✅ Contrato guardado', campos.titulo);
      cargarContratos();
    } catch (e) { notif('❌ Error', e.message); }
  };

  window.eliminarContrato = async function(id) {
    if (!confirm('¿Eliminar este contrato?')) return;
    try {
      await crmDelete('contratos', id);
      notif('✅ Contrato eliminado');
      cargarContratos();
    } catch (e) { notif('❌ Error', e.message); }
  };
})();
