import os
import re
import json
import requests as req
from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Optional, List, Dict

router = APIRouter(prefix="/crm", tags=["CRM"])

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# ── Config Airtable por cliente ────────────────────────────────────────────────
AIRTABLE_API_KEY = os.environ.get("AIRTABLE_API_KEY", "")
AT_HEADERS = {"Authorization": f"Bearer {AIRTABLE_API_KEY}"}

# IDs de tablas por cliente (fijos — no cambian entre entornos)
_CLIENTES_CONFIG = {
    "maicol": {
        "base_id":        os.environ.get("AIRTABLE_BASE_ID_MAICOL", "appaDT7uwHnimVZLM"),
        "table_props":    "tbly67z1oY8EFQoFj",
        "table_clientes": "tblonoyIMAM5kl2ue",
    },
}

def _get_config(cliente_id: str) -> dict:
    cfg = _CLIENTES_CONFIG.get(cliente_id)
    if not cfg:
        raise ValueError(f"cliente_id '{cliente_id}' no encontrado")
    return cfg

def _at_get_all(base_id: str, table_id: str) -> list:
    """Trae todos los registros de una tabla Airtable con paginación."""
    url = f"https://api.airtable.com/v0/{base_id}/{table_id}"
    records, offset = [], None
    while True:
        params = {"pageSize": 100}
        if offset:
            params["offset"] = offset
        r = req.get(url, headers=AT_HEADERS, params=params, timeout=10)
        data = r.json()
        records += [{"id": rec["id"], **rec["fields"]} for rec in data.get("records", [])]
        offset = data.get("offset")
        if not offset:
            break
    return records


# ── Endpoints Airtable CRM (multi-cliente) ────────────────────────────────────

@router.get("/propiedades")
def crm_propiedades(cliente_id: str = Query("maicol")):
    """Propiedades de Airtable para el dashboard CRM."""
    try:
        cfg = _get_config(cliente_id)
        return {"records": _at_get_all(cfg["base_id"], cfg["table_props"])}
    except ValueError as e:
        return {"error": str(e)}


@router.get("/clientes")
def crm_clientes(cliente_id: str = Query("maicol")):
    """Leads/clientes de Airtable para el dashboard CRM."""
    try:
        cfg = _get_config(cliente_id)
        return {"records": _at_get_all(cfg["base_id"], cfg["table_clientes"])}
    except ValueError as e:
        return {"error": str(e)}
GEMINI_TEXT_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

ETAPAS_PIPELINE = [
    "nuevo",
    "contactado",
    "propuesta_enviada",
    "negociacion",
    "cerrado_ganado",
    "cerrado_perdido"
]


class DatosCalificarLead(BaseModel):
    nombre: Optional[str] = ""
    empresa: Optional[str] = ""
    industria: Optional[str] = ""
    mensaje_inicial: Optional[str] = ""
    fuente: Optional[str] = ""  # instagram, whatsapp, referido, web, etc.
    historial_interacciones: Optional[List[str]] = []
    presupuesto_indicado: Optional[str] = ""
    cantidad_empleados: Optional[str] = ""


class DatosEnriquecerLead(BaseModel):
    datos_actuales: Dict
    contexto_conversacion: Optional[str] = ""


class DatosGenerarSeguimiento(BaseModel):
    lead: Dict
    etapa_pipeline: str
    dias_sin_respuesta: Optional[int] = 0
    ultimo_contacto: Optional[str] = ""
    brandbook: Optional[Dict] = {}


def _call_gemini_text(prompt: str, timeout: int = 30) -> str:
    resp = req.post(
        f"{GEMINI_TEXT_URL}?key={GEMINI_API_KEY}",
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=timeout
    )
    resp.raise_for_status()
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"]


def _parse_json_from_text(texto: str) -> dict:
    """Extrae el primer JSON válido del texto de Gemini."""
    match = re.search(r'\{[\s\S]*\}', texto)
    if not match:
        raise ValueError("No se encontró JSON en la respuesta.")
    return json.loads(match.group(0))


# ---------------------------------------------------------------------------
# POST /crm/calificar-lead
# ---------------------------------------------------------------------------
@router.post("/calificar-lead")
async def calificar_lead(entrada: DatosCalificarLead):
    """
    Score IA del lead con temperatura de venta, urgencia y siguiente acción recomendada.
    Entrada: datos del lead (nombre, empresa, mensaje inicial, historial).
    Salida: {status, temperatura, score, potencial_negocio, urgencia_compra,
             objeciones_probables, siguiente_accion, razonamiento}
    """
    if not GEMINI_API_KEY:
        return {"status": "error", "mensaje": "Falta GEMINI_API_KEY."}

    historial_str = "\n".join(f"- {h}" for h in entrada.historial_interacciones[-5:]) \
        if entrada.historial_interacciones else "Sin historial registrado."

    prompt = f"""Eres un experto en ventas B2B de servicios de automatización IA para LATAM (Argentina, México, Colombia, etc.).
Analiza este lead y califícalo con criterio comercial real.

DATOS DEL LEAD:
- Nombre: {entrada.nombre or "No proporcionado"}
- Empresa: {entrada.empresa or "No proporcionado"}
- Industria: {entrada.industria or "No proporcionado"}
- Fuente de entrada: {entrada.fuente or "No especificada"}
- Empleados: {entrada.cantidad_empleados or "No especificado"}
- Presupuesto indicado: {entrada.presupuesto_indicado or "No mencionado"}
- Mensaje inicial: {entrada.mensaje_inicial or "Sin mensaje"}
- Historial de interacciones:
{historial_str}

Responde SOLO con este JSON exacto:
{{
  "temperatura": "[frio/tibio/caliente]",
  "score": [número entero del 1 al 10],
  "potencial_negocio": "[bajo/medio/alto]",
  "urgencia_compra": "[sin_urgencia/explorando/evaluando/listo_para_comprar]",
  "objeciones_probables": ["objecion1", "objecion2"],
  "siguiente_accion": "Acción específica y concreta a tomar ahora",
  "razonamiento": "Por qué este score en máximo 2 oraciones"
}}"""

    try:
        texto = _call_gemini_text(prompt, timeout=30)
        parsed = _parse_json_from_text(texto)
        return {"status": "success", **parsed}
    except Exception as e:
        return {"status": "error", "mensaje": f"Error calificando lead: {str(e)}"}


# ---------------------------------------------------------------------------
# POST /crm/enriquecer-lead
# ---------------------------------------------------------------------------
@router.post("/enriquecer-lead")
async def enriquecer_lead(entrada: DatosEnriquecerLead):
    """
    Infiere datos faltantes del lead con alta confianza basándose en los disponibles.
    No inventa — solo infiere lo que se puede deducir con lógica.
    Entrada: datos_actuales (dict parcial) + contexto_conversacion.
    Salida: {status, datos_enriquecidos}
    """
    if not GEMINI_API_KEY:
        return {"status": "error", "mensaje": "Falta GEMINI_API_KEY."}

    datos_str = json.dumps(entrada.datos_actuales, ensure_ascii=False, indent=2)

    prompt = f"""Eres un experto en prospección B2B para LATAM.
Basándote SOLO en los datos disponibles del lead, infiere los campos vacíos con alta confianza.
NO inventes. Solo completa lo que se puede deducir lógicamente.

DATOS ACTUALES DEL LEAD:
{datos_str}

CONTEXTO DE CONVERSACIÓN:
{entrada.contexto_conversacion or "Sin contexto adicional."}

Responde SOLO con este JSON (mantén campos existentes, completa o mejora los vacíos):
{{
  "industria_inferida": "",
  "tamano_empresa": "[micro/pequena/mediana/grande]",
  "rol_contacto": "",
  "pain_points_probables": ["pain1", "pain2"],
  "servicios_relevantes": ["servicio1", "servicio2"],
  "canal_preferido": "[whatsapp/email/llamada/presencial]",
  "nivel_madurez_digital": "[basico/intermedio/avanzado]",
  "mejor_horario_contacto": "",
  "confianza_inferencia": "[alta/media/baja]"
}}"""

    try:
        texto = _call_gemini_text(prompt, timeout=30)
        parsed = _parse_json_from_text(texto)
        return {"status": "success", "datos_enriquecidos": parsed}
    except Exception as e:
        return {"status": "error", "mensaje": f"Error enriqueciendo lead: {str(e)}"}


# ---------------------------------------------------------------------------
# POST /crm/generar-seguimiento
# ---------------------------------------------------------------------------
@router.post("/generar-seguimiento")
async def generar_seguimiento(entrada: DatosGenerarSeguimiento):
    """
    Genera mensaje de seguimiento personalizado para WhatsApp según etapa del pipeline.
    No suena a template — referencia datos específicos del lead.
    Entrada: lead (dict) + etapa_pipeline + dias_sin_respuesta + brandbook.
    Salida: {status, mensaje_seguimiento, etapa, tono_recomendado}
    """
    if not GEMINI_API_KEY:
        return {"status": "error", "mensaje": "Falta GEMINI_API_KEY."}

    bb              = entrada.brandbook
    nombre_agencia  = bb.get("nombre_agencia", "System IA")
    tono            = bb.get("tono", "profesional pero cercano y humano")

    lead_str = json.dumps(entrada.lead, ensure_ascii=False)

    contexto_por_etapa = {
        "nuevo":             "Lead recién ingresado, nunca contactado. Primer contacto cálido.",
        "contactado":        "Ya hubo primer contacto pero no respondió. Seguimiento gentil.",
        "propuesta_enviada": "Se envió propuesta/presupuesto. Esperando decisión.",
        "negociacion":       "Está en negociación activa. Mantener el momentum.",
        "cerrado_perdido":   "Deal perdido. Mantener relación para futuro."
    }
    contexto_etapa = contexto_por_etapa.get(entrada.etapa_pipeline, "En proceso de venta.")

    prompt = f"""Eres el asesor comercial de {nombre_agencia}, agencia de automatizaciones IA para LATAM.
Tono de voz: {tono}

DATOS DEL LEAD: {lead_str}
ETAPA: {entrada.etapa_pipeline} — {contexto_etapa}
DÍAS SIN RESPUESTA: {entrada.dias_sin_respuesta}
ÚLTIMO CONTACTO: {entrada.ultimo_contacto or "No registrado"}

Escribe el mensaje de seguimiento para WhatsApp:
- Natural, no suene a template de ventas o CRM
- Referencia un dato específico del lead si está disponible (nombre, industria, problema mencionado)
- Tiene una razón válida para contactar (NO solo "¿viste mi propuesta?")
- Si hay muchos días sin respuesta ({entrada.dias_sin_respuesta} días), ajusta el tono apropiadamente
- Corto: máximo 4 líneas
- Termina con UNA pregunta o acción concreta
- Sin asteriscos ni markdown

Solo el mensaje, sin explicaciones."""

    try:
        texto = _call_gemini_text(prompt, timeout=30)

        # Determinar tono recomendado según días sin respuesta
        if entrada.dias_sin_respuesta <= 2:
            tono_rec = "normal"
        elif entrada.dias_sin_respuesta <= 7:
            tono_rec = "persistente_amable"
        else:
            tono_rec = "ultimo_intento"

        return {
            "status": "success",
            "mensaje_seguimiento": texto.strip(),
            "etapa": entrada.etapa_pipeline,
            "tono_recomendado": tono_rec
        }
    except Exception as e:
        return {"status": "error", "mensaje": f"Error generando seguimiento: {str(e)}"}
