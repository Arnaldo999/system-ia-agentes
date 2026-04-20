// Panel Loteos — self-service: grilla de tarjetas con CRUD de lotes
// Cliente carga loteos con N lotes → grilla de tarjetitas clickeables
// Cada tarjetita: vacía (+), libre (verde), reservado (amarillo) o vendido (rojo)
// Estados reservado/vendido se sincronizan con tabla clientes_activos
(function(){
  let LOTEOS = [];
  let LOTE_ACTUAL = null;            // loteo abierto en modalMapa
  let LOTES_ACTUAL = [];             // lotes_mapa del loteo actual
  let CLIENTES_CACHE = [];           // cache de clientes_activos para dropdown

  // ── Utilidades ────────────────────────────────────────────────────────────

  function esUrlMaps(str) {
    if (!str) return false;
    return /^https?:\/\/(www\.)?(google\.[a-z.]+\/maps|maps\.google|maps\.app\.goo\.gl|goo\.gl\/maps)/i.test(str.trim());
  }

  function calcularGrilla(total) {
    // Devuelve { cols, rows } priorizando que quepa en una sola pantalla.
    // Para totales chicos, forma cuadrada. Para totales grandes, aumenta cols.
    const t = parseInt(total) || 0;
    if (t <= 0) return { cols: 0, rows: 0 };
    // Tope de columnas por breakpoint visual: 8 (móvil/chico) / 12 (medio) / 16 (grande)
    const maxCols = t <= 25 ? 5 : t <= 64 ? 8 : t <= 144 ? 12 : 16;
    const cols = Math.min(Math.ceil(Math.sqrt(t)), maxCols);
    const rows = Math.ceil(t / cols);
    return { cols, rows };
  }

  function contarPorEstado(lotes) {
    let libres = 0, reservados = 0, vendidos = 0;
    lotes.forEach(l => {
      if (l.estado === 'reservado') reservados++;
      else if (l.estado === 'vendido') vendidos++;
      else libres++;
    });
    return { libres, reservados, vendidos };
  }

  // ── Listado de loteos (cards grandes) ─────────────────────────────────────

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
      cont.innerHTML = `<div class="p-10 text-center text-txt-2 border border-dashed border-brd rounded-lg">
        <div class="text-5xl mb-3">📍</div>
        <p class="text-base mb-1">Aún no cargaste ningún loteo</p>
        <p class="text-xs mb-4">Creá tu primer loteo para empezar a cargar lotes individuales.</p>
        <button onclick="abrirModalLoteo()" class="btn-primary">+ Crear primer loteo</button>
      </div>`;
      return;
    }
    cont.innerHTML = `<div class="grid grid-cols-1 md:grid-cols-2 gap-5">
      ${LOTEOS.map(renderLoteoCard).join('')}
    </div>`;
  }

  function renderLoteoCard(l) {
    const total = l.total_lotes || 0;
    const libres = l.lotes_disponibles || 0;
    const reservados = l.lotes_reservados || 0;
    const vendidos = l.lotes_vendidos || 0;
    const ocupados = reservados + vendidos;
    const pctOcupado = total > 0 ? Math.round((ocupados / total) * 100) : 0;
    const ubic = l.ubicacion || l.ciudad || '';
    const ubicLabel = esUrlMaps(ubic)
      ? `<a href="${ubic}" target="_blank" class="text-primary hover:underline">📍 Ver en Google Maps</a>`
      : `<span>📍 ${ubic || l.ciudad || 'Sin ubicación'}</span>`;

    return `
      <div class="bg-surface border border-brd rounded-xl overflow-hidden hover:border-primary transition cursor-pointer" onclick="verMapaLoteo(${l.id})">
        <div class="bg-gradient-to-br from-primary/20 to-surface-alt p-6">
          <div class="flex items-start justify-between mb-2">
            <div class="flex-1 min-w-0">
              <div class="font-bold text-lg truncate">${l.nombre}</div>
              <div class="text-xs text-txt-2 mt-1">${ubicLabel}</div>
            </div>
            <div class="flex gap-1 ml-2" onclick="event.stopPropagation()">
              <button onclick='abrirModalLoteo(${JSON.stringify(l).replace(/'/g, "&apos;")})' title="Editar loteo" class="text-xs p-2 bg-surface-alt/70 rounded hover:bg-surface-alt">✏️</button>
              <button onclick="eliminarLoteo(${l.id})" title="Eliminar" class="text-xs p-2 bg-red-500/20 text-red-400 rounded hover:bg-red-500/30">🗑</button>
            </div>
          </div>
          ${l.descripcion ? `<p class="text-xs text-txt-2 mt-2 line-clamp-2">${l.descripcion}</p>` : ''}
        </div>
        <div class="p-5">
          <div class="flex items-center justify-between text-xs mb-2">
            <span class="text-txt-2">${total} lotes totales</span>
            <span class="font-semibold">${pctOcupado}% ocupado</span>
          </div>
          <div class="w-full h-2 bg-surface-alt rounded-full overflow-hidden mb-4">
            <div class="h-full bg-gradient-to-r from-green-500 to-yellow-500" style="width:${pctOcupado}%"></div>
          </div>
          <div class="grid grid-cols-3 gap-2 mb-4">
            <div class="bg-green-500/10 text-green-400 p-3 rounded text-center">
              <div class="font-bold text-xl">${libres}</div>
              <div class="text-[10px] uppercase tracking-wide">Libres</div>
            </div>
            <div class="bg-yellow-500/10 text-yellow-400 p-3 rounded text-center">
              <div class="font-bold text-xl">${reservados}</div>
              <div class="text-[10px] uppercase tracking-wide">Reservados</div>
            </div>
            <div class="bg-red-500/10 text-red-400 p-3 rounded text-center">
              <div class="font-bold text-xl">${vendidos}</div>
              <div class="text-[10px] uppercase tracking-wide">Vendidos</div>
            </div>
          </div>
          <button class="w-full text-sm px-3 py-2 bg-primary/20 text-primary rounded hover:bg-primary/30">🗺️ Abrir mapa del loteo</button>
        </div>
      </div>
    `;
  }

  // ── Modal crear/editar loteo ──────────────────────────────────────────────

  window.abrirModalLoteo = function(data = null) {
    const l = data || {};
    const modal = document.getElementById('modalLoteo');
    if (!modal) return;
    document.getElementById('loteoId').value = l.id || '';
    document.getElementById('loteoNombre').value = l.nombre || '';
    document.getElementById('loteoTotal').value = l.total_lotes || '';
    document.getElementById('loteoCiudad').value = l.ciudad || '';
    document.getElementById('loteoUbicacion').value = l.ubicacion || '';
    document.getElementById('loteoDescripcion').value = l.descripcion || '';
    document.getElementById('loteoSlug').value = l.slug || '';
    abrirModal('modalLoteo');
  };

  window.abrirModalLoteoDesdeMapa = function() {
    if (!LOTE_ACTUAL) return;
    abrirModalLoteo(LOTE_ACTUAL);
  };

  window.guardarLoteo = async function() {
    const id = document.getElementById('loteoId').value;
    const nombre = document.getElementById('loteoNombre').value.trim();
    const total = parseInt(document.getElementById('loteoTotal').value) || 0;
    if (!nombre) { notif('❌ Falta el nombre del loteo'); return; }
    if (total <= 0) { notif('❌ La cantidad de lotes debe ser mayor a 0'); return; }
    const slugActual = document.getElementById('loteoSlug').value.trim();
    const campos = {
      nombre,
      slug: slugActual || nombre.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, ''),
      total_lotes: total,
      ciudad: document.getElementById('loteoCiudad').value.trim(),
      ubicacion: document.getElementById('loteoUbicacion').value.trim(),
      descripcion: document.getElementById('loteoDescripcion').value.trim(),
    };
    try {
      if (id) await crmUpdate('loteos', id, campos);
      else await crmCreate('loteos', campos);
      cerrarModal('modalLoteo');
      notif('✅ Loteo guardado', campos.nombre);
      cargarLoteos();
      // Si estamos viendo ese loteo, refrescar el mapa
      if (LOTE_ACTUAL && id && Number(id) === LOTE_ACTUAL.id) {
        setTimeout(() => verMapaLoteo(LOTE_ACTUAL.id), 300);
      }
    } catch (e) { notif('❌ Error', e.message); }
  };

  window.eliminarLoteo = async function(id) {
    if (!confirm('¿Eliminar este loteo y todos sus lotes?')) return;
    try {
      await crmDelete('loteos', id);
      notif('✅ Loteo eliminado');
      cargarLoteos();
    } catch (e) { notif('❌ Error', e.message); }
  };

  // ── Mapa del loteo: grilla de tarjetitas ──────────────────────────────────

  window.verMapaLoteo = async function(loteoId) {
    const loteo = LOTEOS.find(l => l.id === loteoId);
    if (!loteo) return;
    LOTE_ACTUAL = loteo;
    try {
      const data = await crmFetch(`/crm/lotes-mapa?loteo_id=${loteoId}`);
      LOTES_ACTUAL = data.items || [];
      renderMapaLoteo();
      abrirModal('modalMapa');
    } catch (e) { notif('❌ Error', e.message); }
  };

  function renderMapaLoteo() {
    const loteo = LOTE_ACTUAL;
    const total = loteo.total_lotes || 0;
    const { cols, rows } = calcularGrilla(total);
    const counts = contarPorEstado(LOTES_ACTUAL);

    document.getElementById('mapaTitulo').textContent = `🗺️ ${loteo.nombre}`;
    const sub = document.getElementById('mapaSubtitulo');
    const ubic = loteo.ubicacion || loteo.ciudad || '';
    const ubicLabel = esUrlMaps(ubic)
      ? `<a href="${ubic}" target="_blank" class="text-primary hover:underline">Ver en Google Maps ↗</a>`
      : (ubic || 'Sin ubicación');
    sub.innerHTML = `${total} lotes · ${ubicLabel}`;

    // Construir grilla ordenada por posicion 1..N
    const lotesPorPos = {};
    LOTES_ACTUAL.forEach(l => {
      const pos = parseInt(l.manzana) || null;  // reutilizamos manzana como "posición en grilla"
      if (pos) lotesPorPos[pos] = l;
    });

    let tarjetas = '';
    for (let i = 1; i <= total; i++) {
      const lote = lotesPorPos[i];
      if (lote) {
        const color = lote.estado === 'vendido' ? 'bg-red-500/80 hover:bg-red-500 border-red-400'
                   : lote.estado === 'reservado' ? 'bg-yellow-500/80 hover:bg-yellow-500 border-yellow-400'
                   : 'bg-green-500/80 hover:bg-green-500 border-green-400';
        tarjetas += `<button onclick="abrirModalLote(${lote.id}, ${i})" class="relative aspect-square ${color} border text-white rounded transition font-semibold flex items-center justify-center p-0.5" title="Lote ${lote.numero_lote} — ${lote.estado}">
          <span class="text-[11px] leading-tight truncate max-w-full">${lote.numero_lote}</span>
        </button>`;
      } else {
        tarjetas += `<button onclick="abrirModalLote(null, ${i})" class="relative aspect-square bg-surface-alt/40 hover:bg-surface-alt border border-dashed border-brd hover:border-primary text-txt-2 hover:text-primary rounded transition flex items-center justify-center" title="Posición #${i}">
          <span class="text-base leading-none">+</span>
        </button>`;
      }
    }

    const cont = document.getElementById('mapaContenido');
    cont.innerHTML = `
      <div class="flex gap-4 text-xs mb-4 flex-wrap">
        <span class="flex items-center gap-2"><span class="w-4 h-4 bg-green-500 rounded"></span> Libres: ${counts.libres}</span>
        <span class="flex items-center gap-2"><span class="w-4 h-4 bg-yellow-500 rounded"></span> Reservados: ${counts.reservados}</span>
        <span class="flex items-center gap-2"><span class="w-4 h-4 bg-red-500 rounded"></span> Vendidos: ${counts.vendidos}</span>
        <span class="flex items-center gap-2 text-txt-2"><span class="w-4 h-4 border-2 border-dashed border-brd rounded"></span> Sin configurar</span>
      </div>
      <div class="bg-surface-alt/30 border border-brd rounded-lg p-3 overflow-auto" style="max-height:72vh">
        <div class="grid gap-1.5" style="grid-template-columns: repeat(${cols}, minmax(44px, 1fr))">
          ${tarjetas}
        </div>
      </div>
      <p class="text-xs text-txt-2 mt-3">Hacé clic en cualquier tarjetita <span class="text-primary">+</span> para cargar un lote, o sobre un lote existente para editarlo.</p>
    `;
  }

  // ── Modal crear/editar lote individual ────────────────────────────────────

  window.abrirModalLote = async function(loteIdOrNull, posicion) {
    if (!LOTE_ACTUAL) return;
    const lote = loteIdOrNull ? LOTES_ACTUAL.find(l => l.id === loteIdOrNull) : null;
    document.getElementById('loteId').value = lote ? lote.id : '';
    document.getElementById('loteLoteoId').value = LOTE_ACTUAL.id;
    document.getElementById('loteNumero').value = lote ? lote.numero_lote : `L-${posicion}`;
    document.getElementById('lotePrecio').value = lote && lote.precio ? lote.precio : '';
    document.getElementById('loteEstado').value = lote ? lote.estado : 'disponible';
    document.getElementById('loteTitulo').textContent = lote ? `🏷️ Editar lote ${lote.numero_lote}` : `🏷️ Nuevo lote (posición #${posicion})`;
    document.getElementById('loteSubtitulo').textContent = `${LOTE_ACTUAL.nombre} · posición ${posicion} de ${LOTE_ACTUAL.total_lotes}`;
    document.getElementById('btnEliminarLote').classList.toggle('hidden', !lote);
    // Guardar posición en dataset para que al crear se guarde en manzana
    document.getElementById('loteId').dataset.posicion = posicion;
    await cargarClientesDropdown(lote ? lote.cliente_id : null);
    toggleClienteLote();
    abrirModal('modalLote');
  };

  async function cargarClientesDropdown(clienteIdSeleccionado) {
    try {
      if (CLIENTES_CACHE.length === 0) {
        const data = await crmFetch('/crm/clientes');
        CLIENTES_CACHE = data.items || [];
      }
      const sel = document.getElementById('loteCliente');
      const opciones = CLIENTES_CACHE.map(c => {
        const label = `${c.nombre || ''} ${c.apellido || ''}`.trim() || c.telefono || `Cliente #${c.id}`;
        const selected = c.id === clienteIdSeleccionado ? 'selected' : '';
        return `<option value="${c.id}" ${selected}>${label}</option>`;
      }).join('');
      sel.innerHTML = `<option value="">— Sin asignar —</option>${opciones}`;
      sel.onchange = mostrarInfoCliente;
      mostrarInfoCliente();
    } catch (e) {
      console.error('[LOTEOS] cargar clientes', e);
    }
  }

  function mostrarInfoCliente() {
    const sel = document.getElementById('loteCliente');
    const info = document.getElementById('loteClienteInfo');
    const clienteId = parseInt(sel.value);
    if (!clienteId) { info.classList.add('hidden'); return; }
    const c = CLIENTES_CACHE.find(x => x.id === clienteId);
    if (!c) { info.classList.add('hidden'); return; }
    info.classList.remove('hidden');
    const pct = c.cuotas_total > 0 ? Math.round((c.cuotas_pagadas / c.cuotas_total) * 100) : 0;
    info.innerHTML = `
      <div class="font-semibold mb-1">${c.nombre || ''} ${c.apellido || ''}</div>
      ${c.telefono ? `<div>📞 ${c.telefono}</div>` : ''}
      ${c.email ? `<div>✉️ ${c.email}</div>` : ''}
      <div class="mt-2 grid grid-cols-2 gap-2">
        <div><span class="text-txt-2">Estado:</span> <span class="font-semibold">${c.estado_pago || 'al_dia'}</span></div>
        <div><span class="text-txt-2">Cuotas:</span> <span class="font-semibold">${c.cuotas_pagadas || 0}/${c.cuotas_total || 0} (${pct}%)</span></div>
        ${c.monto_cuota ? `<div><span class="text-txt-2">Cuota:</span> <span class="font-semibold">$${c.monto_cuota}</span></div>` : ''}
        ${c.proximo_vencimiento ? `<div><span class="text-txt-2">Vence:</span> <span class="font-semibold">${c.proximo_vencimiento}</span></div>` : ''}
      </div>
    `;
  }

  window.toggleClienteLote = function() {
    const estado = document.getElementById('loteEstado').value;
    const wrap = document.getElementById('loteClienteWrap');
    if (estado === 'reservado' || estado === 'vendido') {
      wrap.classList.remove('hidden');
    } else {
      wrap.classList.add('hidden');
      document.getElementById('loteCliente').value = '';
      document.getElementById('loteClienteInfo').classList.add('hidden');
    }
  };

  window.guardarLote = async function() {
    if (!LOTE_ACTUAL) return;
    const id = document.getElementById('loteId').value;
    const posicion = parseInt(document.getElementById('loteId').dataset.posicion) || null;
    const numero = document.getElementById('loteNumero').value.trim();
    const estado = document.getElementById('loteEstado').value;
    const clienteSel = document.getElementById('loteCliente').value;
    if (!numero) { notif('❌ Falta el número de lote'); return; }

    const campos = {
      loteo_id: LOTE_ACTUAL.id,
      numero_lote: numero,
      manzana: String(posicion || ''),  // reutilizamos manzana como posición en grilla
      estado,
      precio: parseFloat(document.getElementById('lotePrecio').value) || null,
      cliente_id: (estado === 'reservado' || estado === 'vendido') && clienteSel ? parseInt(clienteSel) : null,
    };
    try {
      if (id) await crmUpdate('lotes-mapa', id, campos);
      else await crmCreate('lotes-mapa', campos);
      cerrarModal('modalLote');
      notif('✅ Lote guardado', numero);
      // Refrescar todo: loteos (contadores) + mapa (lotes)
      await cargarLoteos();
      await verMapaLoteo(LOTE_ACTUAL.id);
    } catch (e) { notif('❌ Error', e.message); }
  };

  window.eliminarLote = async function() {
    const id = document.getElementById('loteId').value;
    if (!id) return;
    if (!confirm('¿Eliminar este lote?')) return;
    try {
      await crmDelete('lotes-mapa', id);
      cerrarModal('modalLote');
      notif('✅ Lote eliminado');
      await cargarLoteos();
      await verMapaLoteo(LOTE_ACTUAL.id);
    } catch (e) { notif('❌ Error', e.message); }
  };
})();
