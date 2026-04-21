"""
DB Airtable — Worker Mica Inmobiliaria Demo
============================================
Capa de DB que implementa la misma API publica que `db_postgres.py` de Robert
pero contra Airtable. Esto permite que el worker conversacional clonado de
Robert funcione sin modificaciones, con un simple swap de import:

    # Robert:
    from workers.clientes.lovbot.robert_inmobiliaria import db_postgres as db
    # Mica:
    from workers.clientes.system_ia.demos.inmobiliaria import db_airtable as db

Firmas publicas (deben coincidir con db_postgres.py):
  _available() -> bool
  registrar_lead(telefono, nombre, score, tipo, zona, notas, presupuesto,
                 operacion, ciudad, subniche, fuente_detalle) -> None
  guardar_email(telefono, email) -> None
  guardar_cita(telefono, fecha_cita) -> None
  guardar_propiedad_interes(telefono, propiedad) -> None
  actualizar_ultimo_contacto(telefono) -> None
  desactivar_seguimiento(telefono) -> None
  activar_nurturing(telefono, dias) -> None
  guardar_historial(telefono, historial) -> None
  buscar_propiedades(tipo, operacion, zona, presupuesto, limit) -> list[dict]
  get_lead_by_telefono(telefono) -> dict | None

Base Mica: appA8QxIhBYYAHw0F (env: MICA_AIRTABLE_BASE_ID)
  - Clientes  (env: MICA_DEMO_AIRTABLE_TABLE_CLIENTES)
  - Propiedades (env: MICA_DEMO_AIRTABLE_TABLE_PROPS)

Mapeo campos Clientes:
  Nombre, Apellido, Telefono, Email, Ciudad, Estado, Tipo_Propiedad, Zona,
  Operacion, Presupuesto, Notas_Bot, Fuente, Llego_WhatsApp, Fecha_WhatsApp,
  Fecha_Cita, Sub_nicho, Propiedad_Interes, Estado_Seguimiento,
  Cantidad_Seguimientos, Proximo_Seguimiento, fecha_ultimo_contacto.
"""

from __future__ import annotations

import os
import re
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import requests

logger = logging.getLogger("mica.db_airtable")

# ── Config ────────────────────────────────────────────────────────────────────
AIRTABLE_TOKEN = (
    os.environ.get("AIRTABLE_API_KEY", "")
    or os.environ.get("AIRTABLE_TOKEN", "")
)
AIRTABLE_BASE_ID = (
    os.environ.get("MICA_AIRTABLE_BASE_ID", "")
    or os.environ.get("MICA_DEMO_AIRTABLE_BASE", "")
)
TABLE_CLIENTES = os.environ.get("MICA_DEMO_AIRTABLE_TABLE_CLIENTES", "")
TABLE_PROPS    = os.environ.get("MICA_DEMO_AIRTABLE_TABLE_PROPS", "")
TABLE_SESSIONS = os.environ.get("MICA_DEMO_AIRTABLE_TABLE_SESSIONS", "BotSessions")

AT_HEADERS = {
    "Authorization": f"Bearer {AIRTABLE_TOKEN}",
    "Content-Type": "application/json",
}
AT_BASE_URL = "https://api.airtable.com/v0"


# ── Helpers internos ──────────────────────────────────────────────────────────

def _available() -> bool:
    """Retorna True si Airtable Mica esta configurado."""
    return bool(AIRTABLE_TOKEN and AIRTABLE_BASE_ID and TABLE_CLIENTES)


def _clean_phone(telefono: str) -> str:
    return re.sub(r"\D", "", telefono or "")


def _buscar_lead_raw(telefono: str) -> Optional[dict]:
    """Retorna el record crudo de Airtable (con id + fields) o None."""
    if not _available():
        return None
    url = f"{AT_BASE_URL}/{AIRTABLE_BASE_ID}/{TABLE_CLIENTES}"
    # Buscar por sufijo ultimos 10 digitos (cubre +549... / 549...)
    tel_clean = _clean_phone(telefono)
    if not tel_clean:
        return None
    sufijo = tel_clean[-10:]
    try:
        r = requests.get(
            url,
            headers=AT_HEADERS,
            params={
                "filterByFormula": f"RIGHT({{Telefono}},10)='{sufijo}'",
                "maxRecords": 1,
            },
            timeout=8,
        )
        if r.status_code != 200:
            logger.warning(f"[MICA-DB] buscar lead {r.status_code}: {r.text[:200]}")
            return None
        records = r.json().get("records", [])
        return records[0] if records else None
    except Exception as e:
        logger.warning(f"[MICA-DB] buscar lead exc: {e}")
        return None


def _patch_lead(record_id: str, campos: dict) -> bool:
    url = f"{AT_BASE_URL}/{AIRTABLE_BASE_ID}/{TABLE_CLIENTES}/{record_id}"
    try:
        r = requests.patch(url, headers=AT_HEADERS, json={"fields": campos}, timeout=8)
        return r.status_code in (200, 201)
    except Exception as e:
        logger.warning(f"[MICA-DB] patch lead exc: {e}")
        return False


def _post_lead(campos: dict) -> Optional[str]:
    url = f"{AT_BASE_URL}/{AIRTABLE_BASE_ID}/{TABLE_CLIENTES}"
    try:
        r = requests.post(url, headers=AT_HEADERS, json={"fields": campos}, timeout=8)
        if r.status_code in (200, 201):
            return r.json().get("id", "")
        logger.warning(f"[MICA-DB] post lead {r.status_code}: {r.text[:200]}")
        return None
    except Exception as e:
        logger.warning(f"[MICA-DB] post lead exc: {e}")
        return None


# ── Normalizadores (coinciden con los del worker) ────────────────────────────

_TIPO_MAP = {
    "casa": "casa", "casas": "casa",
    "departamento": "departamento", "depto": "departamento", "apartamento": "departamento",
    "terreno": "terreno", "lote": "terreno",
    "local": "otro", "oficina": "otro",
}

_ZONA_MAP = {
    "apostoles": "Apóstoles", "apóstoles": "Apóstoles",
    "gdor roca": "Gdor Roca", "gobernador roca": "Gdor Roca", "gdorroca": "Gdor Roca",
    "san ignacio": "San Ignacio", "sanignacio": "San Ignacio",
    "otra zona": "Otra Zona", "otra": "Otra Zona", "no sé": "Otra Zona", "no se": "Otra Zona",
}


def _normalizar_tipo(tipo: str) -> str:
    return _TIPO_MAP.get((tipo or "").lower().strip(), "")


def _normalizar_zona(zona: str) -> str:
    return _ZONA_MAP.get((zona or "").lower().strip(), "")


def _score_a_estado(score: str) -> str:
    """Mapea score del bot a campo Estado (singleSelect Mica)."""
    return {
        "caliente": "en_negociacion",
        "tibio": "contactado",
        "frio": "no_contactado",
    }.get((score or "").lower(), "no_contactado")


# ═══════════════════════════════════════════════════════════════════════════════
# API PUBLICA (compatible con db_postgres.py de Robert)
# ═══════════════════════════════════════════════════════════════════════════════

def registrar_lead(telefono: str, nombre: str, score: str = "",
                   tipo: str = "", zona: str = "", notas: str = "",
                   presupuesto: str = "", operacion: str = "",
                   ciudad: str = "", subniche: str = "",
                   fuente_detalle: str = "") -> None:
    """Registra o actualiza un lead en Airtable Mica (tabla Clientes)."""
    if not _available():
        logger.info("[MICA-DB] no configurado — skip registrar_lead")
        return

    telefono = _clean_phone(telefono)
    campos = {
        "Telefono": telefono,
        "Llego_WhatsApp": True,
        "Fuente": "meta_ads" if fuente_detalle.startswith("ad:") else "whatsapp_directo",
    }

    if nombre:
        partes = nombre.strip().split(" ", 1)
        campos["Nombre"] = partes[0]
        if len(partes) > 1:
            campos["Apellido"] = partes[1]

    if score:
        campos["Estado"] = _score_a_estado(score)

    tipo_norm = _normalizar_tipo(tipo)
    if tipo_norm:
        campos["Tipo_Propiedad"] = tipo_norm

    zona_norm = _normalizar_zona(zona)
    if zona_norm:
        campos["Zona"] = zona_norm

    if operacion in ("venta", "alquiler"):
        campos["Operacion"] = operacion

    if ciudad:
        campos["Ciudad"] = ciudad

    if notas:
        campos["Notas_Bot"] = notas[:1000]

    if presupuesto:
        # Si viene como bucket de Airtable (hata_50k/50k_100k/etc) usarlo directo
        # Si viene como string libre (ej: "USD 150k") intentar mapear
        presup_valido = {"hata_50k", "50k_100k", "100k_200k", "mas_200k"}
        if presupuesto in presup_valido:
            campos["Presupuesto"] = presupuesto

    if subniche:
        campos["Sub_nicho"] = subniche

    # Existe? → PATCH. No existe? → POST
    existing = _buscar_lead_raw(telefono)
    if existing:
        ok = _patch_lead(existing["id"], campos)
        logger.info(f"[MICA-DB] PATCH lead tel={telefono} ok={ok}")
    else:
        campos["Fecha_WhatsApp"] = date.today().isoformat()
        if "Estado" not in campos:
            campos["Estado"] = "no_contactado"
        new_id = _post_lead(campos)
        logger.info(f"[MICA-DB] POST lead tel={telefono} id={new_id}")

    # Activar seguimiento para caliente/tibio
    if score in ("caliente", "tibio"):
        lead = _buscar_lead_raw(telefono)
        if lead:
            _patch_lead(lead["id"], {
                "Estado_Seguimiento": "activo",
                "Cantidad_Seguimientos": 0,
                "Proximo_Seguimiento": (date.today() + timedelta(days=1)).isoformat(),
            })


def guardar_email(telefono: str, email: str) -> None:
    """Guarda email del lead."""
    if not _available() or not email:
        return
    lead = _buscar_lead_raw(telefono)
    if lead:
        _patch_lead(lead["id"], {"Email": email.strip()})


def guardar_cita(telefono: str, fecha_cita: str) -> None:
    """Guarda fecha de cita y cambia estado a en_negociacion."""
    if not _available() or not fecha_cita:
        return
    lead = _buscar_lead_raw(telefono)
    if lead:
        _patch_lead(lead["id"], {
            "Fecha_Cita": fecha_cita[:10],
            "Estado": "en_negociacion",
        })


def guardar_propiedad_interes(telefono: str, propiedad: str) -> None:
    """Guarda la propiedad que mostro interes."""
    if not _available() or not propiedad:
        return
    lead = _buscar_lead_raw(telefono)
    if lead:
        _patch_lead(lead["id"], {"Propiedad_Interes": propiedad[:200]})


def actualizar_ultimo_contacto(telefono: str) -> None:
    """Actualiza fecha_ultimo_contacto a ahora."""
    if not _available():
        return
    lead = _buscar_lead_raw(telefono)
    if lead:
        _patch_lead(lead["id"], {
            "fecha_ultimo_contacto": datetime.now(timezone.utc).isoformat(),
        })


def desactivar_seguimiento(telefono: str) -> None:
    """Pausa el seguimiento cuando el lead responde (evita nurturing solapado)."""
    if not _available():
        return
    lead = _buscar_lead_raw(telefono)
    if not lead:
        return
    est = lead.get("fields", {}).get("Estado_Seguimiento", "")
    if est in ("activo", "dormido"):
        _patch_lead(lead["id"], {"Estado_Seguimiento": "pausado"})


def activar_nurturing(telefono: str, dias: int = 3) -> None:
    """Activa el seguimiento automatico (Mica: solo in-window 24hs)."""
    if not _available():
        return
    lead = _buscar_lead_raw(telefono)
    if not lead:
        return
    _patch_lead(lead["id"], {
        "Estado_Seguimiento": "activo",
        "Cantidad_Seguimientos": 0,
        "Proximo_Seguimiento": (date.today() + timedelta(days=dias)).isoformat(),
    })


def guardar_historial(telefono: str, historial: str) -> None:
    """Guarda el historial de la conversacion en el lead."""
    if not _available() or not historial:
        return
    lead = _buscar_lead_raw(telefono)
    if lead:
        # Limitar a 5000 chars para no sobrepasar limites de Airtable long text
        _patch_lead(lead["id"], {"Notas_Bot": historial[:5000]})


def buscar_propiedades(tipo: str = None, operacion: str = None,
                       zona: str = None, presupuesto: str = None,
                       limit: int = 5) -> list[dict]:
    """Busca propiedades con filtros. Retorna dicts compatibles con el worker."""
    if not _available() or not TABLE_PROPS:
        return []

    filtros = ["OR({Disponible}='✅ Disponible',{Disponible}='⏳ Reservado')"]
    if tipo:
        filtros.append(f"LOWER({{Tipo}})='{tipo.lower()}'")
    if operacion:
        filtros.append(f"LOWER({{Operacion}})='{operacion.lower()}'")
    if zona and zona.lower() not in ("otra zona", "otra", "no sé", "no se"):
        filtros.append(f"{{Zona}}='{zona}'")
    if presupuesto and presupuesto in ("hata_50k", "50k_100k", "100k_200k", "mas_200k"):
        filtros.append(f"{{Presupuesto}}='{presupuesto}'")

    formula = "AND(" + ",".join(filtros) + ")" if len(filtros) > 1 else filtros[0]
    url = f"{AT_BASE_URL}/{AIRTABLE_BASE_ID}/{TABLE_PROPS}"
    try:
        r = requests.get(
            url,
            headers=AT_HEADERS,
            params={
                "filterByFormula": formula,
                "maxRecords": limit,
                "sort[0][field]": "Precio",
                "sort[0][direction]": "asc",
            },
            timeout=8,
        )
        if r.status_code != 200:
            logger.warning(f"[MICA-DB] buscar props {r.status_code}: {r.text[:200]}")
            return []
        # Retornar solo fields para que el worker acceda como dict plano
        return [rec["fields"] for rec in r.json().get("records", [])]
    except Exception as e:
        logger.warning(f"[MICA-DB] buscar props exc: {e}")
        return []


def get_lead_by_telefono(telefono: str) -> Optional[dict]:
    """Busca lead por telefono (match por sufijo 10 digitos). Retorna dict
    con campos normalizados o None. Usado para detectar lead recurrente.

    El formato retornado coincide con el que devolveria db_postgres:
    claves en minusculas, con campos internos accesibles desde el worker.
    """
    if not _available():
        return None
    record = _buscar_lead_raw(telefono)
    if not record:
        return None
    fields = record.get("fields", {}) or {}
    # Normalizar al formato que espera el worker (claves lowercase).
    return {
        "id": record.get("id", ""),
        "telefono": fields.get("Telefono", ""),
        "nombre": fields.get("Nombre", ""),
        "apellido": fields.get("Apellido", ""),
        "email": fields.get("Email", ""),
        "ciudad": fields.get("Ciudad", ""),
        "estado": fields.get("Estado", ""),
        "score": fields.get("Score", ""),  # si existe
        "tipo_propiedad": fields.get("Tipo_Propiedad", ""),
        "zona": fields.get("Zona", ""),
        "operacion": fields.get("Operacion", ""),
        "presupuesto": fields.get("Presupuesto", ""),
        "notas_bot": fields.get("Notas_Bot", ""),
        "sub_nicho": fields.get("Sub_nicho", ""),
        "propiedad_interes": fields.get("Propiedad_Interes", ""),
        "fecha_whatsapp": fields.get("Fecha_WhatsApp", ""),
        "fecha_cita": fields.get("Fecha_Cita", ""),
        "fecha_ultimo_contacto": fields.get("fecha_ultimo_contacto", ""),
        "estado_seguimiento": fields.get("Estado_Seguimiento", ""),
        "etiquetas": fields.get("Etiquetas", []),  # multiSelect si existe
        # Flags de control manual por Mica (si ella los setea en Airtable,
        # el bot lo respeta en el siguiente mensaje — sincronizacion bidireccional)
        "_bot_silenciado": fields.get("Estado", "") in (
            "cerrado_ganado", "cerrado_perdido", "silenciar", "no_molestar",
        ),
    }


def actualizar_score_por_telefono(telefono: str, score: str) -> bool:
    """Actualiza el score/estado de un lead. Usado cuando el bot recalifica."""
    if not _available() or not score:
        return False
    lead = _buscar_lead_raw(telefono)
    if not lead:
        return False
    return _patch_lead(lead["id"], {"Estado": _score_a_estado(score)})


# ── Endpoint compatibility: stubs para mantener API completa ──────────────────
# (estas funciones no se usan en el flow conversacional principal, pero
# podrian ser invocadas desde los endpoints CRM. Las dejo como no-op
# con logging para que si se llaman quede registro.)

def get_all_leads() -> list[dict]:
    """Retorna todos los leads para el CRM. TODO: implementar paginacion."""
    if not _available():
        return []
    url = f"{AT_BASE_URL}/{AIRTABLE_BASE_ID}/{TABLE_CLIENTES}"
    results, offset = [], None
    try:
        while True:
            params = {"pageSize": 100}
            if offset:
                params["offset"] = offset
            r = requests.get(url, headers=AT_HEADERS, params=params, timeout=10)
            if r.status_code != 200:
                break
            data = r.json()
            for rec in data.get("records", []):
                results.append({"id": rec["id"], **rec.get("fields", {})})
            offset = data.get("offset")
            if not offset:
                break
        return results
    except Exception as e:
        logger.warning(f"[MICA-DB] get_all_leads exc: {e}")
        return results


def get_all_propiedades() -> list[dict]:
    if not _available() or not TABLE_PROPS:
        return []
    url = f"{AT_BASE_URL}/{AIRTABLE_BASE_ID}/{TABLE_PROPS}"
    results, offset = [], None
    try:
        while True:
            params = {"pageSize": 100}
            if offset:
                params["offset"] = offset
            r = requests.get(url, headers=AT_HEADERS, params=params, timeout=10)
            if r.status_code != 200:
                break
            data = r.json()
            for rec in data.get("records", []):
                results.append({"id": rec["id"], **rec.get("fields", {})})
            offset = data.get("offset")
            if not offset:
                break
        return results
    except Exception as e:
        logger.warning(f"[MICA-DB] get_all_propiedades exc: {e}")
        return results


# ═══════════════════════════════════════════════════════════════════════════════
# BOT SESSIONS — persistencia en tabla Airtable BotSessions
# ═══════════════════════════════════════════════════════════════════════════════
# Campos esperados: Telefono (singleLineText, PK de hecho), Sesion (longText JSON),
# Historial (longText JSON), Updated (datetime).
# El worker usa RAM como cache primario; estas funciones corren en background
# threads para no bloquear el hilo del webhook.

import json as _json

def _sessions_url() -> str:
    return f"{AT_BASE_URL}/{AIRTABLE_BASE_ID}/{TABLE_SESSIONS}"


def _buscar_session_raw(telefono: str) -> Optional[dict]:
    if not _available():
        return None
    tel = _clean_phone(telefono)
    if not tel:
        return None
    try:
        r = requests.get(
            _sessions_url(),
            headers=AT_HEADERS,
            params={"filterByFormula": f"{{Telefono}}='{tel}'", "maxRecords": 1},
            timeout=10,
        )
        if r.status_code != 200:
            return None
        recs = r.json().get("records", [])
        return recs[0] if recs else None
    except Exception as e:
        logger.warning("[MICA-SESSION] buscar error: %s", e)
        return None


def setup_bot_sessions() -> None:
    """Verifica que la tabla BotSessions exista (Airtable la crea manualmente).
    No lanza excepcion si no existe — solo loguea."""
    if not _available():
        return
    try:
        r = requests.get(_sessions_url(), headers=AT_HEADERS, params={"maxRecords": 1}, timeout=8)
        if r.status_code == 404:
            logger.warning("[MICA-SESSION] tabla '%s' no existe en base %s — crear manualmente con campos: Telefono, Sesion, Historial, Updated", TABLE_SESSIONS, AIRTABLE_BASE_ID)
        elif r.status_code == 200:
            logger.info("[MICA-SESSION] tabla '%s' OK", TABLE_SESSIONS)
    except Exception as e:
        logger.warning("[MICA-SESSION] setup error: %s", e)


def get_bot_session(telefono: str) -> dict:
    """Lee sesion + historial desde Airtable. Retorna {} si no existe."""
    rec = _buscar_session_raw(telefono)
    if not rec:
        return {}
    fields = rec.get("fields", {})
    try:
        sesion = _json.loads(fields.get("Sesion", "") or "{}")
    except Exception:
        sesion = {}
    try:
        historial = _json.loads(fields.get("Historial", "") or "[]")
    except Exception:
        historial = []
    return {"sesion": sesion, "historial": historial}


def save_bot_session(telefono: str, sesion: dict, historial: list) -> None:
    """Guarda o actualiza la sesion en Airtable via upsert atomico.

    Usa performUpsert de Airtable para evitar duplicados cuando 2 saves
    concurrentes (threads background) corren casi a la vez sobre el mismo tel.
    """
    if not _available():
        return
    tel = _clean_phone(telefono)
    if not tel:
        return
    try:
        payload = {
            "performUpsert": {"fieldsToMergeOn": ["Telefono"]},
            "records": [{
                "fields": {
                    "Telefono": tel,
                    "Sesion": _json.dumps(sesion, ensure_ascii=False, default=str)[:99000],
                    "Historial": _json.dumps(historial, ensure_ascii=False, default=str)[:99000],
                    "Updated": datetime.now(timezone.utc).isoformat(),
                }
            }],
        }
        r = requests.patch(_sessions_url(), headers=AT_HEADERS, json=payload, timeout=10)
        if r.status_code >= 400:
            logger.warning("[MICA-SESSION] save HTTP %s tel=%s: %s", r.status_code, tel[-4:], r.text[:200])
    except Exception as e:
        logger.warning("[MICA-SESSION] save error tel=%s: %s", tel[-4:], e)


def delete_bot_session(telefono: str) -> None:
    """Borra el registro de sesion. No-op si no existe."""
    if not _available():
        return
    tel = _clean_phone(telefono)
    if not tel:
        return
    try:
        existing = _buscar_session_raw(tel)
        if existing:
            requests.delete(f"{_sessions_url()}/{existing['id']}", headers=AT_HEADERS, timeout=10)
    except Exception as e:
        logger.warning("[MICA-SESSION] delete error tel=%s: %s", tel[-4:], e)


# ═══════════════════════════════════════════════════════════════════════════════
# RESUMENES + NURTURING — stubs no-op (no usados en Mica)
# ═══════════════════════════════════════════════════════════════════════════════

def crear_tabla_resumenes() -> None:
    pass


def setup_nurturing_columns() -> None:
    pass


def guardar_resumen(telefono: str, resumen: str) -> None:
    pass


def listar_resumenes(limit: int = 20, score_min: int = None,
                     desde: str = None, search: str = None) -> list[dict]:
    """Stub: Mica no tiene tabla 'resumenes_conversacion' en Airtable todavía.
    Retorna lista vacía compatible con handler /crm/resumenes del worker.
    Params aceptados para match con la interfaz del worker Postgres (Robert).
    Futuro: tabla Airtable 'ResumenesConversacion' con schema equivalente."""
    return []


def marcar_nurturing_enviado(telefono: str, tipo: str = "24h") -> None:
    """Mica usa solo nurturing in-window 24hs (no templates). No-op por ahora."""
    pass


def obtener_leads_sin_cita_24h() -> list[dict]:
    """Retorna leads calificados sin cita agendada con +24hs sin contacto.
    Usado por el endpoint /admin/nurturing/24h del worker.

    Filtros Airtable:
    - Estado in (contactado, en_negociacion)
    - Fecha_Cita esta vacio
    - fecha_ultimo_contacto > 24hs
    """
    if not _available():
        return []
    try:
        leads = get_all_leads()
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=24)
        result = []
        for lead in leads:
            estado = lead.get("Estado", "")
            if estado not in ("contactado", "en_negociacion"):
                continue
            if lead.get("Fecha_Cita"):
                continue
            ultimo = lead.get("fecha_ultimo_contacto", "")
            if ultimo:
                try:
                    ts = datetime.fromisoformat(ultimo.replace("Z", "+00:00"))
                    if ts > cutoff:
                        continue
                except Exception:
                    pass
            result.append(lead)
        return result
    except Exception as e:
        logger.warning(f"[MICA-DB] obtener_leads_sin_cita_24h exc: {e}")
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# METRICAS — calculadas sobre Airtable Clientes
# ═══════════════════════════════════════════════════════════════════════════════

def get_metricas() -> dict:
    """Retorna metricas basicas del pipeline calculadas sobre tabla Clientes."""
    if not _available():
        return {"error": "Airtable Mica no configurado"}
    try:
        leads = get_all_leads()
        total = len(leads)
        por_estado = {}
        por_score = {"caliente": 0, "tibio": 0, "frio": 0}
        for lead in leads:
            est = lead.get("Estado", "no_contactado")
            por_estado[est] = por_estado.get(est, 0) + 1
            if est == "en_negociacion":
                por_score["caliente"] += 1
            elif est == "contactado":
                por_score["tibio"] += 1
            else:
                por_score["frio"] += 1
        return {
            "total_leads": total,
            "por_estado": por_estado,
            "por_score": por_score,
        }
    except Exception as e:
        logger.warning(f"[MICA-DB] get_metricas exc: {e}")
        return {"error": str(e)}


def get_reportes() -> dict:
    """Stub — Mica no tiene tabla reportes separada todavia."""
    return get_metricas()


def get_leads_con_cita() -> list[dict]:
    """Retorna leads con Fecha_Cita populated."""
    if not _available():
        return []
    try:
        leads = get_all_leads()
        return [l for l in leads if l.get("Fecha_Cita")]
    except Exception as e:
        logger.warning(f"[MICA-DB] get_leads_con_cita exc: {e}")
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# CRUD LEADS (para endpoints CRM /crm/clientes)
# ═══════════════════════════════════════════════════════════════════════════════

def create_lead(campos: dict) -> dict:
    if not _available():
        return {"error": "Airtable no configurado"}
    new_id = _post_lead(campos)
    return {"id": new_id, **campos} if new_id else {"error": "fallo al crear"}


def update_lead(record_id: str, campos: dict) -> bool:
    if not _available() or not record_id:
        return False
    return _patch_lead(record_id, campos)


def delete_lead(record_id: str) -> bool:
    if not _available() or not record_id:
        return False
    url = f"{AT_BASE_URL}/{AIRTABLE_BASE_ID}/{TABLE_CLIENTES}/{record_id}"
    try:
        r = requests.delete(url, headers=AT_HEADERS, timeout=8)
        return r.status_code in (200, 204)
    except Exception as e:
        logger.warning(f"[MICA-DB] delete_lead exc: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# CRUD PROPIEDADES (para endpoints CRM /crm/propiedades)
# ═══════════════════════════════════════════════════════════════════════════════

def create_propiedad(campos: dict) -> dict:
    if not _available() or not TABLE_PROPS:
        return {"error": "Airtable no configurado"}
    url = f"{AT_BASE_URL}/{AIRTABLE_BASE_ID}/{TABLE_PROPS}"
    try:
        r = requests.post(url, headers=AT_HEADERS, json={"fields": campos}, timeout=8)
        if r.status_code in (200, 201):
            return {"id": r.json().get("id", ""), **campos}
        return {"error": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"error": str(e)}


def update_propiedad(record_id: str, campos: dict) -> bool:
    if not _available() or not TABLE_PROPS or not record_id:
        return False
    url = f"{AT_BASE_URL}/{AIRTABLE_BASE_ID}/{TABLE_PROPS}/{record_id}"
    try:
        r = requests.patch(url, headers=AT_HEADERS, json={"fields": campos}, timeout=8)
        return r.status_code in (200, 201)
    except Exception:
        return False


def delete_propiedad(record_id: str) -> bool:
    if not _available() or not TABLE_PROPS or not record_id:
        return False
    url = f"{AT_BASE_URL}/{AIRTABLE_BASE_ID}/{TABLE_PROPS}/{record_id}"
    try:
        r = requests.delete(url, headers=AT_HEADERS, timeout=8)
        return r.status_code in (200, 204)
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# CRUD ACTIVOS (CLIENTES_ACTIVOS table)
# ═══════════════════════════════════════════════════════════════════════════════

TABLE_ACTIVOS = os.environ.get("MICA_DEMO_AIRTABLE_TABLE_ACTIVOS", "")


def get_all_activos() -> list[dict]:
    if not _available() or not TABLE_ACTIVOS:
        return []
    url = f"{AT_BASE_URL}/{AIRTABLE_BASE_ID}/{TABLE_ACTIVOS}"
    results, offset = [], None
    try:
        while True:
            params = {"pageSize": 100}
            if offset:
                params["offset"] = offset
            r = requests.get(url, headers=AT_HEADERS, params=params, timeout=10)
            if r.status_code != 200:
                break
            data = r.json()
            for rec in data.get("records", []):
                results.append({"id": rec["id"], **rec.get("fields", {})})
            offset = data.get("offset")
            if not offset:
                break
        return results
    except Exception:
        return results


def create_activo(campos: dict) -> dict:
    if not _available() or not TABLE_ACTIVOS:
        return {"error": "Airtable no configurado"}
    url = f"{AT_BASE_URL}/{AIRTABLE_BASE_ID}/{TABLE_ACTIVOS}"
    try:
        r = requests.post(url, headers=AT_HEADERS, json={"fields": campos}, timeout=8)
        if r.status_code in (200, 201):
            return {"id": r.json().get("id", ""), **campos}
        return {"error": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"error": str(e)}


def update_activo(record_id: str, campos: dict) -> bool:
    if not _available() or not TABLE_ACTIVOS or not record_id:
        return False
    url = f"{AT_BASE_URL}/{AIRTABLE_BASE_ID}/{TABLE_ACTIVOS}/{record_id}"
    try:
        r = requests.patch(url, headers=AT_HEADERS, json={"fields": campos}, timeout=8)
        return r.status_code in (200, 201)
    except Exception:
        return False


def delete_activo(record_id: str) -> bool:
    if not _available() or not TABLE_ACTIVOS or not record_id:
        return False
    url = f"{AT_BASE_URL}/{AIRTABLE_BASE_ID}/{TABLE_ACTIVOS}/{record_id}"
    try:
        r = requests.delete(url, headers=AT_HEADERS, timeout=8)
        return r.status_code in (200, 204)
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# STUBS no-op para tablas que Mica no tiene aun (asesores, propietarios, etc)
# Endpoints CRM responden con [] o {} hasta que Mica cree esas tablas en Airtable.
# ═══════════════════════════════════════════════════════════════════════════════

# Asesores
def get_all_asesores() -> list[dict]: return []
def create_asesor(campos: dict) -> dict: return {"error": "Tabla Asesores no existe en base Mica"}
def update_asesor(record_id: str, campos: dict) -> bool: return False
def delete_asesor(record_id: str) -> bool: return False

# Propietarios
def get_all_propietarios() -> list[dict]: return []
def create_propietario(campos: dict) -> dict: return {"error": "Tabla Propietarios no existe en base Mica"}
def update_propietario(record_id: str, campos: dict) -> bool: return False
def delete_propietario(record_id: str) -> bool: return False

# Loteos
def get_all_loteos() -> list[dict]: return []
def create_loteo(campos: dict) -> dict: return {"error": "Tabla Loteos no existe en base Mica"}
def update_loteo(record_id: str, campos: dict) -> bool: return False
def delete_loteo(record_id: str) -> bool: return False

# Lotes mapa
def get_lotes_mapa(loteo_id: str = None) -> list[dict]: return []
def create_lote_mapa(campos: dict) -> dict: return {"error": "Tabla LotesMapa no existe en base Mica"}
def update_lote_mapa(record_id: str, campos: dict) -> bool: return False
def delete_lote_mapa(record_id: str) -> bool: return False

# Contratos
def get_all_contratos() -> list[dict]: return []
def create_contrato(campos: dict) -> dict: return {"error": "Tabla Contratos no existe en base Mica"}
def update_contrato(record_id: str, campos: dict) -> bool: return False
def delete_contrato(record_id: str) -> bool: return False

# Visitas
def get_all_visitas() -> list[dict]: return []
def create_visita(campos: dict) -> dict: return {"error": "Tabla Visitas no existe en base Mica"}
def update_visita(record_id: str, campos: dict) -> bool: return False
def delete_visita(record_id: str) -> bool: return False


# ═══════════════════════════════════════════════════════════════════════════════
# TECH PROVIDER WABA — stubs no-op (Mica no es Tech Provider Meta)
# Si Mica algun dia se vuelve TP, implementar contra una tabla WABA_Clients en Airtable.
# ═══════════════════════════════════════════════════════════════════════════════

def setup_waba_clients_table() -> None:
    pass


def listar_waba_clients() -> list[dict]:
    return []


def obtener_waba_client_por_phone(phone_number_id: str) -> dict:
    return {}


def registrar_waba_client(client_slug: str, phone_number_id: str, waba_id: str,
                          access_token: str, worker_url: str) -> dict:
    return {"error": "Mica no es Tech Provider Meta — usa Evolution API"}


def actualizar_waba_worker_url(phone_number_id: str, nuevo_url: str) -> bool:
    return False


def marcar_webhook_subscrito(phone_number_id: str) -> bool:
    return False


def eliminar_waba_client(phone_number_id: str) -> bool:
    return False
