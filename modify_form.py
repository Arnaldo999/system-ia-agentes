import re

path = '/home/arna/PROYECTO PROPIO ARNALDO AUTOMATIZACION/INMOBILIARIA MAICOL/PRESENTACION/formulario-leads.html'

with open(path, 'r', encoding='utf-8') as f:
    html = f.read()

new_css = """    :root {
      --primary: #154D24;       /* Verde oscuro premium */
      --primary-dark: #0f3d1b;
      --primary-light: #216f38;
      --accent: #b8942e;        /* Dorado Inmobiliaria Back */
      --warm: #e8c96d;
      --dark: #111827;
      --card: #ffffff;
      --bg: #fdfdfc;            /* Casi blanco, crema super sutil */
      --border: #e5e7eb;
      --text: #1f2937;
      --text-muted: #6b7280;
      --success: #10b981;
      --danger: #ef4444;
    }

    body {
      font-family: 'Inter', sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      padding: 0 0 60px;
    }

    /* ── HERO ── */
    .hero {
      text-align: center;
      padding: 60px 20px 40px;
      position: relative;
    }
    .hero-logo {
      font-size: 2.5rem;
      margin-bottom: 12px;
      display: inline-block;
    }
    .hero h1 {
      font-size: clamp(1.8rem, 5vw, 2.8rem);
      font-weight: 800;
      line-height: 1.2;
      margin-bottom: 16px;
      color: var(--primary);
      letter-spacing: -0.02em;
    }
    .hero h1 span { color: var(--accent); }
    .hero p {
      font-size: 1.05rem;
      color: var(--text-muted);
      max-width: 520px;
      margin: 0 auto 28px;
    }
    .trust-badges {
      display: flex;
      justify-content: center;
      gap: 12px;
      flex-wrap: wrap;
      margin-bottom: 10px;
    }
    .badge {
      display: flex;
      align-items: center;
      gap: 8px;
      background: #ffffff;
      border: 1px solid var(--border);
      border-radius: 30px;
      padding: 6px 16px;
      font-size: 0.8rem;
      font-weight: 600;
      color: var(--primary);
      box-shadow: 0 2px 8px rgba(0,0,0,0.02);
    }
    .badge .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--accent); }

    /* ── STEPPER ── */
    .stepper {
      display: flex;
      justify-content: center;
      align-items: center;
      gap: 0;
      max-width: 480px;
      margin: 0 auto 40px;
      padding: 0 20px;
    }
    .step-item {
      display: flex;
      flex-direction: column;
      align-items: center;
      flex: 1;
      position: relative;
    }
    .step-item:not(:last-child)::after {
      content: '';
      position: absolute;
      top: 18px;
      left: 50%;
      width: 100%;
      height: 3px;
      background: var(--border);
      z-index: 0;
      border-radius: 3px;
    }
    .step-item.active:not(:last-child)::after,
    .step-item.done:not(:last-child)::after {
      background: var(--primary);
    }
    .step-circle {
      width: 36px;
      height: 36px;
      border-radius: 50%;
      background: #ffffff;
      border: 2px solid var(--border);
      color: var(--text-muted);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 0.85rem;
      font-weight: 700;
      position: relative;
      z-index: 1;
      transition: all 0.3s;
    }
    .step-item.active .step-circle {
      background: var(--primary);
      border-color: var(--primary);
      color: white;
      box-shadow: 0 0 0 5px rgba(21,77,36,0.15);
    }
    .step-item.done .step-circle {
      background: var(--accent);
      border-color: var(--accent);
      color: white;
    }
    .step-label {
      font-size: 0.75rem;
      color: var(--text-muted);
      margin-top: 8px;
      text-align: center;
      white-space: nowrap;
      font-weight: 500;
    }
    .step-item.active .step-label { color: var(--primary); font-weight: 700; }

    /* ── CARD ── */
    .form-card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 24px;
      max-width: 540px;
      margin: 0 auto;
      padding: 40px 36px;
      box-shadow: 0 20px 40px rgba(0,0,0,0.04);
    }

    /* ── STEPS ── */
    .form-step { display: none; }
    .form-step.active { display: block; animation: fadeIn 0.4s ease; }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }

    .step-title {
      font-size: 1.4rem;
      font-weight: 800;
      margin-bottom: 8px;
      color: var(--primary);
      letter-spacing: -0.01em;
    }
    .step-subtitle {
      font-size: 0.95rem;
      color: var(--text-muted);
      margin-bottom: 30px;
    }

    /* ── OPTION GRID ── */
    .option-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
      margin-bottom: 28px;
    }
    .option-grid.three { grid-template-columns: 1fr 1fr 1fr; }
    .option-grid.wide { grid-template-columns: 1fr; }

    .opt-btn {
      border: 2px solid var(--border);
      background: #ffffff;
      border-radius: 16px;
      padding: 24px 16px;
      cursor: pointer;
      text-align: center;
      transition: all 0.2s ease-in-out;
      color: var(--text);
      position: relative;
      overflow: hidden;
      box-shadow: 0 4px 6px rgba(0,0,0,0.02);
    }
    .opt-btn:hover {
      border-color: var(--accent);
      transform: translateY(-3px);
      box-shadow: 0 8px 15px rgba(0,0,0,0.05);
    }
    .opt-btn.selected {
      border-color: var(--primary);
      background: rgba(21,77,36,0.03);
      box-shadow: 0 0 0 2px var(--primary);
    }
    .opt-btn .opt-icon { font-size: 2.2rem; margin-bottom: 12px; display: block;}
    .opt-btn .opt-label { font-size: 1rem; font-weight: 700; color: var(--primary); }
    .opt-btn .opt-sub { font-size: 0.8rem; color: var(--text-muted); margin-top: 4px; }
    .opt-btn .check {
      position: absolute;
      top: 12px;
      right: 12px;
      width: 22px;
      height: 22px;
      border-radius: 50%;
      background: var(--primary);
      color: white;
      font-size: 0.8rem;
      display: none;
      align-items: center;
      justify-content: center;
    }
    .opt-btn.selected .check { display: flex; }

    /* ── RANGE SLIDER ── */
    .range-group { margin-bottom: 32px; }
    .range-label {
      display: flex;
      justify-content: space-between;
      font-size: 0.95rem;
      margin-bottom: 14px;
      color: var(--text-muted);
      font-weight: 500;
    }
    .range-label strong { color: var(--accent); font-size: 1.2rem; font-weight: 800;}
    input[type="range"] {
      width: 100%;
      accent-color: var(--primary);
      height: 6px;
      background: var(--border);
      border-radius: 4px;
      outline: none;
      -webkit-appearance: none;
    }
    input[type="range"]::-webkit-slider-thumb {
      -webkit-appearance: none;
      width: 20px;
      height: 20px;
      background: var(--primary);
      border-radius: 50%;
      cursor: pointer;
      box-shadow: 0 2px 6px rgba(0,0,0,0.2);
    }
    .range-hints {
      display: flex;
      justify-content: space-between;
      font-size: 0.8rem;
      color: var(--text-muted);
      margin-top: 10px;
    }

    /* ── FORM FIELDS ── */
    .field-group { margin-bottom: 22px; }
    .field-group label {
      display: block;
      font-size: 0.85rem;
      font-weight: 700;
      color: var(--primary);
      margin-bottom: 8px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }
    .field-group input,
    .field-group select,
    .field-group textarea {
      width: 100%;
      background: #f9fafb;
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 16px 20px;
      color: var(--text);
      font-size: 1rem;
      font-family: inherit;
      transition: all 0.2s;
      outline: none;
    }
    .field-group input:focus,
    .field-group select:focus,
    .field-group textarea:focus {
      border-color: var(--primary);
      background: #ffffff;
      box-shadow: 0 0 0 4px rgba(21,77,36,0.08);
    }
    .field-group input.error { border-color: var(--danger); box-shadow: 0 0 0 4px rgba(239, 68, 68, 0.1); }
    .field-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }

    /* ── BOTONES ── */
    .btn-row {
      display: flex;
      gap: 12px;
      margin-top: 16px;
    }
    .btn-back {
      background: #f3f4f6;
      border: none;
      color: var(--text-muted);
      border-radius: 12px;
      padding: 16px 24px;
      font-size: 0.95rem;
      font-weight: 600;
      cursor: pointer;
      font-family: inherit;
      transition: all 0.2s;
    }
    .btn-back:hover { background: #e5e7eb; color: var(--text); transform: translateY(-2px);}
    .btn-next {
      flex: 1;
      background: var(--primary);
      border: none;
      color: white;
      border-radius: 12px;
      padding: 16px 24px;
      font-size: 1rem;
      font-weight: 700;
      cursor: pointer;
      font-family: inherit;
      transition: all 0.2s;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      box-shadow: 0 4px 12px rgba(21,77,36,0.2);
    }
    .btn-next:hover { background: var(--primary-light); transform: translateY(-2px); box-shadow: 0 6px 16px rgba(21,77,36,0.3); }
    .btn-next.accent { background: var(--accent); color: #ffffff; box-shadow: 0 4px 12px rgba(184,148,46,0.3); }
    .btn-next.accent:hover { background: #9e7f27; box-shadow: 0 6px 16px rgba(184,148,46,0.4); }
    .btn-next:disabled { opacity: 0.5; cursor: not-allowed; transform: none; box-shadow: none;}

    /* ── PROGRESS BAR ── */
    .progress-bar {
      height: 6px;
      background: #f3f4f6;
      border-radius: 10px;
      margin-bottom: 32px;
      overflow: hidden;
    }
    .progress-fill {
      height: 100%;
      background: linear-gradient(90deg, var(--primary), var(--accent));
      border-radius: 10px;
      transition: width 0.4s ease;
    }

    /* ── CHIPS ── */
    .chips { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 30px; }
    .chip {
      border: 1px solid var(--border);
      background: #f9fafb;
      border-radius: 30px;
      padding: 10px 20px;
      font-size: 0.9rem;
      font-weight: 500;
      cursor: pointer;
      color: var(--text-muted);
      font-family: inherit;
      transition: all 0.2s;
      box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }
    .chip:hover { border-color: var(--accent); color: var(--primary); }
    .chip.selected {
      border-color: var(--primary);
      background: rgba(21,77,36,0.05);
      color: var(--primary);
      font-weight: 700;
      box-shadow: 0 0 0 2px var(--primary);
    }

    /* ── RESULTADO ── */
    .result-screen { text-align: center; padding: 30px 0; }
    .result-icon {
      font-size: 4rem;
      margin-bottom: 20px;
      display: block;
      animation: popIn 0.5s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    }
    @keyframes popIn { 0% { transform: scale(0.5); opacity: 0; } 100% { transform: scale(1); opacity: 1; } }
    .result-screen h2 { font-size: 1.8rem; font-weight: 800; margin-bottom: 12px; color: var(--primary); letter-spacing: -0.02em;}
    .result-screen p { color: var(--text-muted); font-size: 1rem; margin-bottom: 32px; line-height: 1.6; }

    .cta-wa {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 10px;
      background: #25d366;
      color: white;
      border-radius: 16px;
      padding: 18px 28px;
      font-size: 1.1rem;
      font-weight: 700;
      text-decoration: none;
      margin-bottom: 16px;
      transition: all 0.2s;
      box-shadow: 0 6px 20px rgba(37,211,102,0.3);
    }
    .cta-wa:hover { background: #1ebe5d; transform: translateY(-3px); box-shadow: 0 10px 25px rgba(37,211,102,0.4); }
    .cta-ig {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 10px;
      background: linear-gradient(135deg, #833ab4, #fd1d1d, #fcb045);
      color: white;
      border-radius: 16px;
      padding: 16px 28px;
      font-size: 1rem;
      font-weight: 600;
      text-decoration: none;
      margin-bottom: 16px;
      transition: all 0.2s;
      box-shadow: 0 6px 20px rgba(253,29,29,0.2);
    }
    .cta-ig:hover { transform: translateY(-3px); box-shadow: 0 10px 25px rgba(253,29,29,0.3); }

    .result-note {
      font-size: 0.85rem;
      color: var(--text-muted);
      margin-top: 12px;
      line-height: 1.5;
    }

    /* ── MOBILE ── */
    @media (max-width: 480px) {
      .hero { padding: 40px 16px 20px; }
      .form-card { padding: 32px 20px; border-radius: 20px; margin: 0 16px; }
      .option-grid { grid-template-columns: 1fr; }
      .option-grid.three { grid-template-columns: 1fr; }
      .field-grid { grid-template-columns: 1fr; }
      .stepper { padding: 0 10px; margin-bottom: 30px; } 
    }"""

html = re.sub(r'    :root \{.*    @media \(max-width: 480px\) \{[^\}]*\}\s*\}', new_css, html, flags=re.DOTALL)

# Add accent to submit button
html = html.replace('class="btn-next" id="btn-submit"', 'class="btn-next accent" id="btn-submit"')
html = html.replace('<div class="hero-logo">🏠</div>', '<div class="hero-logo">🏢</div>')

with open(path, 'w', encoding='utf-8') as f:
    f.write(html)

print("CSS updated successfully!")
