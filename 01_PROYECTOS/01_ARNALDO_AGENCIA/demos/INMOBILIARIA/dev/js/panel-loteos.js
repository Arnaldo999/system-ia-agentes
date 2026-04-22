// Panel Loteos — granular v3
// Fuente de verdad: tabla lotes_mapa (GET /crm/loteos/{id}/lotes agrupado por manzana).
// El usuario puede: crear manzana, agregar lote, renombrar manzana, borrar lote/manzana.
// loteos.total_lotes sigue existiendo para backward compat en tarjetas, pero el mapa
// ya no lo usa para derivar lotes — lee directamente los registros de lotes_mapa.
(function(){
  let LOTEOS = [];
  let LOTE_ACTUAL = null;              // loteo abierto en panel-map
  let LOTE_SELECCIONADO = null;        // lote individual seleccionado
  let CLIENTES_CACHE = [];
  let FILTRO_CIUDAD = 'todos';
  let GRUPOS_ACTUALES = [];            // cache de grupos del loteo actual

  // ── Utilidades ─────────────────────────────────────────────────────────────

  function esUrlMaps(str) {
    if (!str) return false;
    return /^https?:\/\/(www\.)?(google\.[a-z.]+\/maps|maps\.google|maps\.app\.goo\.gl|goo\.gl\/maps)/i.test(str.trim());
  }

  // Parsea propiedad "San Ignacio · 5" → { loteo, nro }
  function parsePropiedad(propiedad) {
    if (!propiedad) return null;
    const parts = propiedad.split('·').map(s => s.trim());
    if (parts.length < 2) return null;
    return { loteo: parts[0], nro: parts.slice(1).join('·').trim() };
  }

  // Cruza clientes con un loteo: devuelve mapa { nro_lote: {cliente, estado} }
  function indexarClientesPorLote(loteoNombre) {
    const idx = {};
    CLIENTES_CACHE.forEach(c => {
      const p = parsePropiedad(c.propiedad);
      if (!p || p.loteo !== loteoNombre) return;
      const ep = (c.estado_pago || '').toLowerCase();
      let estado = 'vendido';
      if (ep === 'atrasado' || ep === 'moroso' || ep === 'pendiente') estado = 'reservado';
      idx[p.nro] = { cliente: c, estado };
    });
    return idx;
  }

  function contarEstadosGrupos(grupos, clientesPorLote) {
    let libres = 0, reservados = 0, vendidos = 0;
    grupos.forEach(g => {
      g.lotes.forEach(l => {
        const est = _estadoEfectivo(l, clientesPorLote);
        if (est === 'vendido') vendidos++;
        else if (est === 'reservado') reservados++;
        else libres++;
      });
    });
    return { libres, reservados, vendidos };
  }

  const ESTADOS_LIBRES = new Set(['disponible', 'libre', 'free']);

  // Estado real de un lote: primero lo que diga lotes_mapa, luego cruce con clientes
  function _estadoEfectivo(lote, clientesPorLote) {
    if (lote.estado === 'vendido' || lote.cliente_id) return 'vendido';
    if (lote.estado === 'reservado') return 'reservado';
    // Cruce por numero_lote con clientes_activos.propiedad
    const asignado = clientesPorLote[String(lote.numero_lote)];
    if (asignado) return asignado.estado;
    return 'libre';  // disponible/libre ambos = libre en UI
  }

  // ── Carga combinada: loteos + clientes ─────────────────────────────────────

  window.cargarLoteos = async function() {
    try {
      const [loteosData, clientesData] = await Promise.all([
        crmList('loteos'),
        crmFetch('/crm/clientes'),
      ]);
      LOTEOS = loteosData.items || [];
      CLIENTES_CACHE = clientesData.items || clientesData.records || [];
      renderLoteos();
    } catch (e) {
      console.error('[LOTEOS]', e);
      notif('Error cargando loteos', e.message);
    }
  };

  function ciudadesUnicas() {
    const set = new Map();
    LOTEOS.forEach(l => {
      const key = (l.ciudad || 'Sin ciudad').trim();
      set.set(key, (set.get(key) || 0) + 1);
    });
    return Array.from(set.entries());
  }

  function loteosFiltrados() {
    if (FILTRO_CIUDAD === 'todos') return LOTEOS;
    return LOTEOS.filter(l => (l.ciudad || 'Sin ciudad').trim() === FILTRO_CIUDAD);
  }

  function renderOverview() {
    const cont = document.getElementById('loteosOverview');
    if (!cont) return;
    let totLotes = 0, totLibres = 0, totReservados = 0, totVendidos = 0;
    LOTEOS.forEach(l => {
      totLibres    += (l.lotes_disponibles || 0);
      totReservados+= (l.lotes_reservados  || 0);
      totVendidos  += (l.lotes_vendidos    || 0);
    });
    totLotes = totLibres + totReservados + totVendidos;
    const pctOcup = totLotes > 0 ? Math.round(((totReservados + totVendidos) / totLotes) * 100) : 0;

    cont.innerHTML = `
      <div class="overview cd-overview">
        <div class="ov" style="--c:#7c3aed">
          <div class="ov-label"><span class="d"></span>Loteos activos</div>
          <div class="ov-val mono">${LOTEOS.length}</div>
          <div class="ov-foot">En tu cartera</div>
        </div>
        <div class="ov" style="--c:#10b981">
          <div class="ov-label"><span class="d"></span>Lotes libres</div>
          <div class="ov-val mono">${totLibres}</div>
          <div class="ov-foot">Disponibles</div>
        </div>
        <div class="ov" style="--c:#f59e0b">
          <div class="ov-label"><span class="d"></span>Reservados</div>
          <div class="ov-val mono">${totReservados}</div>
          <div class="ov-foot">En proceso</div>
        </div>
        <div class="ov" style="--c:#ef4444">
          <div class="ov-label"><span class="d"></span>Vendidos</div>
          <div class="ov-val mono">${totVendidos}</div>
          <div class="ov-foot">Cerrados</div>
        </div>
        <div class="ov" style="--c:#06b6d4">
          <div class="ov-label"><span class="d"></span>% Ocupacion</div>
          <div class="ov-val mono">${pctOcup}%</div>
          <div class="ov-foot">${totLotes} lotes totales</div>
        </div>
      </div>
    `;
  }

  function renderFilterChips() {
    const cont = document.getElementById('loteosFilterBar');
    if (!cont) return;
    const ciudades = ciudadesUnicas();
    const chipTodos = `<button class="cd-chip ${FILTRO_CIUDAD === 'todos' ? 'active' : ''}" onclick="filtrarLoteosPorCiudad('todos')">Todos <span class="ct">${LOTEOS.length}</span></button>`;
    const chips = ciudades.map(([ciudad, count]) => `
      <button class="cd-chip ${FILTRO_CIUDAD === ciudad ? 'active' : ''}" onclick="filtrarLoteosPorCiudad('${ciudad.replace(/'/g, "\\'")}')">${ciudad} <span class="ct">${count}</span></button>
    `).join('');
    cont.innerHTML = chipTodos + chips;
  }

  window.filtrarLoteosPorCiudad = function(ciudad) {
    FILTRO_CIUDAD = ciudad;
    renderFilterChips();
    renderLoteos();
  };

  function renderLoteos() {
    const list = document.getElementById('loteosLista');
    if (!list) return;
    renderOverview();
    renderFilterChips();

    const filtrados = loteosFiltrados();
    const countEl = document.getElementById('loteosListCount');
    if (countEl) countEl.textContent = `${filtrados.length} ${filtrados.length === 1 ? 'activo' : 'activos'}`;

    if (filtrados.length === 0) {
      list.innerHTML = renderAddCard();
      return;
    }
    list.innerHTML = filtrados.map(renderLoteoCard).join('') + renderAddCard();

    if (!LOTE_ACTUAL || !filtrados.find(l => l.id === LOTE_ACTUAL.id)) {
      seleccionarLoteo(filtrados[0].id);
    } else {
      renderLotsStage();
    }
  }

  function renderAddCard() {
    return `
      <button class="cd-add-loteo" onclick="abrirModalLoteo()">
        <div class="plus">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
        </div>
        <div><div class="t">Agregar nuevo loteo</div><div class="s">Con lotes, manzanas y mapa</div></div>
      </button>
    `;
  }

  function renderLoteoCard(l) {
    const libres     = l.lotes_disponibles || 0;
    const reservados = l.lotes_reservados  || 0;
    const vendidos   = l.lotes_vendidos    || 0;
    const total      = libres + reservados + vendidos || l.total_lotes || 0;
    const pctVendidos   = total > 0 ? (vendidos   / total) * 100 : 0;
    const pctReservados = total > 0 ? (reservados / total) * 100 : 0;
    const pctOcupado    = total > 0 ? Math.round(((reservados + vendidos) / total) * 100) : 0;
    const ubic = l.ubicacion || l.ciudad || '';
    const ubicLabel = esUrlMaps(ubic)
      ? `<a href="${ubic}" target="_blank" class="cd-place-link" onclick="event.stopPropagation()">Ver en Google Maps</a>`
      : (ubic || l.ciudad || 'Sin ubicacion');

    const dataAttr = JSON.stringify(l).replace(/"/g, '&quot;');
    const selected = LOTE_ACTUAL && LOTE_ACTUAL.id === l.id ? 'selected' : '';

    return `
      <div class="cd-loteo ${selected}" data-id="${l.id}" onclick="seleccionarLoteo(${l.id})">
        <div class="cd-loteo-top">
          <div class="cd-loteo-info">
            <div class="cd-loteo-name">${l.nombre}</div>
            <div class="cd-loteo-place">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>
              <span>${ubicLabel}</span>
            </div>
          </div>
          <div class="cd-loteo-actions" onclick="event.stopPropagation()">
            <button class="cd-icon-btn" title="Editar" data-loteo="${dataAttr}" onclick="abrirModalLoteo(JSON.parse(this.dataset.loteo))">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
            </button>
            <button class="cd-icon-btn danger" title="Eliminar" onclick="eliminarLoteo(${l.id})">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"></path></svg>
            </button>
          </div>
        </div>
        <div class="cd-loteo-progress">
          <div class="seg s-sold"     style="width:${pctVendidos}%"></div>
          <div class="seg s-reserved" style="width:${pctReservados}%"></div>
        </div>
        <div class="cd-loteo-stats">
          <span><b>${total}</b> lotes totales</span>
          <span><b>${pctOcupado}%</b> ocupado</span>
        </div>
        <div class="cd-loteo-counts">
          <div class="cc f"><span class="n">${libres}</span>libres</div>
          <div class="cc r"><span class="n">${reservados}</span>reserv.</div>
          <div class="cc s"><span class="n">${vendidos}</span>vendidos</div>
        </div>
      </div>
    `;
  }

  // ── Seleccion de loteo y carga de lotes granulares ─────────────────────────

  window.seleccionarLoteo = function(id) {
    const l = LOTEOS.find(x => x.id === id);
    if (!l) return;
    LOTE_ACTUAL = l;
    LOTE_SELECCIONADO = null;
    document.querySelectorAll('#loteosLista .cd-loteo').forEach(el => {
      el.classList.toggle('selected', Number(el.dataset.id) === id);
    });
    renderDetailEmpty();
    cargarGruposYRenderizar(id);
  };

  async function cargarGruposYRenderizar(loteoId) {
    const stage = document.getElementById('lotsStage');
    if (stage) stage.innerHTML = `<div class="cd-stage-empty" style="font-size:13px;color:var(--text2)">Cargando lotes...</div>`;
    try {
      const [data, clientesData] = await Promise.all([
        crmFetch(`/crm/loteos/${loteoId}/lotes`),
        crmFetch('/crm/clientes'),
      ]);
      GRUPOS_ACTUALES = data.grupos || [];
      CLIENTES_CACHE  = clientesData.items || clientesData.records || [];
      renderLotsStage();
    } catch (e) {
      console.error('[LOTEOS]', e);
      if (stage) stage.innerHTML = `<div class="cd-stage-empty">Error cargando lotes: ${e.message}</div>`;
    }
  }

  // ── Panel centro: manzanas + lotes ─────────────────────────────────────────

  function renderLotsStage() {
    const stage   = document.getElementById('lotsStage');
    const nameEl  = document.getElementById('currentLoteoName');
    const metaEl  = document.getElementById('currentLoteoMeta');
    if (!stage || !LOTE_ACTUAL) return;

    const loteo = LOTE_ACTUAL;
    const clientesPorLote = indexarClientesPorLote(loteo.nombre);
    const totalLotes = GRUPOS_ACTUALES.reduce((s, g) => s + g.lotes.length, 0);
    const { libres, reservados, vendidos } = contarEstadosGrupos(GRUPOS_ACTUALES, clientesPorLote);

    if (nameEl) nameEl.textContent = `Loteo ${loteo.nombre}`;
    if (metaEl) {
      const ubic = loteo.ubicacion || loteo.ciudad || 'Sin ubicacion';
      metaEl.innerHTML = `${ubic} &nbsp;·&nbsp; ${totalLotes} lotes &nbsp;·&nbsp; ${GRUPOS_ACTUALES.length} manzanas
        <span style="margin-left:12px;font-size:11px">
          <span style="color:#10b981">${libres} libres</span> ·
          <span style="color:#f59e0b">${reservados} reserv.</span> ·
          <span style="color:#ef4444">${vendidos} vendidos</span>
        </span>`;
    }

    // Header: botones globales
    const headerBtns = `
      <div class="cd-stage-header-btns" style="display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap;align-items:center">
        <button class="cd-btn-secondary cd-btn-sm"
          onclick="abrirModalNuevaManzana()"
          style="display:flex;align-items:center;gap:5px">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="14" height="14"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          Nueva manzana
        </button>
      </div>`;

    if (GRUPOS_ACTUALES.length === 0) {
      stage.innerHTML = headerBtns + `<div class="cd-stage-empty">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" width="32" height="32"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 3v18"/></svg>
        <div>Este loteo no tiene lotes todavia.</div>
        <div style="font-size:12px;color:var(--text2);margin-top:4px">Usa "+ Nueva manzana" para empezar a cargar lotes.</div>
      </div>`;
      return;
    }

    const manzanasHtml = GRUPOS_ACTUALES.map(g => renderManzanaBloque(g, clientesPorLote)).join('');
    stage.innerHTML = headerBtns + `<div class="cd-map-inner">${manzanasHtml}</div>`;
  }

  function renderManzanaBloque(grupo, clientesPorLote) {
    const mz = grupo.manzana;
    const lotes = grupo.lotes || [];
    const colsManzana = lotes.length <= 4 ? lotes.length : Math.ceil(Math.sqrt(lotes.length));

    const mzSafe = JSON.stringify(mz).replace(/"/g, '&quot;');

    const headerMz = `
      <div class="cd-manzana-header" style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px">
        <div class="cd-manzana-label">Manzana ${mz}
          <span style="font-size:10px;color:var(--text2);font-weight:400;margin-left:6px">${lotes.length} lotes</span>
        </div>
        <div style="display:flex;gap:4px" onclick="event.stopPropagation()">
          <button class="cd-icon-btn cd-btn-xs" title="Agregar lote" onclick="abrirModalAgregarLote(${JSON.stringify(mz).replace(/"/g, '&quot;')})">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="13" height="13"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          </button>
          <button class="cd-icon-btn cd-btn-xs" title="Renombrar manzana" onclick="renombrarManzanaPrompt(${mzSafe})">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="13" height="13"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
          </button>
          <button class="cd-icon-btn cd-btn-xs danger" title="Eliminar manzana" onclick="eliminarManzana(${mzSafe})">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="13" height="13"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/></svg>
          </button>
        </div>
      </div>`;

    let lotesHtml;
    if (lotes.length === 0) {
      lotesHtml = `<div style="font-size:12px;color:var(--text2);padding:8px;text-align:center">
        Sin lotes — click [+] para agregar
      </div>`;
    } else {
      const cols = Math.min(colsManzana, lotes.length);
      lotesHtml = `<div class="cd-lots-row" style="grid-template-columns:repeat(${cols}, minmax(60px, 84px))">
        ${lotes.map(l => renderLotTile(l, clientesPorLote, mz)).join('')}
      </div>`;
    }

    return `
      <div class="cd-manzana">
        ${headerMz}
        ${lotesHtml}
      </div>`;
  }

  function renderLotTile(lote, clientesPorLote, manzana) {
    const estado = _estadoEfectivo(lote, clientesPorLote);
    const asignado = clientesPorLote[String(lote.numero_lote)];
    const stClass = estado === 'vendido' ? 'sold' : (estado === 'reservado' ? 'reserved' : 'free');
    const active = LOTE_SELECCIONADO && LOTE_SELECCIONADO.id === lote.id ? 'active' : '';
    const icon = stClass === 'sold'
      ? '<span class="cd-lot-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 13l4 4L19 7"/></svg></span>'
      : stClass === 'reserved'
      ? '<span class="cd-lot-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg></span>'
      : '';

    // Context menu en lotes libres: click derecho / long press para borrar
    const nroPadded = String(lote.numero_lote).padStart(2, '0');
    const loteLabel = `${manzana}-${nroPadded}`;
    const extraAttrs = (estado === 'libre' || estado === 'free')
      ? `oncontextmenu="event.preventDefault();confirmarBorrarLote(${lote.id},'${loteLabel}')" `
      : '';

    return `
      <button class="cd-lot ${stClass} ${active}" data-id="${lote.id}" data-nro="${lote.numero_lote}" data-manzana="${manzana}"
        ${extraAttrs}
        onclick="seleccionarLote(${lote.id},'${lote.numero_lote}','${manzana}')">
        ${icon}
        <div class="cd-lot-body">
          <div class="cd-lot-n">${loteLabel}</div>
          ${lote.precio ? `<div class="cd-lot-price" style="font-size:9px;color:var(--text2);margin-top:1px">$${Number(lote.precio).toLocaleString()}</div>` : ''}
        </div>
      </button>`;
  }

  // ── Seleccion de lote individual ───────────────────────────────────────────

  window.seleccionarLote = function(loteId, nroLote, manzana) {
    if (!LOTE_ACTUAL) return;
    // Buscar lote en cache de grupos
    let loteObj = null;
    for (const g of GRUPOS_ACTUALES) {
      loteObj = g.lotes.find(l => l.id === loteId);
      if (loteObj) break;
    }
    const clientesPorLote = indexarClientesPorLote(LOTE_ACTUAL.nombre);
    const estado = loteObj ? _estadoEfectivo(loteObj, clientesPorLote) : 'libre';
    const asignado = clientesPorLote[String(nroLote)];
    const clienteData = loteObj && loteObj.cliente_id
      ? CLIENTES_CACHE.find(c => c.id === loteObj.cliente_id) || null
      : (asignado ? asignado.cliente : null);

    LOTE_SELECCIONADO = {
      id: loteId, nro: String(nroLote), manzana,
      cliente: clienteData,
      estado,
      loteObj,
    };

    document.querySelectorAll('#lotsStage .cd-lot').forEach(el => {
      el.classList.toggle('active', Number(el.dataset.id) === loteId);
    });
    renderDetail();
  };

  // ── Panel derecho: detalle del lote ────────────────────────────────────────

  function renderDetailEmpty() {
    const body = document.getElementById('detailBody');
    if (!body) return;
    body.innerHTML = `
      <div class="cd-detail-empty">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" width="36" height="36"><path d="M9 3H5a2 2 0 0 0-2 2v4m6-6h10a2 2 0 0 1 2 2v4M9 3v18m0 0H5a2 2 0 0 1-2-2v-4m6 6h10a2 2 0 0 0 2-2v-4M3 15v-2m18 2v-2"/></svg>
        <div class="cd-detail-empty-title">Ningun lote seleccionado</div>
        <div class="cd-detail-empty-sub">Elegi un lote del mapa para ver su ficha</div>
      </div>
    `;
  }

  function renderDetail() {
    const body = document.getElementById('detailBody');
    if (!body || !LOTE_SELECCIONADO || !LOTE_ACTUAL) return;

    const { id, nro, manzana, cliente, estado, loteObj } = LOTE_SELECCIONADO;
    const stLabel = estado === 'vendido' ? 'Vendido' : (estado === 'reservado' ? 'Reservado' : 'Libre');
    const stCls   = estado === 'vendido' ? 'sold'    : (estado === 'reservado' ? 'reserved'  : 'free');
    const nroPadded = String(nro).padStart(2, '0');

    const clienteBlock = cliente ? `
      <div class="cd-dt-section-title">Cliente asignado</div>
      <div class="cd-dt-client">
        <div class="cd-dt-client-avatar">${((cliente.nombre || '?') + ' ' + (cliente.apellido || '')).trim().split(' ').map(x => x[0] || '').join('').slice(0,2).toUpperCase()}</div>
        <div class="cd-dt-client-info">
          <div class="cd-dt-client-name">${(cliente.nombre || '') + ' ' + (cliente.apellido || '')}</div>
          <div class="cd-dt-client-meta"><span class="mono">${cliente.telefono || '—'}</span>${cliente.estado_pago ? `<span class="sep">·</span><span>${cliente.estado_pago}</span>` : ''}</div>
        </div>
        <button class="cd-icon-btn" title="Ver ficha" onclick="verInfoClienteLote(${cliente.id})">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg>
        </button>
      </div>
    ` : '';

    const precioBlock = loteObj && loteObj.precio ? `
      <div class="cd-dt-section-title">Precio</div>
      <div class="cd-dt-grid">
        <div class="cd-dt-cell"><div class="l">Precio</div><div class="v">USD ${Number(loteObj.precio).toLocaleString()}</div></div>
      </div>
    ` : '';

    const actions = (estado === 'libre' || estado === 'free') ? `
      <button class="cd-btn-primary" onclick="typeof abrirContratoDesideLote==='function' ? abrirContratoDesideLote(null,'${(LOTE_ACTUAL.nombre||'').replace(/'/g,"\\'")}','${nro}') : notif('Modal contrato','Cargando...')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 13l4 4L19 7"/></svg>
        Nuevo contrato
      </button>
      <button class="cd-btn-secondary" onclick="confirmarBorrarLote(${id},'${manzana}-${nroPadded}')" style="color:#ef4444;border-color:#ef4444">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/></svg>
        Eliminar lote
      </button>
    ` : cliente ? `
      <button class="cd-btn-primary"   onclick="verInfoClienteLote(${cliente.id})">Ver ficha cliente</button>
      <button class="cd-btn-secondary" onclick="window.open('https://wa.me/${(cliente.telefono||'').replace(/[^0-9]/g,'')}','_blank')">WhatsApp</button>
    ` : '';

    body.innerHTML = `
      <div class="cd-dt-head">
        <div>
          <div class="cd-dt-id">Manzana ${manzana} · ${nro}</div>
          <div class="cd-dt-name">${manzana}-${nroPadded}</div>
        </div>
        <div class="cd-dt-status ${stCls}"><span class="d"></span>${stLabel}</div>
      </div>

      <div class="cd-dt-hero">
        <div class="cd-dt-hero-row">
          <div>
            <div class="cd-dt-sup">Loteo</div>
            <div class="cd-dt-price">${LOTE_ACTUAL.nombre}</div>
            <div class="cd-dt-m2">${LOTE_ACTUAL.ciudad || ''}${LOTE_ACTUAL.ubicacion ? ' · ' + LOTE_ACTUAL.ubicacion : ''}</div>
          </div>
        </div>
      </div>

      ${precioBlock}
      ${clienteBlock}

      ${cliente ? `
        <div class="cd-dt-section-title">Estado de pago</div>
        <div class="cd-dt-grid">
          <div class="cd-dt-cell"><div class="l">Cuotas</div><div class="v">${cliente.cuotas_pagadas || 0}/${cliente.cuotas_total || 0}</div></div>
          <div class="cd-dt-cell"><div class="l">Cuota</div><div class="v">${cliente.monto_cuota ? 'USD ' + cliente.monto_cuota : '—'}</div></div>
          <div class="cd-dt-cell"><div class="l">Prox. venc.</div><div class="v">${cliente.proximo_vencimiento || '—'}</div></div>
          <div class="cd-dt-cell"><div class="l">Estado</div><div class="v">${cliente.estado_pago || '—'}</div></div>
        </div>
      ` : (estado === 'libre' || estado === 'free') ? `
        <div class="cd-ai-hint">
          <div class="cd-ai-hint-ico">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 21s-7-4.5-7-10a5 5 0 0 1 9-3 5 5 0 0 1 9 3c0 5.5-7 10-7 10"/></svg>
          </div>
          <div>
            <div class="cd-ai-hint-title">Sugerencia de Lovbot</div>
            <div class="cd-ai-hint-body">Este lote esta <b>libre</b>. Asignalo con "Nuevo contrato" o directamente desde Clientes Activos.</div>
          </div>
        </div>
      ` : ''}

      <div class="cd-dt-actions">${actions}</div>
    `;
    body.scrollTop = 0;
  }

  // ── Acciones sobre lotes y manzanas ────────────────────────────────────────

  window.confirmarBorrarLote = async function(loteId, label) {
    if (!confirm(`Eliminar lote ${label}? Solo se puede borrar si esta libre.`)) return;
    try {
      await crmFetch(`/crm/lotes-mapa/${loteId}/seguro`, { method: 'DELETE' });
      notif('Lote eliminado', label);
      LOTE_SELECCIONADO = null;
      renderDetailEmpty();
      await cargarGruposYRenderizar(LOTE_ACTUAL.id);
      // Refrescar contadores del loteo
      const data = await crmList('loteos');
      LOTEOS = data.items || LOTEOS;
      renderLoteos();
      const l = LOTEOS.find(x => x.id === LOTE_ACTUAL.id);
      if (l) LOTE_ACTUAL = l;
    } catch (e) {
      // 409 trae el mensaje en el body como detail de HTTPException
      const msg = e.message || '';
      const esBloqueado = msg.includes('409') || msg.toLowerCase().includes('vendido') || msg.toLowerCase().includes('reservado');
      notif(esBloqueado ? 'No se puede eliminar' : 'Error al eliminar', msg.replace(/^HTTP \d+: /, ''));
    }
  };

  window.renombrarManzanaPrompt = async function(nombreActual) {
    const nuevoNombre = prompt(`Nuevo nombre para manzana "${nombreActual}":`, nombreActual);
    if (!nuevoNombre || nuevoNombre.trim() === nombreActual) return;
    try {
      await crmFetch(`/crm/loteos/${LOTE_ACTUAL.id}/manzana/${encodeURIComponent(nombreActual)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nuevo_nombre: nuevoNombre.trim() }),
      });
      notif('Manzana renombrada', `${nombreActual} → ${nuevoNombre.trim()}`);
      await cargarGruposYRenderizar(LOTE_ACTUAL.id);
    } catch (e) {
      notif('Error al renombrar', e.message);
    }
  };

  window.eliminarManzana = async function(manzana) {
    if (!confirm(`Eliminar manzana "${manzana}" completa? Solo si todos sus lotes estan libres.`)) return;
    try {
      await crmFetch(`/crm/loteos/${LOTE_ACTUAL.id}/manzana/${encodeURIComponent(manzana)}`, {
        method: 'DELETE',
      });
      notif('Manzana eliminada', manzana);
      LOTE_SELECCIONADO = null;
      renderDetailEmpty();
      await cargarGruposYRenderizar(LOTE_ACTUAL.id);
      const data = await crmList('loteos');
      LOTEOS = data.items || LOTEOS;
      const l = LOTEOS.find(x => x.id === LOTE_ACTUAL.id);
      if (l) LOTE_ACTUAL = l;
      renderLoteos();
    } catch (e) {
      const msg = e.message || '';
      const esBloqueado = msg.includes('409') || msg.toLowerCase().includes('vendido') || msg.toLowerCase().includes('reservado');
      notif(esBloqueado ? 'No se puede eliminar manzana' : 'Error', msg.replace(/^HTTP \d+: /, ''));
    }
  };

  // ── Modal "Nueva manzana" ──────────────────────────────────────────────────

  window.abrirModalNuevaManzana = function() {
    if (!LOTE_ACTUAL) { notif('Selecciona un loteo primero'); return; }
    // Calcular siguiente numero de lote disponible
    const maxNro = GRUPOS_ACTUALES.reduce((max, g) => {
      g.lotes.forEach(l => {
        const n = parseInt(l.numero_lote) || 0;
        if (n > max) max = n;
      });
      return max;
    }, 0);
    document.getElementById('nuevaManzanaNombre').value = '';
    document.getElementById('nuevaManzanaCantidad').value = '8';
    document.getElementById('nuevaManzanaInicio').value = String(maxNro + 1);
    abrirModal('modalNuevaManzana');
  };

  window.guardarNuevaManzana = async function() {
    const nombre   = (document.getElementById('nuevaManzanaNombre').value  || '').trim();
    const cantidad = parseInt(document.getElementById('nuevaManzanaCantidad').value) || 8;
    const inicio   = parseInt(document.getElementById('nuevaManzanaInicio').value)   || 1;
    if (!nombre) { notif('Falta el nombre de la manzana'); return; }
    if (cantidad <= 0 || cantidad > 200) { notif('Cantidad debe ser entre 1 y 200'); return; }
    try {
      const res = await crmFetch(`/crm/loteos/${LOTE_ACTUAL.id}/manzana`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ manzana: nombre, cantidad, numero_lote_inicio: inicio }),
      });
      cerrarModal('modalNuevaManzana');
      notif(`Manzana ${nombre} creada`, `${res.creados || cantidad} lotes`);
      await cargarGruposYRenderizar(LOTE_ACTUAL.id);
      const data = await crmList('loteos');
      LOTEOS = data.items || LOTEOS;
      const l = LOTEOS.find(x => x.id === LOTE_ACTUAL.id);
      if (l) LOTE_ACTUAL = l;
      renderLoteos();
    } catch (e) {
      notif('Error creando manzana', e.message);
    }
  };

  // ── Modal "Agregar lote a manzana" ────────────────────────────────────────

  window.abrirModalAgregarLote = function(manzana) {
    if (!LOTE_ACTUAL) return;
    // Sugerir siguiente numero en esa manzana
    const grupo = GRUPOS_ACTUALES.find(g => g.manzana === manzana);
    let siguienteNro = 1;
    if (grupo && grupo.lotes.length > 0) {
      const maxEnMz = grupo.lotes.reduce((mx, l) => {
        const n = parseInt(l.numero_lote) || 0;
        return n > mx ? n : mx;
      }, 0);
      siguienteNro = maxEnMz + 1;
    }
    document.getElementById('agregarLoteManzana').value  = manzana;
    document.getElementById('agregarLoteNumero').value   = String(siguienteNro);
    document.getElementById('agregarLotePrecio').value   = '';
    abrirModal('modalAgregarLote');
  };

  window.guardarAgregarLote = async function() {
    const manzana = (document.getElementById('agregarLoteManzana').value || '').trim();
    const numero  = (document.getElementById('agregarLoteNumero').value  || '').trim();
    const precio  = document.getElementById('agregarLotePrecio').value.trim();
    if (!numero) { notif('Falta el numero del lote'); return; }
    const payload = {
      loteo_id: LOTE_ACTUAL.id,
      manzana,
      numero_lote: numero,
      estado: 'libre',
    };
    if (precio) payload.precio = parseFloat(precio);
    try {
      await crmFetch('/crm/lotes-mapa/seguro', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      cerrarModal('modalAgregarLote');
      notif(`Lote ${manzana}-${numero} creado`);
      await cargarGruposYRenderizar(LOTE_ACTUAL.id);
    } catch (e) {
      const msg = e.message || '';
      const esDuplicado = msg.includes('409') || msg.toLowerCase().includes('duplicado') || msg.toLowerCase().includes('ya existe');
      notif(esDuplicado ? 'Lote duplicado' : 'Error creando lote', msg.replace(/^HTTP \d+: /, ''));
    }
  };

  // ── Exportar CSV ──────────────────────────────────────────────────────────

  window.exportarLoteos = function() {
    if (!LOTEOS.length) { notif('Sin datos', 'No hay loteos para exportar'); return; }
    const rows = [['Loteo', 'Ciudad', 'Total lotes', 'Libres', 'Reservados', 'Vendidos', '% Ocupado']];
    LOTEOS.forEach(l => {
      const libres     = l.lotes_disponibles || 0;
      const reservados = l.lotes_reservados  || 0;
      const vendidos   = l.lotes_vendidos    || 0;
      const total      = libres + reservados + vendidos || l.total_lotes || 0;
      const pct = total > 0 ? Math.round(((reservados + vendidos) / total) * 100) : 0;
      rows.push([l.nombre, l.ciudad || '', total, libres, reservados, vendidos, pct + '%']);
    });
    const csv  = rows.map(r => r.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url; a.download = `loteos-${new Date().toISOString().slice(0,10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    notif('Exportado', `${LOTEOS.length} loteos a CSV`);
  };

  // ── Modal crear/editar datos del loteo ────────────────────────────────────

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

  window.guardarLoteo = async function() {
    const id     = document.getElementById('loteoId').value;
    const nombre = document.getElementById('loteoNombre').value.trim();
    const total  = parseInt(document.getElementById('loteoTotal').value) || 0;
    if (!nombre) { notif('Falta el nombre del loteo'); return; }
    const slugActual = document.getElementById('loteoSlug').value.trim();
    const campos = {
      nombre,
      slug: slugActual || nombre.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, ''),
      total_lotes: total,
      ciudad:      document.getElementById('loteoCiudad').value.trim(),
      ubicacion:   document.getElementById('loteoUbicacion').value.trim(),
      descripcion: document.getElementById('loteoDescripcion').value.trim(),
    };
    try {
      if (id) await crmUpdate('loteos', id, campos);
      else    await crmCreate('loteos', campos);
      cerrarModal('modalLoteo');
      notif('Loteo guardado', campos.nombre);
      await cargarLoteos();
      if (LOTE_ACTUAL && id && Number(id) === LOTE_ACTUAL.id) {
        setTimeout(() => seleccionarLoteo(LOTE_ACTUAL.id), 300);
      }
    } catch (e) { notif('Error', e.message); }
  };

  window.guardarYCargarLotes = async function() {
    await guardarLoteo();
  };

  window.eliminarLoteo = async function(id) {
    if (!confirm('Eliminar este loteo? No afecta a los clientes activos asignados.')) return;
    try {
      await crmDelete('loteos', id);
      notif('Loteo eliminado');
      cargarLoteos();
    } catch (e) { notif('Error', e.message); }
  };

  // ── Modal de mapa legacy (modalMapa) ─────────────────────────────────────
  // Se mantiene para compatibilidad con verMapaLoteo() si se invoca desde otro lugar.
  // Ahora renderiza con la misma logica granular.

  window.verMapaLoteo = async function(loteoId) {
    const loteo = LOTEOS.find(l => l.id === loteoId);
    if (!loteo) return;
    LOTE_ACTUAL = loteo;
    window.LOTE_MAPA_ACTUAL = loteo;
    try {
      const [data, clientesData] = await Promise.all([
        crmFetch(`/crm/loteos/${loteoId}/lotes`),
        crmFetch('/crm/clientes'),
      ]);
      GRUPOS_ACTUALES = data.grupos || [];
      CLIENTES_CACHE  = clientesData.items || clientesData.records || [];
    } catch (e) { /* fallback: grupos vacios */ GRUPOS_ACTUALES = []; }
    renderMapaLoteo();
    abrirModal('modalMapa');
  };

  function renderMapaLoteo() {
    const loteo = LOTE_ACTUAL;
    const clientesPorLote = indexarClientesPorLote(loteo.nombre);
    const { libres, reservados, vendidos } = contarEstadosGrupos(GRUPOS_ACTUALES, clientesPorLote);
    const total = libres + reservados + vendidos;

    document.getElementById('mapaTitulo').textContent = `Mapa de ${loteo.nombre}`;
    const ubic = loteo.ubicacion || loteo.ciudad || '';
    const ubicLabel = esUrlMaps(ubic)
      ? `<a href="${ubic}" target="_blank" style="color:var(--accent)">Ver en Google Maps</a>`
      : (ubic || 'Sin ubicacion');
    document.getElementById('mapaSubtitulo').innerHTML = `${total} lotes · ${ubicLabel}`;

    const manzanasHtml = GRUPOS_ACTUALES.map((g, idx) => {
      const mz = g.manzana;
      const lotes = g.lotes || [];
      const colsManzana = lotes.length <= 4 ? lotes.length : Math.ceil(lotes.length / 2);
      return `
        <div style="position:relative;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:10px;padding:14px 12px 10px">
          <div style="position:absolute;top:-10px;left:14px;background:var(--surface);color:var(--text2);font-size:10px;font-weight:700;padding:2px 10px;border-radius:10px;border:1px solid var(--brd)">MANZANA ${mz}</div>
          <div style="display:grid;gap:6px;grid-template-columns:repeat(${colsManzana},minmax(48px,70px));justify-content:center;margin-top:6px">
            ${lotes.map(l => renderLoteTarjetaModal(l, clientesPorLote)).join('')}
          </div>
        </div>`;
    }).join('');

    const cont = document.getElementById('mapaContenido');
    cont.innerHTML = `
      <div style="display:flex;gap:16px;font-size:12px;margin-bottom:16px;flex-wrap:wrap;align-items:center;padding:10px 14px;background:var(--surface2);border-radius:10px">
        <span style="display:flex;align-items:center;gap:8px">
          <span style="color:#86efac;font-weight:700">${libres}</span>Libres
        </span>
        <span style="display:flex;align-items:center;gap:8px">
          <span style="color:#fde047;font-weight:700">${reservados}</span>Reservados
        </span>
        <span style="display:flex;align-items:center;gap:8px">
          <span style="color:#fca5a5;font-weight:700">${vendidos}</span>Vendidos
        </span>
      </div>
      <div style="position:relative;background:linear-gradient(135deg,#0f1f14 0%,#0a1410 100%);border:1px solid rgba(134,239,172,0.15);border-radius:14px;padding:24px;overflow:auto;max-height:68vh">
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:24px">
          ${manzanasHtml}
        </div>
      </div>`;
  }

  function renderLoteTarjetaModal(lote, clientesPorLote) {
    const estado = _estadoEfectivo(lote, clientesPorLote);
    const asignado = clientesPorLote[String(lote.numero_lote)];
    const base = 'position:relative;aspect-ratio:1;border-radius:6px;display:flex;flex-direction:column;align-items:center;justify-content:center;cursor:pointer;transition:all 0.2s;font-weight:700;padding:4px;color:#fff;font-size:11px;line-height:1;box-shadow:0 2px 4px rgba(0,0,0,0.2);overflow:hidden';
    const hover = 'onmouseover="this.style.transform=\'scale(1.08)\';this.style.zIndex=\'10\'" onmouseout="this.style.transform=\'scale(1)\';this.style.zIndex=\'1\'"';
    const label = lote.numero_lote;

    if (estado === 'vendido') {
      const cliente = asignado ? asignado.cliente : (lote.cliente_id ? CLIENTES_CACHE.find(c => c.id === lote.cliente_id) : null);
      const nombre  = cliente ? `${cliente.nombre || ''} ${cliente.apellido || ''}`.trim() : 'Cliente';
      const clickAction = cliente ? `onclick="verInfoClienteLote(${cliente.id})"` : '';
      return `<button ${clickAction} title="${label} — ${nombre}" style="${base};background:linear-gradient(135deg,#dc2626 0%,#991b1b 100%);border:1.5px solid #fca5a5" ${hover}>
        <span style="font-size:13px;margin-bottom:2px">🏡</span>
        <span style="font-size:10px;font-weight:800">${label}</span>
      </button>`;
    } else if (estado === 'reservado') {
      return `<button title="${label} — reservado" style="${base};background:linear-gradient(135deg,#eab308 0%,#a16207 100%);border:1.5px solid #fde047" ${hover}>
        <span style="font-size:13px;margin-bottom:2px">⏳</span>
        <span style="font-size:10px;font-weight:800">${label}</span>
      </button>`;
    } else {
      return `<button title="${label} — disponible" style="${base};background:linear-gradient(135deg,#22c55e 0%,#15803d 100%);border:1.5px solid #86efac" ${hover}>
        <span style="font-size:13px;margin-bottom:2px">🌳</span>
        <span style="font-size:10px;font-weight:800">${label}</span>
      </button>`;
    }
  }

  // ── Modal info del cliente (solo lectura) ─────────────────────────────────

  window.verInfoClienteLote = function(clienteId) {
    const c = CLIENTES_CACHE.find(x => x.id === clienteId);
    if (!c) return;
    const pct    = c.cuotas_total > 0 ? Math.round((c.cuotas_pagadas / c.cuotas_total) * 100) : 0;
    const nombre = `${c.nombre || ''} ${c.apellido || ''}`.trim() || 'Cliente';
    document.getElementById('loteTitulo').textContent    = `Cliente: ${nombre}`;
    document.getElementById('loteSubtitulo').textContent = c.propiedad || '';
    document.getElementById('loteClienteInfoContent').innerHTML = `
      ${c.telefono ? `<div style="margin-bottom:6px">Tel: ${c.telefono}</div>` : ''}
      ${c.email    ? `<div style="margin-bottom:6px">Email: ${c.email}</div>`  : ''}
      <div style="margin-top:12px;display:grid;grid-template-columns:1fr 1fr;gap:10px">
        <div><div style="font-size:11px;color:var(--text2)">Estado de pago</div><div style="font-weight:600;margin-top:2px">${c.estado_pago || 'al_dia'}</div></div>
        <div><div style="font-size:11px;color:var(--text2)">Cuotas</div><div style="font-weight:600;margin-top:2px">${c.cuotas_pagadas || 0}/${c.cuotas_total || 0} (${pct}%)</div></div>
        ${c.monto_cuota ? `<div><div style="font-size:11px;color:var(--text2)">Cuota</div><div style="font-weight:600;margin-top:2px">$${c.monto_cuota}</div></div>` : ''}
        ${c.proximo_vencimiento ? `<div><div style="font-size:11px;color:var(--text2)">Proximo vencimiento</div><div style="font-weight:600;margin-top:2px">${c.proximo_vencimiento}</div></div>` : ''}
      </div>
      ${c.notas ? `<div style="margin-top:12px;padding:10px;background:var(--surface2);border-radius:6px;font-size:12px"><strong>Notas:</strong> ${c.notas}</div>` : ''}
    `;
    abrirModal('modalLote');
  };

})();
