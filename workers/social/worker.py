import os
import re
import json
import time
import requests as req
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter(prefix="/social", tags=["Social Media"])

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_TEXT_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
GEMINI_IMG_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-preview-image-generation:generateContent"


class DatosCrearPost(BaseModel):
    cliente_id: str
    datos_marca: list  # Array de items de Airtable enviados por n8n


class DatosGenerarImagen(BaseModel):
    prompt: str
    estilo: Optional[str] = "fotografico, profesional, moderno, sin texto"
    max_intentos: Optional[int] = 4
    espera_segundos: Optional[int] = 25


class DatosSeleccionarTema(BaseModel):
    historial_temas: Optional[List[str]] = []
    industria: Optional[str] = "Automatización IA"
    objetivo_mes: Optional[str] = None


def _call_gemini_text(prompt: str, timeout: int = 60) -> str:
    """Llamada centralizada a Gemini para texto. Lanza excepción si falla."""
    resp = req.post(
        f"{GEMINI_TEXT_URL}?key={GEMINI_API_KEY}",
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=timeout
    )
    resp.raise_for_status()
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"]


# ---------------------------------------------------------------------------
# POST /social/crear-post
# ---------------------------------------------------------------------------
@router.post("/crear-post")
async def crear_post(entrada: DatosCrearPost):
    """
    Genera posts para IG, LinkedIn y Facebook con brandbook del cliente.
    Entrada: cliente_id + datos_marca (array de Airtable via n8n).
    Salida: {status, resultados: {instagram, linkedin, facebook}}
    """
    if not GEMINI_API_KEY:
        return {"status": "error", "mensaje": "Falta GEMINI_API_KEY en variables de entorno."}

    # Buscar datos del cliente en el array de n8n
    cliente_data = None
    for item in entrada.datos_marca:
        if item.get("json", {}).get("ID Cliente") == entrada.cliente_id:
            cliente_data = item.get("json")
            break

    if not cliente_data:
        return {"status": "error", "mensaje": f"No se encontró el cliente '{entrada.cliente_id}' en los datos."}

    industria   = cliente_data.get("Industria", "General")
    servicio    = cliente_data.get("Servicio Principal", "Automatizaciones IA")
    publico     = cliente_data.get("Público Objetivo", "Emprendedores y pymes LATAM")
    tono        = cliente_data.get("Tono de Voz", "Humano, cercano, experto")
    reglas      = cliente_data.get("Reglas Estrictas", "No prometer resultados garantizados")
    tema        = cliente_data.get("Tema del Día", "Automatización con IA")
    angulo      = cliente_data.get("Ángulo", "Beneficios prácticos para el negocio")

    prompt = f"""Eres el Estratega y Copywriter de una agencia de automatizaciones IA para LATAM.

BRANDBOOK DEL CLIENTE:
- Industria: {industria}
- Servicio principal: {servicio}
- Público objetivo: {publico}
- Tono de voz: {tono}
- RESTRICCIONES ABSOLUTAS: {reglas}

TEMA DEL DÍA: {tema}
ÁNGULO: {angulo}

TAREA: Crea 3 posts únicos y diferenciados, uno por red social.
Separa cada post EXACTAMENTE con: |||
NO uses markdown de código. Solo texto puro.

1. INSTAGRAM: Hook fuerte en línea 1, viñetas con emojis, 150-200 palabras, 6-8 hashtags al final.
|||
2. LINKEDIN: Apertura con dato o reflexión, desarrollo analítico (apertura-nudo-desenlace), cierre con pregunta, 300-400 palabras, max 2 emojis, 3-4 hashtags profesionales.
|||
3. FACEBOOK: Storytelling cercano como hablando con un amigo emprendedor, invita a comentar al final, 200-250 palabras, max 3 emojis."""

    try:
        texto = _call_gemini_text(prompt, timeout=60)
        partes = texto.split("|||")
        return {
            "status": "success",
            "resultados": {
                "instagram": partes[0].strip() if len(partes) > 0 else "",
                "linkedin":  partes[1].strip() if len(partes) > 1 else "",
                "facebook":  partes[2].strip() if len(partes) > 2 else ""
            }
        }
    except Exception as e:
        return {"status": "error", "mensaje": f"Error generando contenido: {str(e)}"}


# ---------------------------------------------------------------------------
# POST /social/generar-imagen
# ---------------------------------------------------------------------------
@router.post("/generar-imagen")
async def generar_imagen(entrada: DatosGenerarImagen):
    """
    Genera imagen con Gemini 2.0 Flash con loop de reintentos interno.
    Resuelve el problema de ciclos en n8n — el Worker espera internamente.
    Entrada: prompt + estilo + max_intentos + espera_segundos.
    Salida: {status, base64Image, mimeType, intentos}
    """
    if not GEMINI_API_KEY:
        return {"status": "error", "mensaje": "Falta GEMINI_API_KEY en variables de entorno."}

    prompt_completo = f"{entrada.prompt}. Estilo visual: {entrada.estilo}. Alta calidad, sin texto escrito en la imagen."

    for intento in range(1, entrada.max_intentos + 1):
        try:
            resp = req.post(
                f"{GEMINI_IMG_URL}?key={GEMINI_API_KEY}",
                json={
                    "contents": [{"parts": [{"text": prompt_completo}]}],
                    "generationConfig": {"responseModalities": ["image", "text"]}
                },
                timeout=90
            )
            resp.raise_for_status()
            parts = resp.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])

            for part in parts:
                if "inlineData" in part:
                    return {
                        "status": "success",
                        "base64Image": part["inlineData"]["data"],
                        "mimeType": part["inlineData"].get("mimeType", "image/png"),
                        "intentos": intento
                    }

        except Exception as e:
            if intento == entrada.max_intentos:
                return {"status": "error", "mensaje": f"Error en intento {intento}: {str(e)}"}

        # Imagen no lista aún — esperar antes del siguiente intento
        if intento < entrada.max_intentos:
            time.sleep(entrada.espera_segundos)

    return {
        "status": "error",
        "mensaje": f"Gemini no generó imagen tras {entrada.max_intentos} intentos de {entrada.espera_segundos}s cada uno."
    }


# ---------------------------------------------------------------------------
# POST /social/seleccionar-tema
# ---------------------------------------------------------------------------
@router.post("/seleccionar-tema")
async def seleccionar_tema(entrada: DatosSeleccionarTema):
    """
    IA selecciona el tema y ángulo óptimo para el post del día.
    Evita repetir temas recientes del historial.
    Salida: {status, tema, angulo, idea_central, prompt_imagen, razonamiento}
    """
    if not GEMINI_API_KEY:
        return {"status": "error", "mensaje": "Falta GEMINI_API_KEY en variables de entorno."}

    historial_str = ", ".join(entrada.historial_temas[-10:]) if entrada.historial_temas else "ninguno aún"
    objetivo_str  = entrada.objetivo_mes or "posicionamiento general de marca como expertos en automatización"

    prompt = f"""Eres el Estratega de Contenidos de una agencia de automatizaciones IA para LATAM.

INDUSTRIA: {entrada.industria}
OBJETIVO DEL MES: {objetivo_str}
TEMAS PUBLICADOS RECIENTEMENTE (no repetir): {historial_str}

Selecciona el mejor tema y ángulo para el post de HOY considerando:
- Variedad respecto al historial
- Relevancia para emprendedores y pymes LATAM
- Alto potencial de engagement

Responde SOLO con este JSON, sin explicaciones previas:
{{
  "tema": "Nombre del macro-tema",
  "angulo": "El ángulo específico y diferenciador de hoy",
  "idea_central": "La idea principal en una oración poderosa",
  "prompt_imagen": "Descripción visual detallada y específica para generar la imagen del post",
  "razonamiento": "Por qué este tema hoy (máximo 1 oración)"
}}"""

    try:
        texto = _call_gemini_text(prompt, timeout=30)
        match = re.search(r'\{[\s\S]*\}', texto)
        if not match:
            return {"status": "error", "mensaje": "Gemini no devolvió JSON válido."}
        parsed = json.loads(match.group(0))
        return {"status": "success", **parsed}
    except Exception as e:
        return {"status": "error", "mensaje": f"Error seleccionando tema: {str(e)}"}
