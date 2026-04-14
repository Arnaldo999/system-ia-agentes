// Panel Propietarios — cartera de terceros (agencias)
(function(){
  let PROPIETARIOS = [];

  window.cargarPropietarios = async function() {
    try {
      const data = await crmList('propietarios');
      PROPIETARIOS = data.items || [];
      renderPropietarios();
    } catch (e) {
      console.error('[PROPIETARIOS]', e);
      notif('❌ Error cargando propietarios', e.message);
    }
  };

  function renderPropietarios() {
    const cont = document.getElementById('propietariosLista');
    if (!cont) return;
    if (PROPIETARIOS.length === 0) {
      cont.innerHTML = `<div class="p-8 text-center text-txt-2">
        <div class="text-4xl mb-2">📑</div>
        <p class="text-sm">Aún no hay propietarios cargados.</p>
        <button onclick="abrirModalPropietario()" class="mt-3 btn-primary">+ Agregar primer propietario</button>
      </div>`;
      return;
    }
    cont.innerHTML = `
      <div class="overflow-auto">
        <table class="w-full text-sm">
          <thead class="bg-surface-alt text-txt-2 text-xs uppercase">
            <tr>
              <th class="text-left p-2">Nombre</th>
              <th class="text-left p-2">Teléfono</th>
              <th class="text-left p-2">Email</th>
              <th class="text-left p-2">DNI/CUIT</th>
              <th class="text-left p-2">Comisión</th>
              <th class="text-left p-2">Props</th>
              <th class="text-right p-2">Acciones</th>
            </tr>
          </thead>
          <tbody>
            ${PROPIETARIOS.map(p => `
              <tr class="border-b border-brd hover:bg-surface-alt">
                <td class="p-2 font-medium">${p.nombre || ''}</td>
                <td class="p-2 text-xs">${p.telefono || ''}</td>
                <td class="p-2 text-xs">${p.email || ''}</td>
                <td class="p-2 text-xs">${p.dni_cuit || ''}</td>
                <td class="p-2 text-xs">${p.comision_pactada ? p.comision_pactada + '%' : '—'}</td>
                <td class="p-2 text-xs">${p.cantidad_propiedades || 0}</td>
                <td class="p-2 text-right">
                  <button onclick='abrirModalPropietario(${JSON.stringify(p).replace(/'/g, "&apos;")})' class="text-xs px-2 py-1 bg-primary/20 text-primary rounded">Editar</button>
                  <button onclick="eliminarPropietario(${p.id})" class="text-xs px-2 py-1 bg-red-500/20 text-red-400 rounded">🗑</button>
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    `;
  }

  window.abrirModalPropietario = function(data = null) {
    const p = data || {};
    const modal = document.getElementById('modalPropietario');
    if (!modal) return;
    document.getElementById('propietarioId').value = p.id || '';
    document.getElementById('propietarioNombre').value = p.nombre || '';
    document.getElementById('propietarioTelefono').value = p.telefono || '';
    document.getElementById('propietarioEmail').value = p.email || '';
    document.getElementById('propietarioDni').value = p.dni_cuit || '';
    document.getElementById('propietarioDireccion').value = p.direccion || '';
    document.getElementById('propietarioComision').value = p.comision_pactada || '';
    document.getElementById('propietarioNotas').value = p.notas || '';
    abrirModal('modalPropietario');
  };

  window.guardarPropietario = async function() {
    const id = document.getElementById('propietarioId').value;
    const campos = {
      nombre: document.getElementById('propietarioNombre').value,
      telefono: document.getElementById('propietarioTelefono').value,
      email: document.getElementById('propietarioEmail').value,
      dni_cuit: document.getElementById('propietarioDni').value,
      direccion: document.getElementById('propietarioDireccion').value,
      comision_pactada: parseFloat(document.getElementById('propietarioComision').value) || null,
      notas: document.getElementById('propietarioNotas').value,
    };
    try {
      if (id) await crmUpdate('propietarios', id, campos);
      else await crmCreate('propietarios', campos);
      cerrarModal('modalPropietario');
      notif('✅ Propietario guardado', campos.nombre);
      cargarPropietarios();
    } catch (e) {
      notif('❌ Error', e.message);
    }
  };

  window.eliminarPropietario = async function(id) {
    if (!confirm('¿Eliminar este propietario? (sus propiedades quedarán sin vincular)')) return;
    try {
      await crmDelete('propietarios', id);
      notif('✅ Propietario eliminado');
      cargarPropietarios();
    } catch (e) { notif('❌ Error', e.message); }
  };
})();
