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

TABLE_ACTIVOS       = os.environ.get("MICA_DEMO_AIRTABLE_TABLE_ACTIVOS", "tblpfSE6qkGCV6e99")

# ── Tablas v3 (IDs fijos de base appA8QxIhBYYAHw0F) ─────────────────────────
TABLE_CONTRATOS           = os.environ.get("MICA_TABLE_CONTRATOS",      "tblQvGFwL5sZdf1jU")
TABLE_CONTRATOS_ALQUILER  = os.environ.get("MICA_TABLE_CONTRATOS_ALQ",  "tbluxdLR0bnpfLay9")
TABLE_PAGOS_ALQUILER      = os.environ.get("MICA_TABLE_PAGOS_ALQ",      "tblUKoTFkJzk31N2m")
TABLE_LIQUIDACIONES       = os.environ.get("MICA_TABLE_LIQUIDACIONES",  "tbl3ELdKQOTlKj4Wz")
TABLE_INMUEBLES_RENTA     = os.environ.get("MICA_TABLE_INMUEBLES_RENTA","tblRlLK8doYDCZIiK")
TABLE_LOTES_MAPA          = os.environ.get("MICA_TABLE_LOTES_MAPA",     "tblglWTmEsQ7n8ANf")
TABLE_ASESORES            = os.environ.get("MICA_TABLE_ASESORES",       "tblfso1JAoJaDUTLf")
TABLE_PROPIETARIOS        = os.environ.get("MICA_TABLE_PROPIETARIOS",   "tbl7XoZ9NOfkfqQAG")
TABLE_LOTEOS              = os.environ.get("MICA_TABLE_LOTEOS",         "tbluM3b8vHShORORO")
TABLE_INQUILINOS          = os.environ.get("MICA_TABLE_INQUILINOS",     "tblCs0nMKxExE6lp5")
TABLE_VISITAS             = os.environ.get("MICA_TABLE_VISITAS",        "tblu3EHwh8eJkOPjI")


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
# HELPERS GENÉRICOS para CRUD sobre cualquier tabla Airtable
# ═══════════════════════════════════════════════════════════════════════════════

def _at_get_all(table_id: str, params: dict = None) -> list[dict]:
    """Retorna todos los registros de una tabla Airtable (paginando)."""
    if not _available() or not table_id:
        return []
    url = f"{AT_BASE_URL}/{AIRTABLE_BASE_ID}/{table_id}"
    results, offset = [], None
    try:
        while True:
            p = {"pageSize": 100, **(params or {})}
            if offset:
                p["offset"] = offset
            r = requests.get(url, headers=AT_HEADERS, params=p, timeout=12)
            if r.status_code != 200:
                logger.warning("[MICA-DB] _at_get_all %s HTTP %s: %s", table_id, r.status_code, r.text[:200])
                break
            data = r.json()
            for rec in data.get("records", []):
                results.append({"id": rec["id"], **rec.get("fields", {})})
            offset = data.get("offset")
            if not offset:
                break
        return results
    except Exception as e:
        logger.warning("[MICA-DB] _at_get_all exc: %s", e)
        return results


def _at_create(table_id: str, campos: dict) -> dict:
    """Crea un registro en una tabla Airtable."""
    if not _available() or not table_id:
        return {"error": "Airtable no configurado o tabla vacía"}
    url = f"{AT_BASE_URL}/{AIRTABLE_BASE_ID}/{table_id}"
    try:
        r = requests.post(url, headers=AT_HEADERS, json={"fields": campos}, timeout=10)
        if r.status_code in (200, 201):
            rec = r.json()
            return {"id": rec.get("id", ""), **rec.get("fields", {})}
        logger.warning("[MICA-DB] _at_create %s HTTP %s: %s", table_id, r.status_code, r.text[:200])
        return {"error": f"HTTP {r.status_code}: {r.text[:200]}"}
    except Exception as e:
        logger.warning("[MICA-DB] _at_create exc: %s", e)
        return {"error": str(e)}


def _at_update(table_id: str, record_id: str, campos: dict) -> bool:
    """PATCH un registro en Airtable."""
    if not _available() or not table_id or not record_id:
        return False
    url = f"{AT_BASE_URL}/{AIRTABLE_BASE_ID}/{table_id}/{record_id}"
    try:
        r = requests.patch(url, headers=AT_HEADERS, json={"fields": campos}, timeout=10)
        return r.status_code in (200, 201)
    except Exception as e:
        logger.warning("[MICA-DB] _at_update exc: %s", e)
        return False


def _at_delete(table_id: str, record_id: str) -> bool:
    """Elimina un registro de Airtable."""
    if not _available() or not table_id or not record_id:
        return False
    url = f"{AT_BASE_URL}/{AIRTABLE_BASE_ID}/{table_id}/{record_id}"
    try:
        r = requests.delete(url, headers=AT_HEADERS, timeout=10)
        return r.status_code in (200, 204)
    except Exception as e:
        logger.warning("[MICA-DB] _at_delete exc: %s", e)
        return False


def _at_get_one(table_id: str, record_id: str) -> Optional[dict]:
    """Lee un registro de Airtable por ID."""
    if not _available() or not table_id or not record_id:
        return None
    url = f"{AT_BASE_URL}/{AIRTABLE_BASE_ID}/{table_id}/{record_id}"
    try:
        r = requests.get(url, headers=AT_HEADERS, timeout=10)
        if r.status_code == 200:
            rec = r.json()
            return {"id": rec.get("id", ""), **rec.get("fields", {})}
        return None
    except Exception:
        return None


def _at_filter(table_id: str, formula: str, max_records: int = 100) -> list[dict]:
    """Filtra registros por fórmula Airtable."""
    if not _available() or not table_id:
        return []
    url = f"{AT_BASE_URL}/{AIRTABLE_BASE_ID}/{table_id}"
    try:
        r = requests.get(
            url, headers=AT_HEADERS,
            params={"filterByFormula": formula, "maxRecords": max_records},
            timeout=12,
        )
        if r.status_code == 200:
            return [{"id": rec["id"], **rec.get("fields", {})} for rec in r.json().get("records", [])]
        return []
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# ASESORES
# ═══════════════════════════════════════════════════════════════════════════════

def get_all_asesores() -> list[dict]:
    return [_unmap_asesor(r) for r in _at_get_all(TABLE_ASESORES)]


def create_asesor(campos: dict) -> dict:
    return _at_create(TABLE_ASESORES, _map_asesor(campos))


def update_asesor(record_id: str, campos: dict) -> bool:
    return _at_update(TABLE_ASESORES, record_id, _map_asesor(campos))


def delete_asesor(record_id: str) -> bool:
    return _at_delete(TABLE_ASESORES, record_id)


# ═══════════════════════════════════════════════════════════════════════════════
# PROPIETARIOS (tabla legacy — se mantiene para compatibilidad)
# ═══════════════════════════════════════════════════════════════════════════════

def get_all_propietarios() -> list[dict]:
    return [_unmap_propietario(r) for r in _at_get_all(TABLE_PROPIETARIOS)]


def create_propietario(campos: dict) -> dict:
    return _at_create(TABLE_PROPIETARIOS, _map_propietario(campos))


def update_propietario(record_id: str, campos: dict) -> bool:
    return _at_update(TABLE_PROPIETARIOS, record_id, _map_propietario(campos))


def delete_propietario(record_id: str) -> bool:
    return _at_delete(TABLE_PROPIETARIOS, record_id)


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS DE NORMALIZACIÓN — Airtable PascalCase → frontend lowercase
# Espejo inverso de los _map_* de escritura. Se aplican en los GET para que el
# frontend reciba campos lowercase tal como los espera en cada panel JS.
# Convención: si el campo ya es id (string rec...), se preserva como string.
# ═══════════════════════════════════════════════════════════════════════════════

def _unmap_loteo(rec: dict) -> dict:
    """Airtable Loteos → frontend lowercase."""
    f = rec.get("fields", rec)  # acepta raw Airtable {id, fields} o ya flattened {id, Nombre, ...}
    rec_id = rec.get("id") or f.get("id", "")
    return {
        "id": rec_id,
        "nombre": f.get("Nombre") or "",
        "slug": f.get("Slug") or "",
        "descripcion": f.get("Descripcion") or "",
        "ubicacion": f.get("Ubicacion") or "",
        "ciudad": f.get("Ciudad") or "",
        "mapa_svg_url": f.get("Mapa_SVG_URL") or "",
        "total_lotes": f.get("Total_Lotes") or 0,
        "lotes_disponibles": f.get("Lotes_Disponibles") or 0,
        "lotes_reservados": f.get("Lotes_Reservados") or 0,
        "lotes_vendidos": f.get("Lotes_Vendidos") or 0,
        "precio_desde": f.get("Precio_Desde") or None,
        "moneda": f.get("Moneda") or "USD",
        "activo": f.get("Activo") if f.get("Activo") is not None else True,
        "created_at": f.get("Created_At") or "",
        "updated_at": f.get("Updated_At") or "",
    }


def _unmap_lote_mapa(rec: dict) -> dict:
    """Airtable LotesMapa → frontend lowercase."""
    f = rec.get("fields", rec)
    rec_id = rec.get("id") or f.get("id", "")
    proyecto_ids = f.get("Proyecto") or []
    contrato_ids = f.get("Contratos") or []
    return {
        "id": rec_id,
        "numero_lote": f.get("Numero_Lote") or "",
        "manzana": f.get("Manzana") or "",
        "estado": f.get("Estado") or "disponible",
        "coord_x": f.get("Coord_X") or None,
        "coord_y": f.get("Coord_Y") or None,
        "precio": f.get("Precio") or None,
        "proyecto_id": proyecto_ids[0] if isinstance(proyecto_ids, list) and proyecto_ids else (proyecto_ids or None),
        "contrato_id": contrato_ids[0] if isinstance(contrato_ids, list) and contrato_ids else (contrato_ids or None),
        "created_at": f.get("Created_At") or "",
        "updated_at": f.get("Updated_At") or "",
    }


def _unmap_propietario(rec: dict) -> dict:
    """Airtable Propietarios → frontend lowercase."""
    f = rec.get("fields", rec)
    rec_id = rec.get("id") or f.get("id", "")
    return {
        "id": rec_id,
        "nombre": f.get("Nombre") or "",
        "telefono": f.get("Telefono") or "",
        "email": f.get("Email") or "",
        "dni_cuit": f.get("DNI_CUIT") or "",
        "direccion": f.get("Direccion") or "",
        "comision_pactada": f.get("Comision_Pactada") or None,
        "cantidad_propiedades": f.get("Cantidad_Propiedades") or 0,
        "notas": f.get("Notas") or "",
        "created_at": f.get("Created_At") or "",
        "updated_at": f.get("Updated_At") or "",
    }


def _unmap_asesor(rec: dict) -> dict:
    """Airtable Asesores → frontend lowercase."""
    f = rec.get("fields", rec)
    rec_id = rec.get("id") or f.get("id", "")
    return {
        "id": rec_id,
        "nombre": f.get("Nombre") or "",
        "apellido": f.get("Apellido") or "",
        "email": f.get("Email") or "",
        "telefono": f.get("Telefono") or "",
        "foto_url": f.get("Foto_URL") or "",
        "rol": f.get("Rol") or "asesor",
        "comision_pct": f.get("Comision_Pct") or None,
        "activo": f.get("Activo") if f.get("Activo") is not None else True,
        "notas": f.get("Notas") or "",
        "created_at": f.get("Created_At") or "",
        "updated_at": f.get("Updated_At") or "",
    }


def _unmap_inmueble_renta(rec: dict) -> dict:
    """Airtable InmueblesRenta → frontend lowercase.
    Invierte _map_inmueble_renta: Precio_Mensual→precio_alquiler, Estado→disponible.
    """
    f = rec.get("fields", rec)
    rec_id = rec.get("id") or f.get("id", "")
    prop_ids = f.get("Propietario") or []
    prop_id = (prop_ids[0] if isinstance(prop_ids, list) and prop_ids else (prop_ids or None))
    estado_at = f.get("Estado") or "disponible"
    return {
        "id": rec_id,
        "titulo": f.get("Titulo") or "",
        "tipo": f.get("Tipo") or "",
        "direccion": f.get("Direccion") or "",
        "ciudad": f.get("Ciudad") or "",
        "barrio": f.get("Barrio") or "",
        "zona": f.get("Zona") or f.get("Ciudad") or "",
        "dormitorios": f.get("Dormitorios") or None,
        "banios": f.get("Banios") or None,
        "metros_cubiertos": f.get("Metros_Cubiertos") or None,
        "metros_terreno": f.get("Metros_Terreno") or None,
        "amoblado": f.get("Amoblado") or False,
        "permite_mascotas": f.get("Permite_Mascotas") or False,
        "precio_alquiler": f.get("Precio_Mensual") or None,
        "precio_mensual": f.get("Precio_Mensual") or None,
        "expensas": f.get("Expensas") or None,
        "moneda": f.get("Moneda") or "ARS",
        "comision_pct": f.get("Comision_Pct") or None,
        "deposito_meses": f.get("Deposito_Meses") or None,
        "disponible": estado_at in ("disponible", "reservado"),
        "estado": estado_at,
        "disponible_desde": f.get("Disponible_Desde") or "",
        "fecha_disponibilidad": f.get("Disponible_Desde") or "",
        "imagen_url": f.get("Imagen_URL") or "",
        "maps_url": f.get("Maps_URL") or "",
        "descripcion": f.get("Descripcion") or "",
        "notas": f.get("Descripcion") or "",
        "asesor_asignado": f.get("Asesor_Asignado") or "",
        "propietario_id": prop_id,
        "created_at": f.get("Created_At") or "",
        "updated_at": f.get("Updated_At") or "",
    }


def _unmap_inquilino(rec: dict) -> dict:
    """Airtable Inquilinos → frontend lowercase."""
    f = rec.get("fields", rec)
    rec_id = rec.get("id") or f.get("id", "")
    return {
        "id": rec_id,
        "nombre": f.get("Nombre") or "",
        "apellido": f.get("Apellido") or "",
        "telefono": f.get("Telefono") or "",
        "email": f.get("Email") or "",
        "documento": f.get("DNI_CUIT") or "",
        "dni_cuit": f.get("DNI_CUIT") or "",
        "fecha_nacimiento": f.get("Fecha_Nacimiento") or "",
        "ocupacion": f.get("Ocupacion") or "",
        "ingresos_mensuales": f.get("Ingresos_Mensuales") or None,
        "garante_nombre": f.get("Garante_Nombre") or "",
        "garante_telefono": f.get("Garante_Telefono") or "",
        "garante_dni": f.get("Garante_DNI") or "",
        "garante_tipo": f.get("Garante_Tipo") or "",
        "contacto_emergencia_nombre": f.get("Contacto_Emergencia_Nombre") or "",
        "contacto_emergencia_telefono": f.get("Contacto_Emergencia_Telefono") or "",
        "estado": f.get("Estado") or "activo",
        "notas": f.get("Notas") or "",
        "created_at": f.get("Created_At") or "",
        "updated_at": f.get("Updated_At") or "",
    }


def _unmap_pago_alquiler(rec: dict) -> dict:
    """Airtable PagosAlquiler → frontend lowercase.
    Invierte _map_pago_alquiler: Periodo_Mes + Periodo_Anio → mes_anio string "YYYY-MM".
    Inquilino (linkedRecord) → inquilino_id string.
    """
    f = rec.get("fields", rec)
    rec_id = rec.get("id") or f.get("id", "")
    inq_ids = f.get("Inquilino") or []
    inq_id = (inq_ids[0] if isinstance(inq_ids, list) and inq_ids else (inq_ids or None))
    # Reconstruir mes_anio desde Periodo_Anio + Periodo_Mes
    periodo_mes = f.get("Periodo_Mes")
    periodo_anio = f.get("Periodo_Anio")
    if periodo_anio and periodo_mes:
        mes_anio = f"{int(periodo_anio):04d}-{int(periodo_mes):02d}"
    else:
        mes_anio = ""
    return {
        "id": rec_id,
        "inquilino_id": inq_id,
        "mes_anio": mes_anio,
        "periodo_mes": periodo_mes,
        "periodo_anio": periodo_anio,
        "monto": f.get("Monto_Alquiler") or None,
        "monto_alquiler": f.get("Monto_Alquiler") or None,
        "monto_expensas": f.get("Monto_Expensas") or None,
        "monto_mora": f.get("Monto_Mora") or None,
        "monto_total": f.get("Monto_Total") or None,
        "fecha_vencimiento": f.get("Fecha_Vencimiento") or "",
        "fecha_pago": f.get("Fecha_Pago") or "",
        "metodo": f.get("Metodo_Pago") or "",
        "metodo_pago": f.get("Metodo_Pago") or "",
        "comprobante_url": f.get("Comprobante_URL") or "",
        "estado": f.get("Estado") or "pendiente",
        "moneda": f.get("Moneda") or "ARS",
        "notas": f.get("Notas") or "",
        "created_at": f.get("Created_At") or "",
        "updated_at": f.get("Updated_At") or "",
    }


def _unmap_liquidacion(rec: dict) -> dict:
    """Airtable Liquidaciones → frontend lowercase.
    Invierte _map_liquidacion: Periodo_Mes + Periodo_Anio → mes_anio.
    Propietario (linkedRecord) → propietario_id.
    """
    f = rec.get("fields", rec)
    rec_id = rec.get("id") or f.get("id", "")
    prop_ids = f.get("Propietario") or []
    prop_id = (prop_ids[0] if isinstance(prop_ids, list) and prop_ids else (prop_ids or None))
    periodo_mes = f.get("Periodo_Mes")
    periodo_anio = f.get("Periodo_Anio")
    if periodo_anio and periodo_mes:
        mes_anio = f"{int(periodo_anio):04d}-{int(periodo_mes):02d}"
    else:
        mes_anio = ""
    return {
        "id": rec_id,
        "propietario_id": prop_id,
        "mes_anio": mes_anio,
        "periodo_mes": periodo_mes,
        "periodo_anio": periodo_anio,
        "bruto": f.get("Monto_Bruto") or None,
        "monto_bruto": f.get("Monto_Bruto") or None,
        "comision_agencia": f.get("Comision_Inmobiliaria") or None,
        "comision_inmobiliaria": f.get("Comision_Inmobiliaria") or None,
        "neto_propietario": f.get("Monto_Neto") or None,
        "monto_neto": f.get("Monto_Neto") or None,
        "moneda": f.get("Moneda") or "ARS",
        "metodo_transferencia": f.get("Metodo_Transferencia") or "",
        "cbu_destino": f.get("CBU_Destino") or "",
        "fecha_liquidacion": f.get("Fecha_Liquidacion") or "",
        "comprobante_url": f.get("Comprobante_URL") or "",
        "estado": f.get("Estado") or "pendiente",
        "notas": f.get("Notas") or "",
        "created_at": f.get("Created_At") or "",
        "updated_at": f.get("Updated_At") or "",
    }


def _unmap_clientes_activos(rec: dict) -> dict:
    """Airtable CLIENTES_ACTIVOS → frontend lowercase.
    Campos usados por /crm/clientes (que alimenta el panel de Clientes Activos
    y el cache de clientes en Loteos para cruzar propiedad asignada).
    """
    f = rec.get("fields", rec)
    rec_id = rec.get("id") or f.get("id", "")
    asesor_ids = f.get("Asesor_Asignado") or []
    asesor_id = (asesor_ids[0] if isinstance(asesor_ids, list) and asesor_ids else (asesor_ids or None))
    return {
        "id": rec_id,
        "nombre": f.get("Nombre") or "",
        "apellido": f.get("Apellido") or "",
        "telefono": f.get("Telefono") or "",
        "email": f.get("Email") or "",
        "documento": f.get("Documento") or "",
        "ciudad": f.get("Ciudad") or "",
        "propiedad": f.get("Propiedad") or "",
        "cuotas_total": f.get("Cuotas_Total") or 0,
        "cuotas_pagadas": f.get("Cuotas_Pagadas") or 0,
        "monto_cuota": f.get("Monto_Cuota") or None,
        "proximo_vencimiento": f.get("Proximo_Vencimiento") or "",
        "estado_pago": f.get("Estado_Pago") or "",
        "notas": f.get("Notas") or "",
        "fecha_alta": f.get("Fecha_Alta") or "",
        "roles": f.get("Roles") or [],
        "origen_creacion": f.get("Origen_Creacion") or "",
        "asesor_asignado_id": asesor_id,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS DE MAPEO snake_case → PascalCase Airtable
# El JS del CRM envía campos en snake_case; Airtable espera exactamente el
# nombre del campo tal como está definido en la base (PascalCase con _).
# Estos mappers aplican la conversión + manejan campos con nombres distintos.
# Los campos no reconocidos se pasan tal cual (permite que ya vengan en AT-format).
# ═══════════════════════════════════════════════════════════════════════════════

def _map_loteo(campos: dict) -> dict:
    """JS → Airtable para tabla Loteos."""
    MAPPING = {
        "nombre":          "Nombre",
        "slug":            "Slug",
        "descripcion":     "Descripcion",
        "ubicacion":       "Ubicacion",
        "ciudad":          "Ciudad",
        "mapa_svg_url":    "Mapa_SVG_URL",
        "total_lotes":     "Total_Lotes",
        "lotes_disponibles": "Lotes_Disponibles",
        "lotes_reservados":  "Lotes_Reservados",
        "lotes_vendidos":    "Lotes_Vendidos",
        "precio_desde":    "Precio_Desde",
        "moneda":          "Moneda",
        "activo":          "Activo",
    }
    return {MAPPING.get(k, k): v for k, v in campos.items() if v is not None and v != ""}


def _map_propietario(campos: dict) -> dict:
    """JS → Airtable para tabla Propietarios."""
    MAPPING = {
        "nombre":            "Nombre",
        "telefono":          "Telefono",
        "email":             "Email",
        "dni_cuit":          "DNI_CUIT",
        "direccion":         "Direccion",
        "comision_pactada":  "Comision_Pactada",
        "cantidad_propiedades": "Cantidad_Propiedades",
        "notas":             "Notas",
    }
    return {MAPPING.get(k, k): v for k, v in campos.items() if v is not None and v != ""}


def _map_asesor(campos: dict) -> dict:
    """JS → Airtable para tabla Asesores."""
    MAPPING = {
        "nombre":        "Nombre",
        "apellido":      "Apellido",
        "email":         "Email",
        "telefono":      "Telefono",
        "foto_url":      "Foto_URL",
        "rol":           "Rol",
        "comision_pct":  "Comision_Pct",
        "activo":        "Activo",
        "notas":         "Notas",
    }
    return {MAPPING.get(k, k): v for k, v in campos.items() if v is not None and v != ""}


def _map_inmueble_renta(campos: dict) -> dict:
    """JS → Airtable para tabla InmueblesRenta.
    Nota: JS envía precio_alquiler, Airtable tiene Precio_Mensual.
          JS envía disponible (bool), Airtable tiene Estado (singleSelect).
          JS envía zona, Airtable no tiene Zona — se ignora (no existe en schema).
          JS envía propietario_id (string), Airtable tiene Propietario (linkedRecord).
    """
    MAPPING = {
        "titulo":             "Titulo",
        "direccion":          "Direccion",
        "ciudad":             "Ciudad",
        "barrio":             "Barrio",
        "tipo":               "Tipo",
        "dormitorios":        "Dormitorios",
        "banios":             "Banios",
        "metros_cubiertos":   "Metros_Cubiertos",
        "metros_terreno":     "Metros_Terreno",
        "amoblado":           "Amoblado",
        "permite_mascotas":   "Permite_Mascotas",
        # nombre distinto
        "precio_alquiler":    "Precio_Mensual",
        "precio_mensual":     "Precio_Mensual",
        "expensas":           "Expensas",
        "moneda":             "Moneda",
        "comision_pct":       "Comision_Pct",
        "deposito_meses":     "Deposito_Meses",
        "disponible_desde":   "Disponible_Desde",
        "fecha_disponibilidad": "Disponible_Desde",
        "imagen_url":         "Imagen_URL",
        "maps_url":           "Maps_URL",
        "descripcion":        "Descripcion",
        "asesor_asignado":    "Asesor_Asignado",
        "notas":              "Descripcion",  # InmueblesRenta no tiene campo Notas propio
    }
    at = {}
    for k, v in campos.items():
        if v is None or v == "":
            continue
        # disponible (bool) → Estado (singleSelect)
        if k == "disponible":
            at["Estado"] = "disponible" if v else "alquilado"
            continue
        # propietario_id (string rec...) → Propietario (linkedRecord array)
        if k == "propietario_id" and v:
            at["Propietario"] = [str(v)] if not isinstance(v, list) else v
            continue
        # zona no existe en InmueblesRenta — descartar silenciosamente
        if k == "zona":
            continue
        dest = MAPPING.get(k, k)
        at[dest] = v
    return at


def _map_inquilino(campos: dict) -> dict:
    """JS → Airtable para tabla Inquilinos (tabla de datos puros del inquilino).
    inmueble_renta_id no existe en Inquilinos — se descarta (va al contrato).
    """
    MAPPING = {
        "nombre":                      "Nombre",
        "apellido":                    "Apellido",
        "telefono":                    "Telefono",
        "email":                       "Email",
        "documento":                   "DNI_CUIT",
        "dni_cuit":                    "DNI_CUIT",
        "fecha_nacimiento":            "Fecha_Nacimiento",
        "ocupacion":                   "Ocupacion",
        "ingresos_mensuales":          "Ingresos_Mensuales",
        "garante_nombre":              "Garante_Nombre",
        "garante_telefono":            "Garante_Telefono",
        "garante_dni":                 "Garante_DNI",
        "garante_tipo":                "Garante_Tipo",
        "contacto_emergencia_nombre":  "Contacto_Emergencia_Nombre",
        "contacto_emergencia_telefono":"Contacto_Emergencia_Telefono",
        "estado":                      "Estado",
        "notas":                       "Notas",
    }
    IGNORAR = {"inmueble_renta_id", "fecha_inicio", "fecha_fin",
               "monto_alquiler_actual", "monto_cuota", "monto_mensual"}
    return {MAPPING.get(k, k): v for k, v in campos.items()
            if v is not None and v != "" and k not in IGNORAR}


def _map_pago_alquiler(campos: dict) -> dict:
    """JS → Airtable para tabla PagosAlquiler.
    JS envía mes_anio (str "2024-03"), Airtable tiene Periodo_Mes + Periodo_Anio separados.
    JS envía monto → Monto_Alquiler (campo principal).
    JS envía inquilino_id (string rec...) → Inquilino (linkedRecord).
    """
    MAPPING = {
        "monto":              "Monto_Alquiler",
        "monto_alquiler":     "Monto_Alquiler",
        "monto_expensas":     "Monto_Expensas",
        "monto_mora":         "Monto_Mora",
        "monto_total":        "Monto_Total",
        "fecha_vencimiento":  "Fecha_Vencimiento",
        "fecha_pago":         "Fecha_Pago",
        "metodo":             "Metodo_Pago",
        "metodo_pago":        "Metodo_Pago",
        "comprobante_url":    "Comprobante_URL",
        "estado":             "Estado",
        "notas":              "Notas",
    }
    at = {}
    for k, v in campos.items():
        if v is None or v == "":
            continue
        # mes_anio "2024-03" → Periodo_Mes=3, Periodo_Anio=2024
        if k == "mes_anio" and v:
            try:
                parts = str(v).split("-")
                at["Periodo_Anio"] = int(parts[0])
                at["Periodo_Mes"] = int(parts[1])
            except Exception:
                pass
            continue
        # inquilino_id → Inquilino linkedRecord
        if k == "inquilino_id" and v:
            at["Inquilino"] = [str(v)] if not isinstance(v, list) else v
            continue
        dest = MAPPING.get(k, k)
        at[dest] = v
    return at


def _map_liquidacion(campos: dict) -> dict:
    """JS → Airtable para tabla Liquidaciones.
    JS envía mes_anio → Periodo_Mes + Periodo_Anio.
    JS envía bruto → Monto_Bruto; comision_agencia → Comision_Inmobiliaria;
    neto_propietario → Monto_Neto.
    JS envía propietario_id → Propietario (linkedRecord).
    """
    MAPPING = {
        "bruto":               "Monto_Bruto",
        "monto_bruto":         "Monto_Bruto",
        "comision_agencia":    "Comision_Inmobiliaria",
        "comision_inmobiliaria": "Comision_Inmobiliaria",
        "neto_propietario":    "Monto_Neto",
        "monto_neto":          "Monto_Neto",
        "moneda":              "Moneda",
        "metodo_transferencia":"Metodo_Transferencia",
        "cbu_destino":         "CBU_Destino",
        "fecha_liquidacion":   "Fecha_Liquidacion",
        "comprobante_url":     "Comprobante_URL",
        "estado":              "Estado",
        "notas":               "Notas",
    }
    at = {}
    for k, v in campos.items():
        if v is None or v == "":
            continue
        if k == "mes_anio" and v:
            try:
                parts = str(v).split("-")
                at["Periodo_Anio"] = int(parts[0])
                at["Periodo_Mes"] = int(parts[1])
            except Exception:
                pass
            continue
        if k == "propietario_id" and v:
            # IMPORTANTE: Liquidaciones.Propietario linkea a CLIENTES_ACTIVOS
            # (tblpfSE6qkGCV6e99), NO a la tabla Propietarios (tbl7XoZ9NOfkfqQAG).
            # El JS actualmente envía IDs de la tabla Propietarios — descartamos
            # el link para evitar ROW_TABLE_DOES_NOT_MATCH de Airtable.
            # El vínculo se puede establecer desde Clientes Activos cuando corresponda.
            continue
        dest = MAPPING.get(k, k)
        at[dest] = v
    return at


# ═══════════════════════════════════════════════════════════════════════════════
# LOTEOS
# ═══════════════════════════════════════════════════════════════════════════════

def get_all_loteos() -> list[dict]:
    return [_unmap_loteo(r) for r in _at_get_all(TABLE_LOTEOS)]


def create_loteo(campos: dict) -> dict:
    return _at_create(TABLE_LOTEOS, _map_loteo(campos))


def update_loteo(record_id: str, campos: dict) -> bool:
    return _at_update(TABLE_LOTEOS, record_id, _map_loteo(campos))


def delete_loteo(record_id: str) -> bool:
    return _at_delete(TABLE_LOTEOS, record_id)


# ═══════════════════════════════════════════════════════════════════════════════
# LOTES MAPA
# ═══════════════════════════════════════════════════════════════════════════════

def get_lotes_mapa(loteo_id: str = None) -> list[dict]:
    if loteo_id:
        formula = f"FIND('{loteo_id}', ARRAYJOIN({{Proyecto}}, ','))>0"
        recs = _at_filter(TABLE_LOTES_MAPA, formula, max_records=500)
    else:
        recs = _at_get_all(TABLE_LOTES_MAPA)
    return [_unmap_lote_mapa(r) for r in recs]


def create_lote_mapa(campos: dict) -> dict:
    return _at_create(TABLE_LOTES_MAPA, campos)


def update_lote_mapa(record_id: str, campos: dict) -> bool:
    return _at_update(TABLE_LOTES_MAPA, record_id, campos)


def delete_lote_mapa(record_id: str) -> bool:
    return _at_delete(TABLE_LOTES_MAPA, record_id)


# ═══════════════════════════════════════════════════════════════════════════════
# CONTRATOS (tabla v3 — polimórfica)
# Tipo singleSelect: venta | reserva | alquiler | boleto
# Polimorfismo por 3 linkedRecord: Lote_Asignado | Propiedad_Asignada | Inmueble_Asignado
# ═══════════════════════════════════════════════════════════════════════════════

_TIPO_GRANULAR_MAP = {
    "venta_lote": "venta",
    "venta_casa": "venta",
    "venta_terreno": "venta",
    "venta_unidad": "venta",
    "venta": "venta",
    "reserva": "reserva",
    "alquiler": "alquiler",
    "boleto": "boleto",
}


def _at_serialize_contrato(rec: dict) -> dict:
    """Transforma un registro de Contratos a formato compatible con Robert.
    Resuelve polimorfismo: Lote_Asignado / Propiedad_Asignada / Inmueble_Asignado
    → item_tipo + item_id.
    """
    lote_ids = rec.get("Lote_Asignado") or []
    prop_ids = rec.get("Propiedad_Asignada") or []
    inmu_ids = rec.get("Inmueble_Asignado") or []

    if lote_ids:
        item_tipo = "lote"
        item_id = lote_ids[0] if isinstance(lote_ids, list) else lote_ids
    elif prop_ids:
        item_tipo = "propiedad"
        item_id = prop_ids[0] if isinstance(prop_ids, list) else prop_ids
    elif inmu_ids:
        item_tipo = "inmueble_renta"
        item_id = inmu_ids[0] if isinstance(inmu_ids, list) else inmu_ids
    else:
        item_tipo = ""
        item_id = None

    cliente_ids = rec.get("Cliente") or []
    cliente_id = (cliente_ids[0] if isinstance(cliente_ids, list) else cliente_ids) if cliente_ids else None

    return {
        "id": rec.get("id", ""),
        "cliente_activo_id": cliente_id,
        "tipo": rec.get("Tipo", ""),
        "item_tipo": item_tipo,
        "item_id": item_id,
        "item_descripcion": rec.get("Item_Descripcion", ""),
        "monto": rec.get("Monto_Total") or rec.get("Precio") or None,
        "moneda": rec.get("Moneda", "USD"),
        "fecha_firma": rec.get("Fecha_Firma", ""),
        "estado_pago": rec.get("Estado_Pago", ""),
        "cuotas_total": rec.get("Cuotas_Total", 0),
        "cuotas_pagadas": rec.get("Cuotas_Pagadas", 0),
        "monto_cuota": rec.get("Monto_Cuota") or None,
        "proximo_vencimiento": rec.get("Proximo_Vencimiento", ""),
        "notas": rec.get("Notas", ""),
        # Campos originales Airtable para edición
        "Tipo": rec.get("Tipo", ""),
        "Estado_Pago": rec.get("Estado_Pago", ""),
        "Cliente": cliente_ids,
        "Lote_Asignado": lote_ids,
        "Propiedad_Asignada": prop_ids,
        "Inmueble_Asignado": inmu_ids,
        "Item_Descripcion": rec.get("Item_Descripcion", ""),
    }


def get_all_contratos() -> list[dict]:
    recs = _at_get_all(TABLE_CONTRATOS)
    return [_at_serialize_contrato(r) for r in recs]


def create_contrato(campos: dict) -> dict:
    """Creación legacy directa (backward compat). Mapea campos Robert-like a Airtable."""
    at_campos = {}

    tipo_raw = campos.get("tipo") or campos.get("Tipo", "")
    tipo_at = _TIPO_GRANULAR_MAP.get(tipo_raw, tipo_raw)
    if tipo_at:
        at_campos["Tipo"] = tipo_at

    # Item_Descripcion guarda el subtipo granular si viene
    if tipo_raw != tipo_at:
        at_campos["Item_Descripcion"] = tipo_raw
    if campos.get("notas") or campos.get("Notas"):
        at_campos["Item_Descripcion"] = (campos.get("notas") or campos.get("Notas", ""))[:200]

    # linkedRecord cliente
    cliente_id = campos.get("cliente_activo_id") or campos.get("Cliente")
    if cliente_id:
        at_campos["Cliente"] = [str(cliente_id)] if not isinstance(cliente_id, list) else cliente_id

    # linkedRecord item polimórfico
    item_tipo = campos.get("item_tipo", "")
    item_id = campos.get("item_id") or campos.get("Item_Id")
    if item_id:
        if item_tipo == "lote":
            at_campos["Lote_Asignado"] = [str(item_id)] if not isinstance(item_id, list) else item_id
        elif item_tipo == "propiedad":
            at_campos["Propiedad_Asignada"] = [str(item_id)] if not isinstance(item_id, list) else item_id
        elif item_tipo == "inmueble_renta":
            at_campos["Inmueble_Asignado"] = [str(item_id)] if not isinstance(item_id, list) else item_id

    for src, dst in [
        ("fecha_firma", "Fecha_Firma"), ("Fecha_Firma", "Fecha_Firma"),
        ("moneda", "Moneda"), ("Moneda", "Moneda"),
        ("estado_pago", "Estado_Pago"),
        ("cuotas_total", "Cuotas_Total"),
        ("cuotas_pagadas", "Cuotas_Pagadas"),
        ("monto_cuota", "Monto_Cuota"),
        ("proximo_vencimiento", "Proximo_Vencimiento"),
    ]:
        if campos.get(src) is not None and dst not in at_campos:
            at_campos[dst] = campos[src]

    rec = _at_create(TABLE_CONTRATOS, at_campos)
    if "error" not in rec:
        return _at_serialize_contrato(rec)
    return rec


def update_contrato(record_id: str, campos: dict) -> bool:
    # Mapear campos lowercase a Airtable PascalCase si llegan así
    at = {}
    mapping = {
        "tipo": "Tipo", "estado_pago": "Estado_Pago",
        "fecha_firma": "Fecha_Firma", "moneda": "Moneda",
        "cuotas_total": "Cuotas_Total", "cuotas_pagadas": "Cuotas_Pagadas",
        "monto_cuota": "Monto_Cuota", "proximo_vencimiento": "Proximo_Vencimiento",
        "notas": "Item_Descripcion",
    }
    for k, v in campos.items():
        dest = mapping.get(k, k)
        at[dest] = v
    return _at_update(TABLE_CONTRATOS, record_id, at)


def delete_contrato(record_id: str) -> bool:
    return _at_delete(TABLE_CONTRATOS, record_id)


def get_contratos_by_cliente(cliente_id: str) -> dict:
    """Lista contratos de un CLIENTES_ACTIVOS por su record ID."""
    formula = f"FIND('{cliente_id}', ARRAYJOIN({{Cliente}}, ','))>0"
    recs = _at_filter(TABLE_CONTRATOS, formula, max_records=100)
    items = [_at_serialize_contrato(r) for r in recs]
    return {"items": items, "total": len(items)}


# ═══════════════════════════════════════════════════════════════════════════════
# INMUEBLES RENTA
# ═══════════════════════════════════════════════════════════════════════════════

def _serialize_inmueble(rec: dict) -> dict:
    """Alias de _unmap_inmueble_renta — unificado para GET responses."""
    return _unmap_inmueble_renta(rec)


def get_all_inmuebles_renta() -> list[dict]:
    recs = _at_get_all(TABLE_INMUEBLES_RENTA)
    return [_unmap_inmueble_renta(r) for r in recs]


def create_inmueble_renta(campos: dict) -> dict:
    rec = _at_create(TABLE_INMUEBLES_RENTA, _map_inmueble_renta(campos))
    return _unmap_inmueble_renta(rec) if "error" not in rec else rec


def update_inmueble_renta(record_id: str, campos: dict) -> bool:
    return _at_update(TABLE_INMUEBLES_RENTA, record_id, _map_inmueble_renta(campos))


def delete_inmueble_renta(record_id: str) -> bool:
    return _at_delete(TABLE_INMUEBLES_RENTA, record_id)


# ═══════════════════════════════════════════════════════════════════════════════
# INQUILINOS (tabla legacy — se mantiene para compatibilidad)
# ═══════════════════════════════════════════════════════════════════════════════

def get_all_inquilinos(inmueble_id: str = None) -> list[dict]:
    if inmueble_id:
        formula = f"FIND('{inmueble_id}', ARRAYJOIN({{Inmueble}}, ','))>0"
        recs = _at_filter(TABLE_INQUILINOS, formula)
    else:
        recs = _at_get_all(TABLE_INQUILINOS)
    return [_unmap_inquilino(r) for r in recs]


def create_inquilino(campos: dict) -> dict:
    return _at_create(TABLE_INQUILINOS, _map_inquilino(campos))


def update_inquilino(record_id: str, campos: dict) -> bool:
    return _at_update(TABLE_INQUILINOS, record_id, _map_inquilino(campos))


def delete_inquilino(record_id: str) -> bool:
    return _at_delete(TABLE_INQUILINOS, record_id)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGOS ALQUILER
# ═══════════════════════════════════════════════════════════════════════════════

def get_all_pagos_alquiler(inquilino_id: str = None, mes_anio: str = None) -> list[dict]:
    filtros = []
    if inquilino_id:
        filtros.append(f"FIND('{inquilino_id}', ARRAYJOIN({{Inquilino}}, ','))>0")
    if mes_anio:
        filtros.append(f"{{Mes_Anio}}='{mes_anio}'")
    if filtros:
        formula = "AND(" + ",".join(filtros) + ")" if len(filtros) > 1 else filtros[0]
        recs = _at_filter(TABLE_PAGOS_ALQUILER, formula)
    else:
        recs = _at_get_all(TABLE_PAGOS_ALQUILER)
    return [_unmap_pago_alquiler(r) for r in recs]


def create_pago_alquiler(campos: dict) -> dict:
    return _at_create(TABLE_PAGOS_ALQUILER, _map_pago_alquiler(campos))


def update_pago_alquiler(record_id: str, campos: dict) -> bool:
    return _at_update(TABLE_PAGOS_ALQUILER, record_id, _map_pago_alquiler(campos))


def delete_pago_alquiler(record_id: str) -> bool:
    return _at_delete(TABLE_PAGOS_ALQUILER, record_id)


# ═══════════════════════════════════════════════════════════════════════════════
# LIQUIDACIONES
# ═══════════════════════════════════════════════════════════════════════════════

def get_all_liquidaciones(propietario_id: str = None, mes_anio: str = None) -> list[dict]:
    filtros = []
    if propietario_id:
        filtros.append(f"FIND('{propietario_id}', ARRAYJOIN({{Propietario}}, ','))>0")
    if mes_anio:
        filtros.append(f"{{Mes_Anio}}='{mes_anio}'")
    if filtros:
        formula = "AND(" + ",".join(filtros) + ")" if len(filtros) > 1 else filtros[0]
        recs = _at_filter(TABLE_LIQUIDACIONES, formula)
    else:
        recs = _at_get_all(TABLE_LIQUIDACIONES)
    return [_unmap_liquidacion(r) for r in recs]


def create_liquidacion(campos: dict) -> dict:
    return _at_create(TABLE_LIQUIDACIONES, _map_liquidacion(campos))


def update_liquidacion(record_id: str, campos: dict) -> bool:
    return _at_update(TABLE_LIQUIDACIONES, record_id, _map_liquidacion(campos))


def delete_liquidacion(record_id: str) -> bool:
    return _at_delete(TABLE_LIQUIDACIONES, record_id)


# ═══════════════════════════════════════════════════════════════════════════════
# VISITAS
# ═══════════════════════════════════════════════════════════════════════════════

def get_all_visitas() -> list[dict]:
    return _at_get_all(TABLE_VISITAS)


def create_visita(campos: dict) -> dict:
    return _at_create(TABLE_VISITAS, campos)


def update_visita(record_id: str, campos: dict) -> bool:
    return _at_update(TABLE_VISITAS, record_id, campos)


def delete_visita(record_id: str) -> bool:
    return _at_delete(TABLE_VISITAS, record_id)


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


# ═══════════════════════════════════════════════════════════════════════════════
# PERSONA ÚNICA — búsqueda, ficha 360, agregar rol
# Equivalente a las funciones homónimas en db_postgres.py de Robert,
# adaptadas a Airtable (sin transacciones, con linkedRecords).
# ═══════════════════════════════════════════════════════════════════════════════

def buscar_personas(q: str, limit: int = 20) -> dict:
    """Busca en CLIENTES_ACTIVOS por nombre, apellido, teléfono, email o documento.
    Usa filterByFormula con FIND/LOWER — Airtable no tiene ILIKE nativo.
    Retorna {"items": [...]} con hasta `limit` resultados.
    """
    if not _available() or not TABLE_ACTIVOS:
        return {"items": []}
    q_safe = q.replace("'", "\\'")
    formula = (
        f"OR("
        f"FIND(LOWER('{q_safe}'),LOWER({{Nombre}}&''))>0,"
        f"FIND(LOWER('{q_safe}'),LOWER({{Apellido}}&''))>0,"
        f"FIND(LOWER('{q_safe}'),LOWER({{Telefono}}&''))>0,"
        f"FIND(LOWER('{q_safe}'),LOWER({{Email}}&''))>0,"
        f"FIND(LOWER('{q_safe}'),LOWER({{Documento}}&''))>0"
        f")"
    )
    recs = _at_filter(TABLE_ACTIVOS, formula, max_records=limit)
    items = []
    for rec in recs:
        roles = rec.get("Roles") or ["comprador"]
        items.append({
            "id": rec.get("id", ""),
            "nombre": rec.get("Nombre", ""),
            "apellido": rec.get("Apellido", ""),
            "telefono": rec.get("Telefono", ""),
            "email": rec.get("Email", ""),
            "documento": rec.get("Documento", ""),
            "roles": roles,
            "origen_creacion": rec.get("Origen_Creacion", ""),
        })
    return {"items": items}


def get_ficha_persona(cliente_id: str) -> dict:
    """Ficha 360 de una persona en CLIENTES_ACTIVOS.
    Reune: datos base + lead origen + contratos + alquileres ContratosAlquiler + inmuebles propios.

    Sin transacciones — cada llamada Airtable es independiente.
    Si una falla se loguea y se devuelve parcial.
    """
    if not _available() or not TABLE_ACTIVOS:
        return {"error": "Airtable no configurado"}

    # 1. Persona base
    persona_rec = _at_get_one(TABLE_ACTIVOS, cliente_id)
    if not persona_rec:
        return {"error": f"Persona {cliente_id} no encontrada"}

    roles = persona_rec.get("Roles") or ["comprador"]
    lead_origen_ids = persona_rec.get("Lead_Origen") or []

    persona = {
        "id": persona_rec.get("id", ""),
        "nombre": persona_rec.get("Nombre", ""),
        "apellido": persona_rec.get("Apellido", ""),
        "telefono": persona_rec.get("Telefono", ""),
        "email": persona_rec.get("Email", ""),
        "documento": persona_rec.get("Documento", ""),
        "roles": roles,
        "origen_creacion": persona_rec.get("Origen_Creacion", ""),
        "ciudad": persona_rec.get("Ciudad", ""),
        # IDs de links inversos (Airtable los expone en el registro)
        "contratos_ids": persona_rec.get("Contratos") or [],
        "visitas_ids": persona_rec.get("Visitas") or [],
    }

    # 2. Lead origen (linkedRecord a tabla Clientes)
    lead_origen = None
    if lead_origen_ids:
        lead_id = lead_origen_ids[0] if isinstance(lead_origen_ids, list) else lead_origen_ids
        try:
            lead_rec = _at_get_one(TABLE_CLIENTES, lead_id)
            if lead_rec:
                lead_origen = {
                    "id": lead_rec.get("id", ""),
                    "nombre": lead_rec.get("Nombre", ""),
                    "telefono": lead_rec.get("Telefono", ""),
                    "estado": lead_rec.get("Estado", ""),
                    "fecha_whatsapp": lead_rec.get("Fecha_WhatsApp", ""),
                }
        except Exception as e:
            logger.warning("[MICA-FICHA] lead origen exc: %s", e)

    # 3. Contratos del cliente — filterByFormula por linkedRecord Cliente
    contratos = []
    try:
        contratos = get_contratos_by_cliente(cliente_id).get("items", [])
    except Exception as e:
        logger.warning("[MICA-FICHA] contratos exc: %s", e)

    # 4. ContratosAlquiler donde Inquilino = este cliente
    alquileres = []
    try:
        formula_alq = f"FIND('{cliente_id}', ARRAYJOIN({{Inquilino}}, ','))>0"
        alq_recs = _at_filter(TABLE_CONTRATOS_ALQUILER, formula_alq, max_records=50)
        for a in alq_recs:
            inmueble_ids = a.get("Inmueble") or []
            contrato_ids = a.get("Contrato") or []
            alquileres.append({
                "id": a.get("id", ""),
                "contrato_id": contrato_ids[0] if contrato_ids else None,
                "inmueble_id": inmueble_ids[0] if inmueble_ids else None,
                "fecha_inicio": a.get("Fecha_Inicio", ""),
                "fecha_fin": a.get("Fecha_Fin", ""),
                "monto_mensual": a.get("Monto_Mensual") or None,
                "estado": a.get("Estado", ""),
                "garante_nombre": a.get("Garante_Nombre", ""),
            })
    except Exception as e:
        logger.warning("[MICA-FICHA] alquileres exc: %s", e)

    # 5. Inmuebles propios — InmueblesRenta donde Propietario = este cliente
    inmuebles_propios = []
    try:
        formula_inm = f"FIND('{cliente_id}', ARRAYJOIN({{Propietario}}, ','))>0"
        inm_recs = _at_filter(TABLE_INMUEBLES_RENTA, formula_inm, max_records=50)
        for inm in inm_recs:
            inmuebles_propios.append({
                "id": inm.get("id", ""),
                "titulo": inm.get("Titulo") or inm.get("Nombre", ""),
                "tipo": inm.get("Tipo", ""),
                "precio_mensual": inm.get("Precio_Mensual") or None,
                "disponible": inm.get("Disponible", True),
            })
    except Exception as e:
        logger.warning("[MICA-FICHA] inmuebles propios exc: %s", e)

    return {
        "persona": persona,
        "lead_origen": lead_origen,
        "contratos": contratos,
        "alquileres": alquileres,
        "inmuebles_propios": inmuebles_propios,
    }


def agregar_rol_persona(cliente_id: str, rol: str) -> dict:
    """Agrega un rol al multiSelect Roles de CLIENTES_ACTIVOS.
    Idempotente — si ya tiene el rol no lo duplica.
    Airtable no tiene array_append nativo: leer → merge → PATCH.
    """
    roles_validos = {"comprador", "inquilino", "propietario"}
    if rol not in roles_validos:
        return {"error": f"Rol inválido: {rol}. Válidos: {roles_validos}"}

    rec = _at_get_one(TABLE_ACTIVOS, cliente_id)
    if not rec:
        return {"error": f"cliente_id {cliente_id} no encontrado"}

    roles_actuales = rec.get("Roles") or []
    if rol in roles_actuales:
        return {"ok": True, "cliente_id": cliente_id, "rol_agregado": rol, "ya_existia": True}

    nuevos_roles = list(roles_actuales) + [rol]
    ok = _at_update(TABLE_ACTIVOS, cliente_id, {"Roles": nuevos_roles})
    if ok:
        return {"ok": True, "cliente_id": cliente_id, "rol_agregado": rol, "roles": nuevos_roles}
    return {"error": "No se pudo actualizar el registro en Airtable"}


# ═══════════════════════════════════════════════════════════════════════════════
# CONTRATO UNIFICADO v3 — 3 ramas de cliente + polimorfismo de item
# Sin transacciones — si un paso falla se loguea y se retorna parcial.
# ═══════════════════════════════════════════════════════════════════════════════

def crear_contrato_unificado(payload: dict) -> dict:
    """
    Endpoint unificado de contrato para Airtable.
    Acepta exactamente UNA opción de cliente:
      A) cliente_activo_id: str (rec...)  → usar cliente existente en CLIENTES_ACTIVOS
      B) convertir_lead_id: str (rec...)  → convierte lead de tabla Clientes a CLIENTES_ACTIVOS
      C) cliente_nuevo: dict              → crea cliente directo en CLIENTES_ACTIVOS

    Sin transacciones — si un paso falla se loguea y se devuelve estado parcial.
    El frontend puede reintentar.

    Retorna: {ok, cliente_activo_id, contrato_id, origen_creacion, item_actualizado}
    """
    if not _available():
        return {"error": "Airtable no configurado"}

    opcion_a = payload.get("cliente_activo_id")
    opcion_b = payload.get("convertir_lead_id")
    opcion_c = payload.get("cliente_nuevo")
    opciones = sum([bool(opcion_a), bool(opcion_b), bool(opcion_c)])

    if opciones != 1:
        return {"error": "Debe venir exactamente una opción: cliente_activo_id, convertir_lead_id o cliente_nuevo"}

    tipo = payload.get("tipo")
    if not tipo:
        return {"error": "Campo 'tipo' es obligatorio"}

    item_tipo = payload.get("item_tipo", "")
    item_id = payload.get("item_id")
    log = []

    # ── Resolver cliente ─────────────────────────────────────────────────────
    cliente_activo_id = None
    origen_creacion = "manual_directo"

    if opcion_a:
        rec = _at_get_one(TABLE_ACTIVOS, opcion_a)
        if not rec:
            return {"error": f"cliente_activo_id={opcion_a} no encontrado en CLIENTES_ACTIVOS"}
        cliente_activo_id = opcion_a
        log.append(f"Usando cliente existente {cliente_activo_id}")

    elif opcion_b:
        lead_rec = _at_get_one(TABLE_CLIENTES, opcion_b)
        if not lead_rec:
            return {"error": f"convertir_lead_id={opcion_b} no encontrado en tabla Clientes"}

        # Crear cliente activo copiando datos del lead
        at_campos_nuevo = {
            "Nombre": lead_rec.get("Nombre", ""),
            "Apellido": lead_rec.get("Apellido", ""),
            "Telefono": lead_rec.get("Telefono", ""),
            "Email": lead_rec.get("Email", ""),
            "Ciudad": lead_rec.get("Ciudad", ""),
            "Origen_Creacion": "lead_convertido",
            "Lead_Origen": [opcion_b],
        }
        nuevo_rec = _at_create(TABLE_ACTIVOS, at_campos_nuevo)
        if "error" in nuevo_rec:
            return {"error": f"No se pudo crear cliente desde lead: {nuevo_rec['error']}"}
        cliente_activo_id = nuevo_rec["id"]
        origen_creacion = "lead_convertido"
        log.append(f"Lead {opcion_b} convertido a cliente {cliente_activo_id}")

        # Marcar lead como cerrado_ganado (no hay rollback si falla)
        _patch_lead(opcion_b, {"Estado": "cerrado_ganado"})

    elif opcion_c:
        cnuevo = opcion_c
        origen = payload.get("origen_creacion", "manual_directo")
        at_campos_nuevo = {
            "Nombre": cnuevo.get("nombre", ""),
            "Apellido": cnuevo.get("apellido", ""),
            "Telefono": cnuevo.get("telefono", ""),
            "Email": cnuevo.get("email", ""),
            "Documento": cnuevo.get("documento", ""),
            "Origen_Creacion": origen,
        }
        nuevo_rec = _at_create(TABLE_ACTIVOS, at_campos_nuevo)
        if "error" in nuevo_rec:
            return {"error": f"No se pudo crear cliente: {nuevo_rec['error']}"}
        cliente_activo_id = nuevo_rec["id"]
        origen_creacion = origen
        log.append(f"Nuevo cliente {cliente_activo_id} creado (origen={origen})")

    # ── Crear contrato ────────────────────────────────────────────────────────
    tipo_at = _TIPO_GRANULAR_MAP.get(tipo, tipo)
    item_descripcion = payload.get("item_descripcion", "")
    if tipo != tipo_at and not item_descripcion:
        # Guardar subtipo granular en Item_Descripcion
        item_descripcion = tipo

    at_contrato = {
        "Tipo": tipo_at,
        "Cliente": [cliente_activo_id],
    }
    if item_descripcion:
        at_contrato["Item_Descripcion"] = item_descripcion

    # linkedRecord item polimórfico
    if item_id:
        if item_tipo == "lote":
            at_contrato["Lote_Asignado"] = [str(item_id)] if not isinstance(item_id, list) else item_id
        elif item_tipo == "propiedad":
            at_contrato["Propiedad_Asignada"] = [str(item_id)] if not isinstance(item_id, list) else item_id
        elif item_tipo == "inmueble_renta":
            at_contrato["Inmueble_Asignado"] = [str(item_id)] if not isinstance(item_id, list) else item_id

    for src, dst in [
        ("fecha_firma", "Fecha_Firma"),
        ("moneda", "Moneda"),
        ("estado_pago", "Estado_Pago"),
        ("cuotas_total", "Cuotas_Total"),
        ("cuotas_pagadas", "Cuotas_Pagadas"),
        ("monto_cuota", "Monto_Cuota"),
        ("proximo_vencimiento", "Proximo_Vencimiento"),
    ]:
        v = payload.get(src) or payload.get("monto_total" if src == "monto_total" else src)
        if v is not None:
            at_contrato[dst] = v

    contrato_rec = _at_create(TABLE_CONTRATOS, at_contrato)
    if "error" in contrato_rec:
        return {
            "error": f"Cliente creado ({cliente_activo_id}) pero contrato falló: {contrato_rec['error']}",
            "cliente_activo_id": cliente_activo_id,
            "log": log,
        }
    contrato_id = contrato_rec["id"]
    log.append(f"Contrato {contrato_id} creado (tipo={tipo_at}, item={item_tipo}/{item_id})")

    # ── Actualizar item según tipo ────────────────────────────────────────────
    item_actualizado = False
    if item_id:
        try:
            if item_tipo == "lote":
                item_actualizado = _at_update(TABLE_LOTES_MAPA, str(item_id), {
                    "Estado": "vendido",
                    "Cliente_Activo": [cliente_activo_id],
                })
            elif item_tipo == "propiedad":
                item_actualizado = _at_update(TABLE_PROPS, str(item_id), {"Disponible": "No Disponible"})
            elif item_tipo == "inmueble_renta":
                item_actualizado = _at_update(TABLE_INMUEBLES_RENTA, str(item_id), {"Disponible": False})
            log.append(f"Item {item_tipo}/{item_id} actualizado={item_actualizado}")
        except Exception as e:
            logger.warning("[MICA-CONTRATO] update item exc: %s", e)
            log.append(f"WARNING: update item falló: {e}")

    return {
        "ok": True,
        "cliente_activo_id": cliente_activo_id,
        "contrato_id": contrato_id,
        "origen_creacion": origen_creacion,
        "item_actualizado": item_actualizado,
        "log": log,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# CONTRATO ALQUILER — crea Contratos + ContratosAlquiler + actualiza inmueble
# ═══════════════════════════════════════════════════════════════════════════════

def crear_contrato_alquiler(campos: dict) -> dict:
    """Crea contrato tipo alquiler en 4 pasos secuenciales sin transacción:
    1. Crear registro en Contratos
    2. Crear registro en ContratosAlquiler
    3. Marcar InmueblesRenta como no disponible
    4. Agregar rol 'inquilino' al cliente

    Si un paso falla: loguea warning y retorna estado parcial.
    """
    if not _available():
        return {"error": "Airtable no configurado"}

    alquiler_data = campos.get("alquiler") or {}
    cliente_activo_id = campos.get("cliente_activo_id")
    item_id = campos.get("item_id")

    if not cliente_activo_id or not item_id:
        return {"error": "Faltan cliente_activo_id o item_id"}

    log = []

    # Paso 1: Crear contrato base en tabla Contratos
    at_contrato = {
        "Tipo": "alquiler",
        "Cliente": [cliente_activo_id],
        "Inmueble_Asignado": [str(item_id)],
        "Estado_Pago": "al_dia",
    }
    if campos.get("fecha_firma"):
        at_contrato["Fecha_Firma"] = campos["fecha_firma"]
    if campos.get("moneda"):
        at_contrato["Moneda"] = campos["moneda"]
    if campos.get("notas"):
        at_contrato["Item_Descripcion"] = campos["notas"][:200]
    monto = campos.get("monto_total") or alquiler_data.get("monto_mensual")
    if monto:
        at_contrato["Monto_Cuota"] = monto

    contrato_rec = _at_create(TABLE_CONTRATOS, at_contrato)
    if "error" in contrato_rec:
        return {"error": f"Paso 1 falló (crear Contratos): {contrato_rec['error']}"}
    contrato_id = contrato_rec["id"]
    log.append(f"Contrato {contrato_id} creado")

    # Paso 2: Crear ContratosAlquiler
    alquiler_id = None
    at_alquiler = {
        "Contrato": [contrato_id],
        "Inquilino": [cliente_activo_id],
        "Inmueble": [str(item_id)],
        "Estado": "vigente",
    }
    for src, dst in [
        ("fecha_inicio", "Fecha_Inicio"), ("fecha_fin", "Fecha_Fin"),
        ("monto_mensual", "Monto_Mensual"), ("deposito_pagado", "Deposito_Pagado"),
        ("garante_nombre", "Garante_Nombre"), ("garante_telefono", "Garante_Telefono"),
        ("garante_dni", "Garante_DNI"),
    ]:
        if alquiler_data.get(src) is not None:
            at_alquiler[dst] = alquiler_data[src]

    alq_rec = _at_create(TABLE_CONTRATOS_ALQUILER, at_alquiler)
    if "error" in alq_rec:
        logger.warning("[MICA-ALQ] Paso 2 falló (ContratosAlquiler): %s", alq_rec["error"])
        log.append(f"WARNING Paso 2: {alq_rec['error']}")
    else:
        alquiler_id = alq_rec["id"]
        log.append(f"ContratosAlquiler {alquiler_id} creado")

    # Paso 3: Marcar inmueble no disponible
    ok3 = _at_update(TABLE_INMUEBLES_RENTA, str(item_id), {"Disponible": False})
    if not ok3:
        logger.warning("[MICA-ALQ] Paso 3 falló (update InmueblesRenta)")
        log.append("WARNING Paso 3: inmueble no actualizado")
    else:
        log.append(f"InmueblesRenta {item_id} marcado no disponible")

    # Paso 4: Agregar rol 'inquilino' al cliente
    rol_res = agregar_rol_persona(cliente_activo_id, "inquilino")
    if "error" in rol_res:
        logger.warning("[MICA-ALQ] Paso 4 falló (agregar rol): %s", rol_res["error"])
        log.append(f"WARNING Paso 4: {rol_res['error']}")
    else:
        log.append("Rol inquilino agregado")

    return {
        "ok": True,
        "contrato_id": contrato_id,
        "alquiler_id": alquiler_id,
        "cliente_activo_id": cliente_activo_id,
        "item_id": item_id,
        "log": log,
    }


def get_all_alquileres() -> dict:
    """Lista todos los ContratosAlquiler con datos de inmueble y cliente."""
    recs = _at_get_all(TABLE_CONTRATOS_ALQUILER)
    items = []
    for a in recs:
        inmueble_ids = a.get("Inmueble") or []
        inquilino_ids = a.get("Inquilino") or []
        contrato_ids = a.get("Contrato") or []
        items.append({
            "id": a.get("id", ""),
            "contrato_id": contrato_ids[0] if contrato_ids else None,
            "inmueble_id": inmueble_ids[0] if inmueble_ids else None,
            "cliente_id": inquilino_ids[0] if inquilino_ids else None,
            "fecha_inicio": a.get("Fecha_Inicio", ""),
            "fecha_fin": a.get("Fecha_Fin", ""),
            "monto_mensual": a.get("Monto_Mensual") or None,
            "deposito_pagado": a.get("Deposito_Pagado") or None,
            "estado": a.get("Estado", ""),
            "garante_nombre": a.get("Garante_Nombre", ""),
            "garante_telefono": a.get("Garante_Telefono", ""),
            "garante_dni": a.get("Garante_DNI", ""),
        })
    return {"items": items, "total": len(items)}
