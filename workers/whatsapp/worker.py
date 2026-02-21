import os
import re
import json
import requests as req
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List, Dict

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp"])

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_TEXT_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

INTENCIONES_VALIDAS = [
    "consulta_precio",
    "agendar_cita",
    "queja_reclamo",
    "soporte_tecnico",
    "informacion_general",
    "compra_directa",
    "otro"
]


class DatosClasificar(BaseModel):
    mensaje: str
    historial: Optional[List[Dict]] = []  # [{role: "user"|"agente", text: "..."}]
    brandbook: Optional[Dict] = {}


class DatosGenerarRespuesta(BaseModel):
    mensaje: str
    intencion: str
    historial: Optional[List[Dict]] = []
    brandbook: Optional[Dict] = {}
    nombre_cliente: Optional[str] = ""


class DatosTranscribir(BaseModel):
    audio_base64: str
    mime_type: Optional[str] = "audio/ogg"  # ogg, mp4, mpeg, webm


def _call_gemini_text(prompt: str, timeout: int = 30) -> str:
    resp = req.post(
        f"{GEMINI_TEXT_URL}?key={GEMINI_API_KEY}",
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=timeout
    )
    resp.raise_for_status()
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"]


def _call_gemini_multimodal(parts: list, timeout: int = 60) -> str:
    resp = req.post(
        f"{GEMINI_TEXT_URL}?key={GEMINI_API_KEY}",
        json={"contents": [{"parts": parts}]},
        timeout=timeout
    )
    resp.raise_for_status()
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"]


# ---------------------------------------------------------------------------
# POST /whatsapp/clasificar-mensaje
# ---------------------------------------------------------------------------
@router.post("/clasificar-mensaje")
async def clasificar_mensaje(entrada: DatosClasificar):
    """
    Detecta intención, urgencia, sentimiento y extrae datos clave del mensaje.
    Entrada: mensaje + historial reciente + brandbook.
    Salida: {status, intencion, confianza, urgencia, sentimiento, datos_extraidos}
    """
    if not GEMINI_API_KEY:
        return {"status": "error", "mensaje": "Falta GEMINI_API_KEY."}

    historial_str = ""
    for msg in entrada.historial[-5:]:
        role = "Cliente" if msg.get("role") == "user" else "Agente"
        historial_str += f"{role}: {msg.get('text', '')}\n"

    prompt = f"""Analiza este mensaje de WhatsApp de negocios. Responde SOLO con este JSON exacto, sin texto adicional:
{{
  "intencion": "[una de: {', '.join(INTENCIONES_VALIDAS)}]",
  "confianza": "[alta/media/baja]",
  "urgencia": "[urgente/normal/puede_esperar]",
  "sentimiento": "[positivo/neutral/negativo/frustrado]",
  "datos_extraidos": {{
    "nombre": "",
    "telefono": "",
    "fecha_mencionada": "",
    "producto_servicio_interes": ""
  }}
}}

Historial reciente:
{historial_str if historial_str else "Sin historial previo."}

Mensaje a clasificar: "{entrada.mensaje}"

Clasifica con el contexto del historial si está disponible."""

    try:
        texto = _call_gemini_text(prompt, timeout=20)
        match = re.search(r'\{[\s\S]*\}', texto)
        if not match:
            return {"status": "error", "mensaje": "No se pudo parsear la clasificación."}
        parsed = json.loads(match.group(0))
        return {"status": "success", **parsed}
    except Exception as e:
        return {"status": "error", "mensaje": f"Error clasificando mensaje: {str(e)}"}


# ---------------------------------------------------------------------------
# POST /whatsapp/generar-respuesta
# ---------------------------------------------------------------------------
@router.post("/generar-respuesta")
async def generar_respuesta(entrada: DatosGenerarRespuesta):
    """
    Genera respuesta personalizada de WhatsApp con voz de marca del cliente.
    Adapta el tono según la intención detectada (queja → empatía primero, etc).
    Entrada: mensaje + intencion + historial + brandbook.
    Salida: {status, respuesta}
    """
    if not GEMINI_API_KEY:
        return {"status": "error", "mensaje": "Falta GEMINI_API_KEY."}

    bb = entrada.brandbook
    nombre_agencia  = bb.get("nombre_agencia", "System IA")
    tono            = bb.get("tono", "amable, humano y profesional")
    servicios       = bb.get("servicios", "automatizaciones de WhatsApp, CRM, agendamientos y redes sociales")
    reglas          = bb.get("reglas", "No prometer tiempos exactos sin confirmar con el equipo")
    nombre_cliente  = f" {entrada.nombre_cliente}" if entrada.nombre_cliente else ""

    historial_str = ""
    for msg in entrada.historial[-6:]:
        role = "Cliente" if msg.get("role") == "user" else nombre_agencia
        historial_str += f"{role}: {msg.get('text', '')}\n"

    instrucciones_por_intencion = {
        "queja_reclamo":   "PRIMERO valida y empatiza con la frustración del cliente, LUEGO ofrece solución concreta.",
        "agendar_cita":    "Muestra disponibilidad y pide fecha + hora preferida del cliente.",
        "consulta_precio": "Da contexto de valor antes del precio. Si no tienes el precio exacto, ofrece agendar una llamada.",
        "compra_directa":  "Facilita el proceso al máximo. Confirma los detalles y próximo paso.",
        "soporte_tecnico": "Pide detalles específicos del problema para poder ayudar mejor.",
    }
    instruccion_extra = instrucciones_por_intencion.get(entrada.intencion, "")

    prompt = f"""Eres el asistente de WhatsApp de {nombre_agencia}, agencia de automatizaciones IA para LATAM.
Servicios: {servicios}
Tono de voz: {tono}
REGLAS ABSOLUTAS: {reglas}

Historial de conversación:
{historial_str if historial_str else "Primera interacción."}

El cliente{nombre_cliente} envió: "{entrada.mensaje}"
Intención detectada: {entrada.intencion}

{instruccion_extra}

REGLAS DE FORMATO PARA WHATSAPP:
- Natural y humano, no suenes a bot ni a template corporativo
- Máximo 3 párrafos cortos separados por salto de línea
- Sin asteriscos, sin markdown, sin listas con guiones
- Termina con UNA acción clara o pregunta concreta
- Si usas emojis, máximo 2 y solo si van con el tono"""

    try:
        texto = _call_gemini_text(prompt, timeout=30)
        return {"status": "success", "respuesta": texto.strip()}
    except Exception as e:
        return {"status": "error", "mensaje": f"Error generando respuesta: {str(e)}"}


# ---------------------------------------------------------------------------
# POST /whatsapp/transcribir-audio
# ---------------------------------------------------------------------------
@router.post("/transcribir-audio")
async def transcribir_audio(entrada: DatosTranscribir):
    """
    Transcribe notas de voz de WhatsApp usando Gemini multimodal.
    Entrada: audio en base64 + mime_type (ogg, mp4, mpeg, webm).
    Salida: {status, transcripcion}
    """
    if not GEMINI_API_KEY:
        return {"status": "error", "mensaje": "Falta GEMINI_API_KEY."}

    partes = [
        {
            "inlineData": {
                "mimeType": entrada.mime_type,
                "data": entrada.audio_base64
            }
        },
        {
            "text": (
                "Transcribe exactamente lo que dice este audio de WhatsApp en español. "
                "Solo devuelve el texto transcrito, sin explicaciones, sin comillas, sin encabezados."
            )
        }
    ]

    try:
        texto = _call_gemini_multimodal(partes, timeout=60)
        return {"status": "success", "transcripcion": texto.strip()}
    except Exception as e:
        return {"status": "error", "mensaje": f"Error transcribiendo audio: {str(e)}"}
