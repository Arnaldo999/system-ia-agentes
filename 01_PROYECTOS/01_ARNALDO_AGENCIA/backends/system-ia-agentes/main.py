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

# Throttle de alertas Telegram: mismo endpoint+tipo_error no repite en <5 min
_ALERT_THROTTLE: dict = {}
_ALERT_COOLDOWN = 300  # segundos

def _enviar_alerta_telegram(endpoint: str, error: Exception, method: str = ""):
    """Envía alerta a Telegram cuando hay un error 500. Throttle para no spammear."""
    import time, requests
    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    tg_chat = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not tg_token or not tg_chat:
        return

    # Throttle: mismo endpoint + tipo error no re-envía en cooldown
    key = f"{endpoint}:{type(error).__name__}"
    now = time.time()
    last = _ALERT_THROTTLE.get(key, 0)
    if now - last < _ALERT_COOLDOWN:
        return
    _ALERT_THROTTLE[key] = now

    host = os.environ.get("COOLIFY_URL", "prod")
    msg = (
        f"🚨 *Error 500 en producción*\n\n"
        f"*Host*: {host}\n"
        f"*{method} {endpoint}*\n"
        f"*{type(error).__name__}*: {str(error)[:200]}\n\n"
        f"Ver traceback: `GET /debug/errors`"
    )
    try:
        requests.post(
            f"https://api.telegram.org/bot{tg_token}/sendMessage",
            json={"chat_id": tg_chat, "text": msg, "parse_mode": "Markdown"},
            timeout=5,
        )
    except Exception:
        pass  # no queremos que la alerta rompa el flujo principal

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
    # Alerta Telegram asíncrona (con throttle)
    _enviar_alerta_telegram(endpoint, error, contexto.get("method", ""))

# ── Clientes Arnaldo ──────────────────────────────────────────────────────────
from workers.clientes.arnaldo.maicol.worker import router as maicol_router
from workers.clientes.arnaldo.prueba.worker import router as prueba_router

# ── Clientes Lovbot ───────────────────────────────────────────────────────────
from workers.clientes.lovbot.robert_inmobiliaria.worker import router as robert_inmo_router
from workers.clientes.lovbot.robert_inmobiliaria.worker import _procesar as robert_inmo_procesar

# ── Cliente Lovbot — Inmobiliaria García ──
from workers.clientes.lovbot.inmobiliaria_garcia.worker import router as inmobiliaria_garcia_router
from workers.clientes.lovbot.inmobiliaria_garcia.worker import _procesar as inmobiliaria_garcia_procesar
from workers.clientes.lovbot.test_arnaldo.worker import router as test_arnaldo_router

# ── Tech Provider Lovbot — Meta Webhooks (reemplaza n8n workflows) ────────────
from workers.clientes.lovbot.tech_provider.webhook_meta import router as meta_tp_router

# ── Demos ─────────────────────────────────────────────────────────────────────
from workers.demos.inmobiliaria.worker  import router as demo_inmobiliaria_router
from workers.demos.gastronomico.worker  import router as demo_gastronomico_router

# ── SaaS ──────────────────────────────────────────────────────────────────────
from workers.shared.tenants import router as tenants_router, crm_router, admin_router

# ── System IA — Clientes ──────────────────────────────────────────────────────
from workers.clientes.system_ia.lau.worker import router as lau_router
from workers.clientes.system_ia.demos.inmobiliaria.worker import (
    router as mica_demo_inmo_router,
    router_v2 as mica_demo_inmo_router_v2,
)
from workers.clientes.system_ia.onboarding.router import router as mica_onboarding_router

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
    allow_origin_regex=r"https?://.*",
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
app.include_router(inmobiliaria_garcia_router)
app.include_router(test_arnaldo_router)
app.include_router(demo_inmobiliaria_router)
app.include_router(demo_gastronomico_router)
app.include_router(lau_router)
app.include_router(mica_demo_inmo_router)
app.include_router(mica_demo_inmo_router_v2)
app.include_router(mica_onboarding_router)
app.include_router(social_router)
app.include_router(meta_tp_router)


# ── Meta Webhook — Tech Provider Robert/Lovbot ───────────────────────────────
_META_VERIFY_TOKEN = os.environ.get("META_VERIFY_TOKEN", "")
_META_MSG_IDS_PROCESADOS: set[str] = set()  # deduplicación de reintentos Meta
_META_DEDUP_LOCK = __import__("threading").Lock()  # thread-safe dedup


def _transcribir_audio_meta(media_id: str) -> str:
    """Descarga audio de Meta Graph API y transcribe con Whisper (OpenAI de Robert)."""
    import requests, tempfile, os as _os
    token = _os.environ.get("META_ACCESS_TOKEN", "")
    openai_key = _os.environ.get("LOVBOT_OPENAI_API_KEY", "")
    if not token or not openai_key:
        print("[META-AUDIO] Faltan META_ACCESS_TOKEN o LOVBOT_OPENAI_API_KEY")
        return ""
    try:
        # Paso 1: obtener URL del media
        r = requests.get(
            f"https://graph.facebook.com/v18.0/{media_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if r.status_code != 200:
            print(f"[META-AUDIO] Error obteniendo URL media: {r.status_code} {r.text[:200]}")
            return ""
        media_url = r.json().get("url", "")
        if not media_url:
            return ""

        # Paso 2: descargar el audio
        r2 = requests.get(
            media_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        if r2.status_code != 200:
            print(f"[META-AUDIO] Error descargando audio: {r2.status_code}")
            return ""

        # Paso 3: transcribir con Whisper
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp.write(r2.content)
            tmp_path = tmp.name
        try:
            with open(tmp_path, "rb") as f:
                resp = requests.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {openai_key}"},
                    data={"model": "whisper-1", "language": "es"},
                    files={"file": ("audio.ogg", f, "audio/ogg")},
                    timeout=30,
                )
            if resp.status_code == 200:
                texto = resp.json().get("text", "").strip()
                print(f"[META-AUDIO] Transcripción: '{texto[:80]}'")
                return texto
            else:
                print(f"[META-AUDIO] Whisper error: {resp.status_code} {resp.text[:200]}")
                return ""
        finally:
            try:
                _os.unlink(tmp_path)
            except Exception:
                pass
    except Exception as e:
        print(f"[META-AUDIO] Excepción: {e}")
        return ""

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
                # Aceptar text, button y audio (notas de voz)
                if msg_type == "text":
                    texto = msg.get("text", {}).get("body", "")
                elif msg_type == "button":
                    texto = msg.get("button", {}).get("text", "") or msg.get("button", {}).get("payload", "")
                elif msg_type == "audio":
                    media_id = msg.get("audio", {}).get("id", "")
                    if not media_id:
                        continue
                    texto = _transcribir_audio_meta(media_id)
                    if not texto:
                        # No se pudo transcribir — avisarle al usuario
                        telefono_tmp = msg.get("from", "")
                        if telefono_tmp:
                            import requests as _req
                            _token = os.environ.get("META_ACCESS_TOKEN", "")
                            _phone_id = os.environ.get("META_PHONE_NUMBER_ID", "")
                            if _token and _phone_id:
                                try:
                                    _req.post(
                                        f"https://graph.facebook.com/v18.0/{_phone_id}/messages",
                                        headers={"Authorization": f"Bearer {_token}", "Content-Type": "application/json"},
                                        json={"messaging_product": "whatsapp", "to": telefono_tmp,
                                              "type": "text", "text": {"body": "Recibí tu nota de voz, pero no pude entenderla bien. ¿Podés escribirme? 🙏"}},
                                        timeout=8,
                                    )
                                except Exception:
                                    pass
                        continue
                else:
                    continue

                msg_id = msg.get("id", "")
                # Ignorar mensajes con timestamp > 30 segundos (reintentos de Meta tras restart)
                import time as _time
                msg_ts = int(msg.get("timestamp", 0))
                if msg_ts and (_time.time() - msg_ts) > 30:
                    print(f"[META-WEBHOOK] Mensaje viejo ignorado ({int(_time.time()-msg_ts)}s): {msg_id}")
                    continue

                if msg_id:
                    with _META_DEDUP_LOCK:
                        if msg_id in _META_MSG_IDS_PROCESADOS:
                            print(f"[META-WEBHOOK] Duplicado ignorado: {msg_id}")
                            continue
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



@app.get("/admin/setup-audit-columns", tags=["Admin"])
async def admin_setup_audit_columns():
    """Agrega columnas de auditoría (updated_by, updated_at, created_by) a tablas
    principales del CRM. Idempotente — se puede correr varias veces sin efecto adverso.
    """
    try:
        import psycopg2
        dsn = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
        if not dsn:
            # Fallback: usar LOVBOT_PG_* si estamos en el VPS de Robert
            pg_host = os.environ.get("LOVBOT_PG_HOST")
            if pg_host:
                dsn = (
                    f"host={pg_host} port={os.environ.get('LOVBOT_PG_PORT','5432')} "
                    f"dbname={os.environ.get('LOVBOT_PG_DB','lovbot_crm')} "
                    f"user={os.environ.get('LOVBOT_PG_USER','lovbot')} "
                    f"password={os.environ.get('LOVBOT_PG_PASS','')}"
                )
        if not dsn:
            return {"ok": False, "error": "DATABASE_URL no configurado"}
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        tablas = ["leads", "propiedades", "clientes_activos", "asesores",
                  "propietarios", "loteos", "contratos", "visitas"]
        resultados = {}
        for tabla in tablas:
            try:
                for col_sql in [
                    f"ALTER TABLE {tabla} ADD COLUMN IF NOT EXISTS updated_by TEXT",
                    f"ALTER TABLE {tabla} ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()",
                    f"ALTER TABLE {tabla} ADD COLUMN IF NOT EXISTS created_by TEXT",
                ]:
                    cur.execute(col_sql)
                resultados[tabla] = "ok"
            except psycopg2.errors.UndefinedTable:
                conn.rollback()
                resultados[tabla] = "no existe (skip)"
            except Exception as e:
                conn.rollback()
                resultados[tabla] = f"error: {e}"
        conn.commit()
        cur.close()
        conn.close()
        return {"ok": True, "resultados": resultados}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/admin/crear-db-cliente", tags=["Admin"])
async def admin_crear_db_cliente(db: str, from_tenant: str = None, from_db: str = "lovbot_crm"):
    """
    Crea una DB dedicada para un cliente inmobiliario.
    Cada cliente → su propia DB (aislamiento tipo Airtable, regla #0 irrompible).

    Params:
        db:          nombre de la DB nueva (ej: robert_crm, maria_crm)
        from_tenant: slug del tenant a copiar (opcional)
        from_db:     DB origen desde donde copiar (default: lovbot_crm).
                     Útil si los datos están en otra DB como robert_crm vieja.

    Ejemplos:
        GET /admin/crear-db-cliente?db=robert_crm_new&from_tenant=robert&from_db=robert_crm
        GET /admin/crear-db-cliente?db=maria_crm
    """
    import sys
    scripts_dir = os.path.join(os.path.dirname(__file__), "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    from scripts.crear_db_cliente import crear_db_cliente
    return crear_db_cliente(db, from_tenant, from_db)


@app.get("/admin/listar-dbs", tags=["Admin"])
async def admin_listar_dbs():
    """
    Lista todas las DBs del cluster Postgres con su conteo de filas en
    las tablas principales. Útil para auditar arquitectura workspaces.
    """
    import psycopg2
    PG_HOST = os.environ.get("LOVBOT_PG_HOST", "")
    PG_PORT = os.environ.get("LOVBOT_PG_PORT", "5432")
    PG_USER = os.environ.get("LOVBOT_PG_USER", "lovbot")
    PG_PASS = os.environ.get("LOVBOT_PG_PASS", "")

    # 1. Listar DBs
    try:
        conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname="postgres",
                                user=PG_USER, password=PG_PASS)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("""
            SELECT datname FROM pg_database
            WHERE datistemplate = false AND datname NOT IN ('postgres')
            ORDER BY datname
        """)
        dbs = [r[0] for r in cur.fetchall()]
        cur.close()
        conn.close()
    except Exception as e:
        return {"ok": False, "error": f"listar DBs: {e}"}

    # 2. Por cada DB, intentar contar leads/propiedades/clientes_activos
    resumen = {}
    for db in dbs:
        try:
            c = psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=db,
                                 user=PG_USER, password=PG_PASS, connect_timeout=5)
            cur = c.cursor()
            info = {}
            for tabla in ["leads", "propiedades", "clientes_activos", "loteos", "contratos", "visitas"]:
                try:
                    cur.execute(f"SELECT COUNT(*), COUNT(DISTINCT tenant_slug) FROM {tabla}")
                    total, n_tenants = cur.fetchone()
                    info[tabla] = {"total": total, "tenants": n_tenants}
                except Exception:
                    info[tabla] = "no_existe"
            # Tenant_slugs distintos en leads
            try:
                cur.execute("SELECT tenant_slug, COUNT(*) FROM leads GROUP BY tenant_slug")
                info["_tenants_leads"] = {row[0]: row[1] for row in cur.fetchall()}
            except Exception:
                info["_tenants_leads"] = {}
            cur.close()
            c.close()
            resumen[db] = info
        except Exception as e:
            resumen[db] = {"error": str(e)[:100]}

    return {"ok": True, "dbs_totales": len(dbs), "dbs": dbs, "resumen": resumen}


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

