import re

path = '/home/arna/PROYECTO PROPIO ARNALDO AUTOMATIZACION/INMOBILIARIA MAICOL/PRESENTACION/dashboard-crm.html'

with open(path, 'r', encoding='utf-8') as f:
    html = f.read()

# CSS Enhancements
new_css = """    :root {
      --primary: #154D24;       /* Verde oscuro premium */
      --primary-dark: #0f3d1b;
      --primary-light: #216f38;
      --accent: #b8942e;        /* Dorado Inmobiliaria Back */
      --warm: #e8c96d;
      --dark: #1f2937;
      --card: #ffffff;
      --bg: #f5f7fa;            /* Gris re suave moderno */
      --border: #e5e7eb;
      --text: #111827;          /* Casi negro, premium */
      --muted: #6b7280;
      --success: #10b981;
      --danger: #ef4444;
      --reservado: #f59e0b;
    }

    /* Forzar fondo aunque WordPress sobreescriba body */
    html, body,
    .site, .site-content, .entry-content,
    .wp-site-blocks, main, article, .page,
    #page, #content, #primary, #main {
      background: var(--bg) !important;
      background-color: var(--bg) !important;
    }
    body, html {
      font-family: 'Inter', sans-serif;
      background: var(--bg) !important;
      color: var(--text);
      min-height: 100vh;
      padding: 0 24px 24px 24px !important;
      margin-top: 0 !important;
    }
    /* Eliminar espacio superior de WordPress */
    .entry-content, .site-content, .wp-site-blocks,
    main, article, .page, #page, #content, #primary, #main {
      padding-top: 0 !important;
      margin-top: 0 !important;
    }

    /* ── HEADER ── */
    .header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 32px;
      flex-wrap: wrap;
      gap: 16px;
      background: rgba(255, 255, 255, 0.7);
      backdrop-filter: blur(12px);
      border-radius: 20px;
      padding: 24px 30px;
      border: 1px solid rgba(255, 255, 255, 0.6);
      box-shadow: 0 4px 30px rgba(0, 0, 0, 0.03);
      margin-top: 0;
    }
    .header-left h1 { font-size: 1.8rem; font-weight: 800; color: var(--primary) !important; letter-spacing: -0.02em; }
    .header-left p { color: var(--muted) !important; font-size: 0.9rem; margin-top: 4px; font-weight: 400; }
    /* Forzar colores de texto contra tema WordPress */
    body, html, body *, html * { color: inherit; }
    .container, .container * { color: var(--text); }
    .header-actions { display: flex; gap: 10px; flex-wrap: wrap; }
    .btn {
      border: none;
      padding: 12px 20px;
      border-radius: 12px;
      cursor: pointer;
      font-size: 0.9rem;
      font-weight: 600;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
      box-shadow: 0 2px 10px rgba(0,0,0,0.05);
    }
    .btn:active { transform: scale(0.97); }
    .btn-primary { background: var(--primary); color: white; }
    .btn-primary:hover { background: var(--primary-light); box-shadow: 0 4px 15px rgba(21, 77, 36, 0.2); transform: translateY(-2px); }
    .btn-success { background: var(--accent); color: white; }
    .btn-success:hover { background: #9e7f27; box-shadow: 0 4px 15px rgba(184, 148, 46, 0.2); transform: translateY(-2px); }
    .btn-outline { background: #ffffff; color: var(--text); border: 1px solid var(--border); }
    .btn-outline:hover { border-color: var(--primary); color: var(--primary); transform: translateY(-2px); box-shadow: 0 4px 15px rgba(0,0,0,0.04); }
    .header .btn-success { background: var(--accent); color: #ffffff; }
    .btn-danger { background: var(--danger); color: white; }
    .btn-danger:hover { background: #dc2626; transform: translateY(-2px); box-shadow: 0 4px 15px rgba(239, 68, 68, 0.2); }
    .btn-sm { padding: 8px 14px; font-size: 0.8rem; border-radius: 8px; }
    .btn.loading { opacity: 0.6; pointer-events: none; }

    /* ── TABS ── */
    .tabs {
      display: flex;
      gap: 10px;
      margin-bottom: 28px;
      border-bottom: 2px solid var(--border);
      padding-bottom: 0;
    }
    .tab {
      padding: 12px 24px;
      cursor: pointer;
      border-radius: 12px 12px 0 0;
      font-size: 0.95rem;
      font-weight: 600;
      color: var(--muted);
      border: 2px solid transparent;
      border-bottom: none;
      transition: all 0.3s ease;
      margin-bottom: -2px;
    }
    .tab.active {
      background: var(--card);
      color: var(--primary);
      border-color: var(--border);
      border-bottom-color: var(--card);
    }
    .tab:hover:not(.active) { color: var(--text); background: rgba(0,0,0,0.02); }

    /* ── STAT CARDS ── */
    .stats-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 20px;
      margin-bottom: 32px;
    }
    .stat-card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 24px;
      text-align: center;
      transition: transform 0.3s ease, box-shadow 0.3s ease;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.03);
    }
    .stat-card:hover { align-items: center; transform: translateY(-5px); box-shadow: 0 10px 30px rgba(0, 0, 0, 0.06); }
    .stat-card .num { font-size: 2.4rem; font-weight: 800; margin-bottom: 6px; letter-spacing: -0.03em; }
    .stat-card .lbl { font-size: 0.8rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.1em; font-weight: 600;}
    .stat-card.green .num { color: var(--primary); }
    .stat-card.blue .num { color: #3b82f6; }
    .stat-card.yellow .num { color: var(--accent); }
    .stat-card.red .num { color: var(--danger); }

    /* ── FILTROS ── */
    .filters {
      display: flex !important;
      flex-direction: row !important;
      gap: 12px !important;
      margin-bottom: 24px;
      flex-wrap: wrap;
      align-items: center;
    }
    .filter-chip {
      background: #ffffff !important;
      border: 1px solid var(--border) !important;
      color: var(--text) !important;
      padding: 10px 18px !important;
      border-radius: 30px !important;
      font-size: 0.85rem !important;
      font-weight: 600 !important;
      cursor: pointer;
      outline: none;
      transition: all 0.2s;
      white-space: nowrap;
      font-family: 'Inter', sans-serif;
      box-shadow: 0 2px 8px rgba(0,0,0,0.02) !important;
      appearance: none !important;
      -webkit-appearance: none !important;
      background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6'%3E%3Cpath d='M0 0l5 6 5-6z' fill='%236b7280'/%3E%3C/svg%3E") !important;
      background-repeat: no-repeat !important;
      background-position: right 14px center !important;
      padding-right: 36px !important;
      width: auto !important;
      max-width: fit-content !important;
      flex: 0 0 auto !important;
      display: inline-block !important;
    }
    .filter-chip:hover, .filter-chip:focus { border-color: var(--primary) !important; color: var(--primary) !important; box-shadow: 0 4px 12px rgba(0,0,0,0.05) !important;}
    .filters input.filter-chip {
      background-image: none !important;
      padding-right: 18px !important;
      min-width: 240px;
    }
    .filter-count { color: var(--muted); font-size: 0.85rem; margin-left: auto; font-weight: 500; }

    /* ── TABLE ── */
    .table-wrap {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 16px;
      overflow: hidden;
      box-shadow: 0 4px 20px rgba(0,0,0,0.03);
    }
    table { width: 100%; border-collapse: collapse; }
    thead { background: #f9fafb; border-bottom: 2px solid var(--border); }
    th {
      padding: 16px 20px;
      text-align: left;
      font-size: 0.78rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
      font-weight: 700;
    }
    td {
      padding: 14px 20px;
      font-size: 0.9rem;
      border-top: 1px solid var(--border);
      vertical-align: middle;
      color: var(--text);
    }
    tr:hover td { background: #fdfdfd; }

    /* ── BADGES ── */
    .badge {
      display: inline-block;
      padding: 4px 12px;
      border-radius: 20px;
      font-size: 0.75rem;
      font-weight: 700;
      letter-spacing: 0.02em;
    }
    .badge-disponible { background: rgba(16,185,129,0.1); color: #059669; border: 1px solid rgba(16,185,129,0.2); }
    .badge-reservado  { background: rgba(245,158,11,0.1);  color: #d97706; border: 1px solid rgba(245,158,11,0.2); }
    .badge-no        { background: rgba(239,68,68,0.1);   color: #dc2626; border: 1px solid rgba(239,68,68,0.2); }
    .badge-venta     { background: rgba(79,70,229,0.1);  color: #4f46e5; border: 1px solid rgba(79,70,229,0.2); }
    .badge-alquiler  { background: rgba(6,182,212,0.1);   color: #0891b2; border: 1px solid rgba(6,182,212,0.2); }
    .badge-no_contactado  { background: rgba(156,163,175,0.1); color: #4b5563; border: 1px solid rgba(156,163,175,0.2); }
    .badge-contactado     { background: rgba(16,185,129,0.1);  color: #059669; border: 1px solid rgba(16,185,129,0.2); }
    .badge-en_negociacion { background: rgba(245,158,11,0.1);  color: #d97706; border: 1px solid rgba(245,158,11,0.2); }
    .badge-cerrado        { background: rgba(79,70,229,0.1);  color: #4f46e5; border: 1px solid rgba(79,70,229,0.2); }
    .badge-descartado     { background: rgba(239,68,68,0.1);   color: #dc2626; border: 1px solid rgba(239,68,68,0.2); }

    /* ── LEAD CARDS ── */
    .leads-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 20px;
    }
    .lead-card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 24px;
      transition: all 0.3s ease;
      box-shadow: 0 4px 15px rgba(0,0,0,0.02);
    }
    .lead-card:hover { border-color: var(--primary); transform: translateY(-3px); box-shadow: 0 8px 25px rgba(0,0,0,0.05); }
    .lead-card .lead-name { font-size: 1.1rem; font-weight: 800; margin-bottom: 8px; color: var(--text); }
    .lead-card .lead-meta { font-size: 0.85rem; color: var(--muted); margin-bottom: 14px; display: flex; flex-direction: column; gap: 4px; }
    .lead-card .lead-tags { display: flex; gap: 8px; flex-wrap: wrap; }
    .lead-card .lead-notas { font-size: 0.85rem; color: var(--muted); margin-top: 14px; font-style: italic; border-top: 1px solid var(--border); padding-top: 12px; }
    .lead-whatsapp { display: inline-flex; align-items: center; gap: 6px; color: #10b981; font-size: 0.8rem; font-weight: 600; margin-top: 10px; }
    .lead-actions { display: flex; gap: 8px; margin-top: 16px; flex-wrap: wrap; }

    /* ── SECTION TITLE ── */
    .section-title {
      font-size: 1.2rem;
      font-weight: 800;
      margin-bottom: 20px;
      display: flex;
      align-items: center;
      gap: 10px;
      color: var(--text);
    }

    /* ── LOADING / EMPTY ── */
    .loading-msg, .empty-msg {
      text-align: center;
      padding: 60px;
      color: var(--muted);
      font-size: 1rem;
      font-weight: 500;
    }
    .spinner {
      display: inline-block;
      width: 24px; height: 24px;
      border: 3px solid var(--border);
      border-top-color: var(--primary);
      border-radius: 50%;
      animation: spin 0.7s linear infinite;
      vertical-align: middle;
      margin-right: 8px;
    }
    @keyframes spin { to { transform: rotate(360deg); } }

    /* ── GALERÍA ── */
    .gallery-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
      gap: 24px;
    }
    .gallery-card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 18px;
      overflow: hidden;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      box-shadow: 0 4px 15px rgba(0,0,0,0.03);
      display: flex;
      flex-direction: column;
    }
    .gallery-card:hover { transform: translateY(-6px); border-color: var(--primary); box-shadow: 0 14px 30px rgba(0,0,0,0.08); }
    .gallery-img {
      width: 100%;
      height: 200px;
      object-fit: cover;
      display: block;
      background: #f3f4f6;
      border-bottom: 1px solid var(--border);
    }
    .gallery-img-placeholder {
      width: 100%;
      height: 200px;
      background: #f3f4f6;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 3rem;
      color: #9ca3af;
      border-bottom: 1px solid var(--border);
    }
    .gallery-body { padding: 20px; flex-grow: 1; display: flex; flex-direction: column;}
    .gallery-title { font-weight: 800; font-size: 1.05rem; margin-bottom: 8px; line-height: 1.4; color: var(--text);}
    .gallery-meta { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 12px; }
    .gallery-price { font-size: 1.2rem; font-weight: 800; color: var(--accent); margin-bottom: 4px; }
    .gallery-zona { font-size: 0.85rem; color: var(--muted); margin-top: 4px; font-weight: 500;}
    .gallery-img-wrap { position: relative; }
    .gallery-actions { display: flex; gap: 8px; margin-top: auto; padding-top: 16px; border-top: 1px solid var(--border);}
    
    .price { font-weight: 800; color: var(--accent); }
    .zona-tag { font-size: 0.8rem; color: var(--muted); }

    /* ── MODAL ── */
    .modal-overlay {
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(17, 24, 39, 0.6);
      backdrop-filter: blur(4px);
      z-index: 1000;
      align-items: center;
      justify-content: center;
      padding: 20px;
      opacity: 0;
      transition: opacity 0.3s ease;
    }
    .modal-overlay.open { display: flex; opacity: 1; }
    .modal {
      background: #ffffff;
      border: 1px solid var(--border);
      border-radius: 20px;
      padding: 32px;
      width: 100%;
      max-width: 600px;
      max-height: 90vh;
      overflow-y: auto;
      position: relative;
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
      transform: scale(0.95);
      transition: transform 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    }
    .modal-overlay.open .modal { transform: scale(1); }
    .modal-title {
      font-size: 1.3rem;
      font-weight: 800;
      margin-bottom: 24px;
      padding-right: 30px;
      color: var(--primary);
    }
    .modal-close {
      position: absolute;
      top: 20px; right: 20px;
      background: #f3f4f6;
      border: none;
      color: var(--muted);
      width: 32px; height: 32px;
      border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      font-size: 1rem;
      cursor: pointer;
      transition: all 0.2s;
    }
    .modal-close:hover { background: #e5e7eb; color: var(--text); }
    .form-group { margin-bottom: 20px; }
    .form-group label { display: block; font-size: 0.85rem; color: var(--muted); margin-bottom: 8px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }
    .form-control {
      width: 100%;
      background: #f9fafb;
      border: 1px solid var(--border);
      color: var(--text);
      padding: 12px 16px;
      border-radius: 10px;
      font-size: 0.95rem;
      font-family: 'Inter', sans-serif;
      outline: none;
      transition: all 0.2s;
    }
    .form-control:focus { border-color: var(--primary); background: #ffffff; box-shadow: 0 0 0 3px rgba(21, 77, 36, 0.1); }
    .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    .modal-footer { display: flex; gap: 12px; justify-content: flex-end; margin-top: 28px; padding-top: 20px; border-top: 1px solid var(--border); }

    /* Imagen preview */
    .img-preview-wrap { position: relative; margin-bottom: 10px; }
    .img-preview { width: 100%; height: 160px; object-fit: cover; border-radius: 12px; border: 1px solid var(--border); display: none; }
    .img-placeholder { width: 100%; height: 100px; border: 2px dashed var(--border); border-radius: 12px; display: flex; align-items: center; justify-content: center; color: var(--muted); font-size: 0.9rem; cursor: pointer; transition: all 0.2s; font-weight: 500;}
    .img-placeholder:hover { border-color: var(--primary); color: var(--primary); background: rgba(21, 77, 36, 0.02);}

    /* Toast */
    .toast {
      position: fixed;
      bottom: 30px; right: 30px;
      background: #ffffff;
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 16px 24px;
      font-size: 0.95rem;
      font-weight: 500;
      z-index: 2000;
      box-shadow: 0 10px 25px rgba(0,0,0,0.1);
      display: flex;
      align-items: center;
      gap: 12px;
      transform: translateY(100px);
      opacity: 0;
      transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
      max-width: 350px;
    }
    .toast.show { transform: translateY(0); opacity: 1; }
    .toast.success { border-left: 4px solid var(--success); }
    .toast.error { border-left: 4px solid var(--danger); }

    /* Kanban mini */
    .estado-btn-group { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 12px; }
    .estado-btn {
      padding: 6px 14px;
      border-radius: 20px;
      font-size: 0.8rem;
      font-weight: 600;
      cursor: pointer;
      border: 1px solid transparent;
      transition: all 0.2s;
    }
    .estado-btn.active-no_contactado  { background: #f3f4f6; color: #4b5563; border-color: #d1d5db; }
    .estado-btn.active-contactado     { background: #ecfdf5;  color: #059669; border-color: #a7f3d0; }
    .estado-btn.active-en_negociacion { background: #fffbeb;  color: #d97706; border-color: #fde68a; }
    .estado-btn.active-cerrado        { background: #eef2ff;  color: #4f46e5; border-color: #c7d2fe; }
    .estado-btn.active-descartado     { background: #fef2f2;   color: #dc2626; border-color: #fca5a5; }
    .estado-btn.inactive { background: #f9fafb; color: var(--muted); border-color: #e5e7eb; }
    .estado-btn.inactive:hover { background: #e5e7eb; color: var(--text); }

    /* Responsive */
    @media (max-width: 768px) {
      body { padding: 16px !important; }
      .header { padding: 20px; }
      .header-left h1 { font-size: 1.4rem; }
      table thead { display: none; }
      td { display: block; padding: 10px 16px; border: none; }
      td::before { content: attr(data-label); font-weight: 700; color: var(--muted); margin-right: 12px; font-size: 0.8rem; text-transform: uppercase; }
      tr { border-top: 1px solid var(--border); display: block; padding: 12px 0; }
      .form-row { grid-template-columns: 1fr; }
    }

    .panel { display: none; }
    .panel.active { display: block; }"""

html = re.sub(r'    :root \{.*\.panel\.active \{ display: block; \}', new_css, html, flags=re.DOTALL)

# Add openModal function at the end of the script block
if 'function openModal(id)' not in html:
    new_script = """function closeModal(id) {
  document.getElementById(id).classList.remove('open');
}

function openModal(id) {
  document.getElementById(id).classList.add('open');
}"""
    html = re.sub(r"function closeModal\(id\) \{\s*document\.getElementById\(id\)\.classList\.remove\('open'\);\s*\}", new_script, html)
    print("Added openModal function!")
else:
    print("openModal already exists")

with open(path, 'w', encoding='utf-8') as f:
    f.write(html)

print("CSS and bugs updated successfully!")

