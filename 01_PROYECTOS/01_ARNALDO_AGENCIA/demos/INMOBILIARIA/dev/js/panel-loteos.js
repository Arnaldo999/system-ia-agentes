// Panel Loteos + Mapa SVG — proyectos para desarrolladoras
(function(){
  let LOTEOS = [];
  let LOTES_ACTUAL = [];

  window.cargarLoteos = async function() {
    try {
      const data = await crmList('loteos');
      LOTEOS = data.items || [];
      renderLoteos();
    } catch (e) {
      console.error('[LOTEOS]', e);
      notif('❌ Error cargando loteos', e.message);
    }
  };

  function renderLoteos() {
    const cont = document.getElementById('loteosLista');
    if (!cont) return;
    if (LOTEOS.length === 0) {
      cont.innerHTML = `<div class="p-8 text-center text-txt-2">
        <div class="text-4xl mb-2">📍</div>
        <p class="text-sm">Aún no hay loteos cargados.</p>
        <p class="text-xs mt-2">Los loteos permiten mostrar mapas SVG interactivos con estado de cada lote.</p>
        <button onclick="abrirModalLoteo()" class="mt-3 btn-primary">+ Crear primer loteo</button>
      </div>`;
      return;
    }
    cont.innerHTML = `<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      ${LOTEOS.map(l => `
        <div class="bg-surface border border-brd rounded-lg overflow-hidden hover:border-primary transition">
          ${l.mapa_svg_url ? `<div class="bg-surface-alt aspect-video flex items-center justify-center"><img src="${l.mapa_svg_url}" class="max-h-full max-w-full" alt="${l.nombre}"/></div>` : `<div class="bg-surface-alt aspect-video flex items-center justify-center text-4xl">🗺️</div>`}
          <div class="p-4">
            <div class="font-semibold">${l.nombre}</div>
            <div class="text-xs text-txt-2 mb-2">${l.ubicacion || l.ciudad || ''}</div>
            <div class="grid grid-cols-3 gap-2 text-xs mb-3">
              <div class="bg-green-500/10 text-green-400 p-2 rounded text-center">
                <div class="font-bold text-base">${l.lotes_disponibles || 0}</div>
                <div>Disponibles</div>
              </div>
              <div class="bg-yellow-500/10 text-yellow-400 p-2 rounded text-center">
                <div class="font-bold text-base">${l.lotes_reservados || 0}</div>
                <div>Reservados</div>
              </div>
              <div class="bg-red-500/10 text-red-400 p-2 rounded text-center">
                <div class="font-bold text-base">${l.lotes_vendidos || 0}</div>
                <div>Vendidos</div>
              </div>
            </div>
            <div class="flex gap-2">
              <button onclick="verMapaLoteo(${l.id})" class="flex-1 text-xs px-2 py-2 bg-primary/20 text-primary rounded hover:bg-primary/30">🗺️ Ver mapa</button>
              <button onclick='abrirModalLoteo(${JSON.stringify(l).replace(/'/g, "&apos;")})' class="text-xs px-2 py-2 bg-surface-alt rounded">✏️</button>
              <button onclick="eliminarLoteo(${l.id})" class="text-xs px-2 py-2 bg-red-500/20 text-red-400 rounded">🗑</button>
            </div>
          </div>
        </div>
      `).join('')}
    </div>`;
  }

  window.abrirModalLoteo = function(data = null) {
    const l = data || {};
    const modal = document.getElementById('modalLoteo');
    if (!modal) return;
    document.getElementById('loteoId').value = l.id || '';
    document.getElementById('loteoNombre').value = l.nombre || '';
    document.getElementById('loteoSlug').value = l.slug || '';
    document.getElementById('loteoUbicacion').value = l.ubicacion || '';
    document.getElementById('loteoCiudad').value = l.ciudad || '';
    document.getElementById('loteoMapa').value = l.mapa_svg_url || '';
    document.getElementById('loteoPrecio').value = l.precio_desde || '';
    document.getElementById('loteoDescripcion').value = l.descripcion || '';
    modal.classList.remove('hidden');
  };

  window.guardarLoteo = async function() {
    const id = document.getElementById('loteoId').value;
    const campos = {
      nombre: document.getElementById('loteoNombre').value,
      slug: document.getElementById('loteoSlug').value || document.getElementById('loteoNombre').value.toLowerCase().replace(/\s+/g, '-'),
      ubicacion: document.getElementById('loteoUbicacion').value,
      ciudad: document.getElementById('loteoCiudad').value,
      mapa_svg_url: document.getElementById('loteoMapa').value,
      precio_desde: parseFloat(document.getElementById('loteoPrecio').value) || null,
      descripcion: document.getElementById('loteoDescripcion').value,
    };
    try {
      if (id) await crmUpdate('loteos', id, campos);
      else await crmCreate('loteos', campos);
      document.getElementById('modalLoteo').classList.add('hidden');
      notif('✅ Loteo guardado', campos.nombre);
      cargarLoteos();
    } catch (e) { notif('❌ Error', e.message); }
  };

  window.eliminarLoteo = async function(id) {
    if (!confirm('¿Eliminar este loteo y todos sus pines del mapa?')) return;
    try {
      await crmDelete('loteos', id);
      notif('✅ Loteo eliminado');
      cargarLoteos();
    } catch (e) { notif('❌ Error', e.message); }
  };

  window.verMapaLoteo = async function(loteoId) {
    const loteo = LOTEOS.find(l => l.id === loteoId);
    if (!loteo) return;
    try {
      const data = await crmFetch(`/crm/lotes-mapa?loteo_id=${loteoId}`);
      LOTES_ACTUAL = data.items || [];
      const modal = document.getElementById('modalMapa');
      document.getElementById('mapaTitulo').textContent = `🗺️ ${loteo.nombre}`;
      const cont = document.getElementById('mapaContenido');
      if (LOTES_ACTUAL.length === 0) {
        cont.innerHTML = `<div class="p-8 text-center text-txt-2">
          <p class="text-sm">Este loteo aún no tiene pines calibrados.</p>
          <p class="text-xs mt-2">Cargá el SVG base en el loteo, luego agregá cada lote con sus coordenadas.</p>
        </div>`;
      } else {
        cont.innerHTML = `
          ${loteo.mapa_svg_url ? `<div class="relative inline-block"><img src="${loteo.mapa_svg_url}" class="max-w-full"/>
            ${LOTES_ACTUAL.map(lote => {
              const color = lote.estado === 'vendido' ? 'bg-red-500' : lote.estado === 'reservado' ? 'bg-yellow-500' : 'bg-green-500';
              return `<div class="absolute w-3 h-3 rounded-full ${color} border-2 border-white" style="left:${lote.coord_x}%;top:${lote.coord_y}%;transform:translate(-50%,-50%)" title="Lote ${lote.numero_lote} (${lote.estado})"></div>`;
            }).join('')}
          </div>` : ''}
          <div class="mt-4 text-xs">
            <div class="flex gap-4 mb-2">
              <span class="flex items-center gap-1"><span class="w-3 h-3 bg-green-500 rounded-full"></span> Disponible</span>
              <span class="flex items-center gap-1"><span class="w-3 h-3 bg-yellow-500 rounded-full"></span> Reservado</span>
              <span class="flex items-center gap-1"><span class="w-3 h-3 bg-red-500 rounded-full"></span> Vendido</span>
            </div>
            <p class="text-txt-2">Total lotes: ${LOTES_ACTUAL.length}</p>
          </div>
        `;
      }
      modal.classList.remove('hidden');
    } catch (e) { notif('❌ Error', e.message); }
  };
})();
