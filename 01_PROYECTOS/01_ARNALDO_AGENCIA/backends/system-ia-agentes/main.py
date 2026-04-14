import os
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

# ── Logging estructurado ──────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("system-ia")

# Registro global de errores en memoria (últimos 100)
_error_log: list[dict] = []

def registrar_error(endpoint: str, error: Exception, contexto: dict = {}):
    """Registra un error en el log interno y en stdout para Coolify/Render."""
    import traceback, datetime
    entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "endpoint": endpoint,
        "error": str(error),
        "tipo": type(error).__name__,
        "traceback": traceback.format_exc(),
        **contexto
    }
    _error_log.append(entry)
    if len(_error_log) > 100:
        _error_log.pop(0)
    logger.error(f"[{endpoint}] {type(error).__name__}: {error}")

# ── Clientes Arnaldo ──────────────────────────────────────────────────────────
from workers.clientes.arnaldo.maicol.worker import router as maicol_router
from workers.clientes.arnaldo.prueba.worker import router as prueba_router

# ── Clientes Lovbot ───────────────────────────────────────────────────────────
from workers.clientes.lovbot.robert_inmobiliaria.worker import router as robert_inmo_router
from workers.clientes.lovbot.robert_inmobiliaria.worker import _procesar as robert_inmo_procesar

# ── Demos ─────────────────────────────────────────────────────────────────────
from workers.demos.inmobiliaria.worker  import router as demo_inmobiliaria_router
from workers.demos.gastronomico.worker  import router as demo_gastronomico_router

# ── SaaS ──────────────────────────────────────────────────────────────────────
from workers.shared.tenants import router as tenants_router, crm_router, admin_router

# ── System IA — Clientes ──────────────────────────────────────────────────────
from workers.clientes.system_ia.lau.worker import router as lau_router
from workers.clientes.system_ia.demos.inmobiliaria.worker import router as mica_demo_inmo_router

# ── System IA ─────────────────────────────────────────────────────────────────
from workers.social.worker import router as social_router

app = FastAPI(
    title="System IA — Agentes",
    description=(
        "Backend de automatizaciones IA para la agencia System IA. "
        "Arquitectura: clientes/ (producción) · demos/ (presentaciones) · social/ (System IA)"
    ),
    version="3.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def middleware_deteccion_errores(request: Request, call_next):
    """Captura cualquier excepción no manejada y la registra."""
    import time
    start = time.time()
    try:
        response = await call_next(request)
        elapsed = round((time.time() - start) * 1000)
        if response.status_code >= 500:
            logger.warning(f"[{request.method}] {request.url.path} → {response.status_code} ({elapsed}ms)")
        return response
    except Exception as e:
        registrar_error(request.url.path, e, {"method": request.method})
        return PlainTextResponse(f"Error interno: {type(e).__name__}", status_code=500)

# ── Registrar routers ─────────────────────────────────────────────────────────
app.include_router(tenants_router)
app.include_router(crm_router)
app.include_router(admin_router)
app.include_router(maicol_router)
app.include_router(prueba_router)
app.include_router(robert_inmo_router)
app.include_router(demo_inmobiliaria_router)
app.include_router(demo_gastronomico_router)
app.include_router(lau_router)
app.include_router(mica_demo_inmo_router)
app.include_router(social_router)


# ── Meta Webhook — Tech Provider Robert/Lovbot ───────────────────────────────
_META_VERIFY_TOKEN = os.environ.get("META_VERIFY_TOKEN", "")
_META_MSG_IDS_PROCESADOS: set[str] = set()  # deduplicación de reintentos Meta

@app.get("/meta/webhook", tags=["Meta"])
async def meta_webhook_verify(request: Request):
    params = dict(request.query_params)
    if params.get("hub.verify_token") == _META_VERIFY_TOKEN:
        return PlainTextResponse(params.get("hub.challenge", ""))
    return PlainTextResponse("Token inválido", status_code=403)

@app.post("/meta/webhook", tags=["Meta"])
async def meta_webhook_events(request: Request):
    """Recibe eventos de Meta (WhatsApp) y los despacha al worker correcto."""
    import threading
    try:
        data = await request.json()
    except Exception:
        return {"status": "ignored"}

    _ROBERT_PHONE_ID = os.environ.get("META_PHONE_NUMBER_ID", "")

    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            phone_number_id = value.get("metadata", {}).get("phone_number_id", "")
            for msg in value.get("messages", []):
                msg_type = msg.get("type", "")
                # Aceptar text y button (Meta Ads envía button como primer mensaje)
                if msg_type == "text":
                    texto = msg.get("text", {}).get("body", "")
                elif msg_type == "button":
                    texto = msg.get("button", {}).get("text", "") or msg.get("button", {}).get("payload", "")
                else:
                    continue

                msg_id = msg.get("id", "")
                if msg_id and msg_id in _META_MSG_IDS_PROCESADOS:
                    print(f"[META-WEBHOOK] Duplicado ignorado: {msg_id}")
                    continue
                if msg_id:
                    _META_MSG_IDS_PROCESADOS.add(msg_id)
                    if len(_META_MSG_IDS_PROCESADOS) > 500:
                        _META_MSG_IDS_PROCESADOS.clear()

                telefono = msg.get("from", "")
                if not telefono or not texto:
                    continue

                # Extraer referral (origen del lead: Meta Ads, click-to-WhatsApp)
                referral = msg.get("referral", {})

                # Enrutar según phone_number_id
                if phone_number_id == _ROBERT_PHONE_ID:
                    threading.Thread(
                        target=robert_inmo_procesar,
                        args=(telefono, texto, referral), daemon=True
                    ).start()

    return {"status": "received"}


# ── Rutas de sistema ──────────────────────────────────────────────────────────
@app.get("/", tags=["Sistema"])
def root():
    """Mapa de endpoints activos."""
    return {
        "status": "online",
        "version": "3.0.0",
        "agencia": "System IA — Automatizaciones para LATAM",
        "clientes": {
            "arnaldo/maicol": [
                "POST /clientes/arnaldo/maicol/lead",
                "POST /clientes/arnaldo/maicol/whatsapp",
                "GET  /clientes/arnaldo/maicol/propiedades",
                "GET  /clientes/arnaldo/maicol/crm/propiedades",
                "GET  /clientes/arnaldo/maicol/crm/clientes",
            ],
        },
        "demos": {
            "inmobiliaria": [
                "POST /demos/inmobiliaria/lead",
                "POST /demos/inmobiliaria/whatsapp",
                "GET  /demos/inmobiliaria/propiedades",
                "GET  /demos/inmobiliaria/crm/propiedades",
                "GET  /demos/inmobiliaria/crm/clientes",
                "GET  /demos/inmobiliaria/config",
            ],
            "gastronomico": [
                "POST /demos/gastronomico/whatsapp",
                "POST /demos/gastronomico/mensaje",
                "GET  /demos/gastronomico/crm/reservas",
                "GET  /demos/gastronomico/crm/pedidos",
                "GET  /demos/gastronomico/crm/clientes",
                "GET  /demos/gastronomico/config",
                "POST /demos/gastronomico/difusion",
            ],
        },
        "system_ia": {
            "social": [
                "GET  /social/meta-webhook",
                "POST /social/meta-webhook",
            ],
        },
    }


@app.get("/debug/errors", tags=["Sistema"])
def debug_errors(limit: int = 20):
    """Últimos errores capturados por el middleware. Útil para monitoreo."""
    ultimos = _error_log[-limit:] if _error_log else []
    return {
        "total_errores": len(_error_log),
        "mostrando": len(ultimos),
        "errores": list(reversed(ultimos))  # más reciente primero
    }


@app.get("/health", tags=["Sistema"])
def health_check():
    """Health check para monitoreo de Easypanel/Coolify."""
    gemini_ok = bool(os.environ.get("GEMINI_API_KEY"))
    return {
        "status": "healthy",
        "gemini_api": "configured" if gemini_ok else "ERROR — falta GEMINI_API_KEY",
        "workers_activos": 6
    }


@app.get("/auditor/fase2", tags=["Sistema"])
async def auditor_fase2():
    """Ejecuta auditoría completa y retorna reporte estructurado + mensaje Telegram."""
    import sys, datetime, traceback
    scripts_dir = os.path.join(os.path.dirname(__file__), "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    from scripts import auditor_infra, auditor_workflows, auditor_ycloud
    from scripts import auditor_tokens, auditor_evolution, auditor_meta_provider, auditor_crm

    AUDITORES = [
        auditor_infra, auditor_workflows, auditor_ycloud,
        auditor_tokens, auditor_evolution, auditor_meta_provider, auditor_crm,
    ]
    TITULOS = {
        "infra": "🏗️ Infraestructura", "workflows": "📋 Workflows",
        "ycloud": "📡 YCloud", "tokens": "🔐 Tokens",
        "evolution": "💬 Evolution API", "meta": "🌐 Meta Tech Provider",
        "crm": "🗄️ CRM / Tenants",
    }

    fecha = datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=-3))
    ).strftime("%d/%m/%Y %H:%M ARG")

    resultados = []
    for auditor in AUDITORES:
        nombre = getattr(auditor, "__name__", str(auditor)).split(".")[-1].replace("auditor_", "")
        try:
            resultado = auditor.run()
            resultados.append(resultado)
        except Exception as e:
            resultados.append({
                "auditor": nombre, "ok": False,
                "alertas": [], "error_runner": str(e),
            })

    total_alertas = sum(len(r["alertas"]) for r in resultados)

    # Armar mensaje Telegram
    lineas = [f"🔍 <b>AUDITORÍA DIARIA</b> — {fecha}", ""]
    for r in resultados:
        titulo = TITULOS.get(r["auditor"], r["auditor"].upper())
        if r.get("error_runner"):
            lineas.append(f"{titulo}: ⚠️ error — {r['error_runner']}")
        elif r["ok"]:
            lineas.append(f"{titulo}: ✅ OK")
        else:
            lineas.append(f"{titulo}:")
            for a in r["alertas"]:
                nombre_a = a.get("nombre") or a.get("servicio") or "—"
                detalle = a.get("detalle", "")
                inst = f" [{a['instancia']}]" if "instancia" in a else ""
                lineas.append(f"  ⚠️ {nombre_a}{inst} — {detalle}")

    lineas.append("")
    if total_alertas == 0:
        lineas.append("✅ <b>Todo OK</b> — sin alertas")
    else:
        lineas.append(f"⚠️ <b>{total_alertas} alerta{'s' if total_alertas != 1 else ''}</b> — revisá el panel")

    mensaje = "\n".join(lineas)

    # Enviar a Telegram directamente
    import requests as req
    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    tg_chat = os.environ.get("TELEGRAM_CHAT_ID", "")
    telegram_enviado = False
    if tg_token and tg_chat:
        try:
            req.post(
                f"https://api.telegram.org/bot{tg_token}/sendMessage",
                json={"chat_id": tg_chat, "text": mensaje, "parse_mode": "HTML"},
                timeout=10,
            )
            telegram_enviado = True
        except Exception as e:
            logger.error(f"[auditor/fase2] Error enviando Telegram: {e}")

    return {
        "fecha": fecha,
        "total_alertas": total_alertas,
        "telegram_enviado": telegram_enviado,
        "mensaje_telegram": mensaje,
        "resultados": resultados,
    }


@app.get("/admin/reset-propiedades", tags=["Admin"])
async def admin_reset_propiedades():
    """Borra TODAS las propiedades del tenant demo (para re-migrar limpio)."""
    import psycopg2
    PG_HOST = os.environ.get("LOVBOT_PG_HOST", "")
    PG_PORT = os.environ.get("LOVBOT_PG_PORT", "5432")
    PG_DB = os.environ.get("LOVBOT_PG_DB", "lovbot_crm")
    PG_USER = os.environ.get("LOVBOT_PG_USER", "lovbot")
    PG_PASS = os.environ.get("LOVBOT_PG_PASS", "")
    try:
        conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASS)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("DELETE FROM propiedades WHERE tenant_slug='demo'")
        eliminadas = cur.rowcount
        cur.close()
        conn.close()
        return {"ok": True, "propiedades_eliminadas": eliminadas}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/admin/limpiar-duplicados", tags=["Admin"])
async def admin_limpiar_duplicados():
    """Elimina propiedades y activos duplicados (deja el primero)."""
    import psycopg2
    PG_HOST = os.environ.get("LOVBOT_PG_HOST", "")
    PG_PORT = os.environ.get("LOVBOT_PG_PORT", "5432")
    PG_DB = os.environ.get("LOVBOT_PG_DB", "lovbot_crm")
    PG_USER = os.environ.get("LOVBOT_PG_USER", "lovbot")
    PG_PASS = os.environ.get("LOVBOT_PG_PASS", "")
    try:
        conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASS)
        conn.autocommit = True
        cur = conn.cursor()

        # Eliminar duplicados de propiedades (deja el ID más bajo)
        cur.execute("""
            DELETE FROM propiedades a USING propiedades b
            WHERE a.id > b.id
              AND a.tenant_slug = b.tenant_slug
              AND a.titulo = b.titulo
        """)
        props_eliminadas = cur.rowcount

        # Eliminar duplicados de activos
        cur.execute("""
            DELETE FROM clientes_activos a USING clientes_activos b
            WHERE a.id > b.id
              AND a.tenant_slug = b.tenant_slug
              AND a.telefono = b.telefono
        """)
        activos_eliminados = cur.rowcount

        cur.close()
        conn.close()
        return {"ok": True, "propiedades_eliminadas": props_eliminadas, "activos_eliminados": activos_eliminados}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/admin/migrar-airtable", tags=["Admin"])
async def admin_migrar_airtable():
    """Migra datos de Airtable a PostgreSQL (una sola vez)."""
    import sys
    scripts_dir = os.path.join(os.path.dirname(__file__), "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    try:
        from scripts.migrar_airtable_postgres import migrate
        migrate()
        return {"ok": True, "message": "Migración completada"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/admin/setup-postgres", tags=["Admin"])
async def admin_setup_postgres():
    """Ejecuta el setup de PostgreSQL para Lovbot CRM (una sola vez)."""
    import sys
    scripts_dir = os.path.join(os.path.dirname(__file__), "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    from scripts.setup_postgres_lovbot import setup
    return setup()


@app.get("/admin/setup-crm-completo", tags=["Admin"])
async def admin_setup_crm_completo():
    """Migración CRM multi-subnicho: agrega columnas + tablas asesores/propietarios/loteos/contratos/visitas. Idempotente."""
    import sys
    scripts_dir = os.path.join(os.path.dirname(__file__), "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    from scripts.setup_postgres_crm_completo import setup
    return setup()


@app.get("/admin/debug-pg", tags=["Admin"])
async def admin_debug_pg(db_name: str = "lovbot_crm", tenant: str = "robert"):
    """Debug: muestra count de leads en una DB específica. Temporal."""
    import psycopg2
    PG_HOST = os.environ.get("LOVBOT_PG_HOST", "lovbot-postgres-tkkk8owkg40ssoksk8ok4gsc")
    PG_PORT = os.environ.get("LOVBOT_PG_PORT", "5432")
    PG_USER = os.environ.get("LOVBOT_PG_USER", "lovbot")
    PG_PASS = os.environ.get("LOVBOT_PG_PASS", "")
    try:
        conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=db_name,
                                user=PG_USER, password=PG_PASS)
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM leads")
        total = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM leads WHERE tenant_slug=%s", (tenant,))
        del_tenant = cur.fetchone()[0]
        cur.execute("SELECT DISTINCT tenant_slug FROM leads")
        tenants = [r[0] for r in cur.fetchall()]
        cur.close()
        conn.close()
        return {
            "db": db_name,
            "host": PG_HOST,
            "total_leads": total,
            f"leads_tenant_{tenant}": del_tenant,
            "tenants_distintos": tenants,
        }
    except Exception as e:
        return {"error": str(e), "host": PG_HOST, "db": db_name}


@app.get("/admin/update-tenant-slug", tags=["Admin"])
async def admin_update_tenant_slug(from_tenant: str = "demo", to_tenant: str = "robert", db_name: str = "lovbot_crm"):
    """
    Actualiza tenant_slug en todas las tablas de una DB.
    
    Params:
        from_tenant: slug actual (default: demo)
        to_tenant: slug nuevo (default: robert)
        db_name: nombre de la DB (default: lovbot_crm)
    
    Ejemplo:
        GET /admin/update-tenant-slug?from_tenant=demo&to_tenant=robert
    """
    import psycopg2
    PG_HOST = os.environ.get("LOVBOT_PG_HOST", "lovbot-postgres-tkkk8owkg40ssoksk8ok4gsc")
    PG_PORT = os.environ.get("LOVBOT_PG_PORT", "5432")
    PG_USER = os.environ.get("LOVBOT_PG_USER", "lovbot")
    PG_PASS = os.environ.get("LOVBOT_PG_PASS", "")
    try:
        conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=db_name,
                                user=PG_USER, password=PG_PASS)
        cur = conn.cursor()
        
        # UPDATEs
        updates = [
            "UPDATE leads SET tenant_slug = %s WHERE tenant_slug = %s",
            "UPDATE propiedades SET tenant_slug = %s WHERE tenant_slug = %s",
            "UPDATE clientes_activos SET tenant_slug = %s WHERE tenant_slug = %s"
        ]
        
        results = {}
        for update_query in updates:
            cur.execute(update_query, (to_tenant, from_tenant))
            rows_affected = cur.rowcount
            table_name = update_query.split("UPDATE ")[1].split(" SET")[0]
            results[table_name] = rows_affected
        
        conn.commit()
        
        # Verificar con SELECTs
        verify = {}
        for table in ["leads", "propiedades", "clientes_activos"]:
            cur.execute(f"SELECT COUNT(*) FROM {table} WHERE tenant_slug = %s", (to_tenant,))
            verify[table] = cur.fetchone()[0]
        
        cur.close()
        conn.close()
        
        return {
            "status": "success",
            "db": db_name,
            "from_tenant": from_tenant,
            "to_tenant": to_tenant,
            "rows_updated": results,
            "final_counts": verify
        }
    except Exception as e:
        return {"error": str(e), "db": db_name, "from_tenant": from_tenant, "to_tenant": to_tenant}


@app.get("/admin/crear-db-cliente", tags=["Admin"])
async def admin_crear_db_cliente(db: str, from_tenant: str = None):
    """
    Crea una DB dedicada para un cliente inmobiliario.
    Cada cliente → su propia DB (aislamiento tipo Airtable).

    Params:
        db: nombre de la DB nueva (ej: robert_crm, maria_crm)
        from_tenant: slug del tenant en lovbot_crm para copiar datos (opcional)

    Ejemplos:
        GET /admin/crear-db-cliente?db=robert_crm&from_tenant=robert
        GET /admin/crear-db-cliente?db=maria_crm
    """
    import sys
    scripts_dir = os.path.join(os.path.dirname(__file__), "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    from scripts.crear_db_cliente import crear_db_cliente
    return crear_db_cliente(db, from_tenant)


@app.post("/admin/onboard", tags=["Admin"])
async def admin_onboard(request: Request):
    """Onboarding automático de cliente inmobiliario. Llamado desde n8n."""
    import sys
    scripts_dir = os.path.join(os.path.dirname(__file__), "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    from scripts.onboard_inmobiliaria import onboard

    data = await request.json()
    resultado = onboard(
        nombre_empresa=data.get("nombre_empresa", ""),
        nombre_asesor=data.get("nombre_asesor", ""),
        email_asesor=data.get("email_asesor", ""),
        telefono_whatsapp=data.get("telefono_whatsapp", ""),
        ciudad=data.get("ciudad", ""),
        zonas=data.get("zonas", ""),
        moneda=data.get("moneda", "USD"),
        chatwoot_account_id=data.get("chatwoot_account_id"),
    )
    return resultado


@app.get("/debug/linkedin-id", tags=["Sistema"])
def debug_linkedin_id():
    """Llama a LinkedIn con el token guardado y devuelve tu Person ID."""
    import requests
    token = os.environ.get("LINKEDIN_ACCESS_TOKEN", "")
    if not token:
        return {"error": "LINKEDIN_ACCESS_TOKEN no está configurado"}
    try:
        r = requests.get(
            "https://api.linkedin.com/v2/userinfo",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        data = r.json()
        person_id = data.get("sub", "no encontrado")
        return {
            "LINKEDIN_PERSON_ID": person_id,
            "instruccion": f"Copia este valor y ponlo en Easypanel como LINKEDIN_PERSON_ID={person_id}",
            "nombre": data.get("name", ""),
            "email": data.get("email", "")
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/debug/env", tags=["Sistema"])
def debug_env():
    """Muestra qué variables de entorno están configuradas (sin exponer valores)."""
    def check(key):
        val = os.environ.get(key, "")
        return f"✅ ({len(val)} chars)" if val else "❌ vacía"

    return {
        "gemini":     {"GEMINI_API_KEY": check("GEMINI_API_KEY")},
        "meta":       {
            "META_ACCESS_TOKEN":      check("META_ACCESS_TOKEN"),
            "IG_BUSINESS_ACCOUNT_ID": check("IG_BUSINESS_ACCOUNT_ID"),
            "FACEBOOK_PAGE_ID":       check("FACEBOOK_PAGE_ID"),
        },
        "linkedin":   {
            "LINKEDIN_ACCESS_TOKEN": check("LINKEDIN_ACCESS_TOKEN"),
            "LINKEDIN_PERSON_ID":    check("LINKEDIN_PERSON_ID"),
        },
        "cloudinary": {
            "CLOUDINARY_CLOUD_NAME":    check("CLOUDINARY_CLOUD_NAME"),
            "CLOUDINARY_UPLOAD_PRESET": check("CLOUDINARY_UPLOAD_PRESET"),
        },
        "whatsapp":   {
            "EVOLUTION_API_URL":       check("EVOLUTION_API_URL"),
            "EVOLUTION_INSTANCE":      check("EVOLUTION_INSTANCE"),
            "EVOLUTION_API_KEY":       check("EVOLUTION_API_KEY"),
            "WHATSAPP_APPROVAL_NUMBER": check("WHATSAPP_APPROVAL_NUMBER"),
        }
    }

