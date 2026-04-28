"""
Nuestra Iglesia — Software de presentación inteligente
Backend FastAPI que orquesta:
- Detección de referencias bíblicas (Gemini 2.0 Flash via Google AI Studio API)
- Transcripción y comprensión de audio del Pastor (Gemini multimodal)
- Sincronización con Freeshow (REST API en localhost:5506)
- Modo demo sin internet ni API key

LLM_PROVIDER: gemini (default, cloud, gratis hasta 1500 req/día) | demo (sin LLM, heurística)

Endpoints principales:
- POST /detectar/texto       → recibe texto, detecta referencia/canción
- POST /detectar/audio       → recibe chunk de audio (Gemini multimodal)
- POST /presentar/versiculo  → muestra versículo en Freeshow + pantalla web pública
- POST /presentar/letra      → muestra línea de canción
- POST /presentar/limpiar    → clear screen
- GET  /estado               → estado actual + conexiones
- GET  /datos/versiculos     → biblia precargada
- GET  /datos/canciones      → repertorio cargado
- WS   /ws/publico           → pantalla pública (la que va al proyector)
- WS   /ws/operador          → panel de control del operador
"""
import asyncio
import base64
import json
import os
import re
import tempfile
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

try:
    from faster_whisper import WhisperModel
    WHISPER_AVAILABLE = True
except ImportError:
    WhisperModel = None
    WHISPER_AVAILABLE = False

DATA_DIR = Path(__file__).parent.parent / "data"
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
FREESHOW_URL = os.getenv("FREESHOW_URL", "http://localhost:5506")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini" if GEMINI_API_KEY else "demo")

WHISPER_MODEL_NAME = os.getenv("WHISPER_MODEL", "small")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
whisper_model = None  # se carga lazy en lifespan


class TextoRequest(BaseModel):
    texto: str


class VersiculoRequest(BaseModel):
    referencia: str
    texto: Optional[str] = None
    version: Optional[str] = "RV1960"


class LetraRequest(BaseModel):
    cancion_id: str
    linea_index: int


# Carpeta donde guardamos imágenes/videos subidos por el operador
UPLOADS_DIR = Path(__file__).parent.parent / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ALLOWED_VIDEO_TYPES = {
    "video/mp4", "video/webm", "video/quicktime", "video/x-matroska",
    "video/x-msvideo",  # .avi
    "video/3gpp",       # .3gp
    "video/x-flv",      # .flv
}
# 2 GB — un sermón de 60 min en 1080p ronda 1-2 GB, deja margen.
# Configurable via env: MAX_UPLOAD_MB
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "2048")) * 1024 * 1024
UPLOAD_CHUNK = 1024 * 1024  # 1 MB chunks para streaming


class EstadoConexiones:
    operador_clients: list[WebSocket] = []
    publico_clients: list[WebSocket] = []
    gemini_disponible: bool = False
    freeshow_disponible: bool = False
    whisper_disponible: bool = False
    pantalla_actual: dict = {"tipo": "idle", "contenido": None}
    # Cola de sugerencias detectadas por Whisper que el operador todavía no aprobó.
    # Cada sugerencia tiene id único, timestamp, transcripción cruda y referencia detectada.
    # Solo se "muestra" en pantalla pública cuando el operador hace click en aprobar.
    sugerencias_pendientes: list[dict] = []


estado = EstadoConexiones()
versiculos_cache: dict = {}
canciones_cache: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global versiculos_cache, canciones_cache, whisper_model
    versiculos_cache = json.loads((DATA_DIR / "versiculos.json").read_text(encoding="utf-8"))
    canciones_cache = json.loads((DATA_DIR / "canciones.json").read_text(encoding="utf-8"))
    print(f"[init] Cargados {len(versiculos_cache)} versículos y {len(canciones_cache)} canciones")
    print(f"[init] LLM_PROVIDER={LLM_PROVIDER} | Modelo={GEMINI_MODEL} | Freeshow={FREESHOW_URL}")
    if LLM_PROVIDER == "gemini" and not GEMINI_API_KEY:
        print("[WARN] LLM_PROVIDER=gemini pero GEMINI_API_KEY vacío. Cae a modo demo.")

    if WHISPER_AVAILABLE:
        try:
            print(f"[whisper] Cargando modelo '{WHISPER_MODEL_NAME}' ({WHISPER_DEVICE}, {WHISPER_COMPUTE_TYPE})...")
            whisper_model = WhisperModel(
                WHISPER_MODEL_NAME,
                device=WHISPER_DEVICE,
                compute_type=WHISPER_COMPUTE_TYPE,
            )
            estado.whisper_disponible = True
            print(f"[whisper] ✓ Modelo cargado y listo")
        except Exception as e:
            print(f"[whisper] ✗ Error cargando modelo: {e}")
            estado.whisper_disponible = False
    else:
        print("[whisper] No disponible (paquete faster-whisper no instalado)")

    asyncio.create_task(verificar_conexiones_periodico())
    yield


app = FastAPI(title="Nuestra Iglesia — Sistema Inteligente", version="0.2.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


async def verificar_conexiones_periodico():
    while True:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                if LLM_PROVIDER == "gemini" and GEMINI_API_KEY:
                    try:
                        r = await client.get(
                            f"{GEMINI_API_BASE}/{GEMINI_MODEL}?key={GEMINI_API_KEY}"
                        )
                        estado.gemini_disponible = r.status_code == 200
                    except Exception:
                        estado.gemini_disponible = False
                else:
                    estado.gemini_disponible = False
                try:
                    r = await client.post(f"{FREESHOW_URL}", json={"action": "get_outputs"})
                    estado.freeshow_disponible = r.status_code in (200, 204)
                except Exception:
                    estado.freeshow_disponible = False
        except Exception:
            pass
        await asyncio.sleep(15)


def normalizar_referencia(texto_crudo: str) -> Optional[str]:
    """Heurística simple sin LLM. Para casos complejos usa Gemini."""
    t = texto_crudo.lower().strip()

    libros = {
        "génesis": "GN", "genesis": "GN",
        "éxodo": "EX", "exodo": "EX",
        "salmo": "SAL", "salmos": "SAL",
        "proverbios": "PR", "proverbio": "PR",
        "isaías": "IS", "isaias": "IS",
        "jeremías": "JER", "jeremias": "JER",
        "mateo": "MT",
        "marcos": "MR", "marco": "MR",
        "lucas": "LC",
        "juan": "JN",
        "hechos": "HCH",
        "romanos": "RO",
        "primera de corintios": "1CO", "1 corintios": "1CO", "primera corintios": "1CO",
        "segunda de corintios": "2CO", "2 corintios": "2CO",
        "gálatas": "GA", "galatas": "GA",
        "efesios": "EF",
        "filipenses": "FIL",
        "colosenses": "COL",
        "hebreos": "HE",
        "santiago": "STG",
        "apocalipsis": "AP",
    }

    numeros_palabra = {
        "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7,
        "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12, "trece": 13,
        "catorce": 14, "quince": 15, "dieciseis": 16, "dieciséis": 16,
        "diecisiete": 17, "dieciocho": 18, "diecinueve": 19, "veinte": 20,
        "veintiuno": 21, "veintidós": 22, "veintidos": 22, "veintitrés": 23, "veintitres": 23,
        "veinticuatro": 24, "veinticinco": 25, "treinta": 30,
    }

    for palabra, num in numeros_palabra.items():
        t = re.sub(rf"\b{palabra}\b", str(num), t)

    libro_codigo = None
    for nombre, codigo in libros.items():
        if nombre in t:
            libro_codigo = codigo
            t = t.replace(nombre, "")
            break
    if not libro_codigo:
        return None

    nums = re.findall(r"\d+", t)
    if len(nums) >= 2:
        return f"{libro_codigo} {nums[0]}:{nums[1]}"
    if len(nums) == 1:
        return f"{libro_codigo} {nums[0]}"
    return None


async def llamar_gemini_texto(prompt: str) -> Optional[str]:
    """Llama a Gemini 2.0 Flash con prompt de texto. Devuelve respuesta cruda."""
    if not GEMINI_API_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(
                f"{GEMINI_API_BASE}/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}",
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.1,
                        "maxOutputTokens": 100,
                    },
                },
            )
            if r.status_code == 200:
                data = r.json()
                candidates = data.get("candidates", [])
                if candidates and candidates[0].get("content", {}).get("parts"):
                    return candidates[0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        print(f"[gemini-texto] error: {e}")
    return None


async def llamar_gemini_audio(audio_bytes: bytes, mime_type: str = "audio/wav") -> Optional[dict]:
    """Procesa chunk de audio con Gemini multimodal. Detecta referencias bíblicas y canciones."""
    if not GEMINI_API_KEY:
        return None

    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
    prompt = (
        "Sos asistente de una iglesia evangélica que escucha lo que dice el Pastor durante el sermón. "
        "Analiza este audio en español y devuelve SOLO un JSON con este formato exacto, sin markdown:\n"
        '{"texto_transcripto": "...", "referencia_biblica": "LIBRO CAP:VER o null", "es_canto": true/false}\n\n'
        "Si menciona una referencia bíblica, normalizala a formato corto (ej 'Juan 3:16' → 'JN 3:16', "
        "'Primera de Corintios 13' → '1CO 13'). Si no hay referencia clara, dejá null."
    )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                f"{GEMINI_API_BASE}/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}",
                json={
                    "contents": [{
                        "parts": [
                            {"text": prompt},
                            {"inline_data": {"mime_type": mime_type, "data": audio_b64}},
                        ]
                    }],
                    "generationConfig": {
                        "temperature": 0.1,
                        "maxOutputTokens": 300,
                        "responseMimeType": "application/json",
                    },
                },
            )
            if r.status_code == 200:
                data = r.json()
                candidates = data.get("candidates", [])
                if candidates and candidates[0].get("content", {}).get("parts"):
                    raw = candidates[0]["content"]["parts"][0]["text"].strip()
                    raw = re.sub(r"^```json\s*|\s*```$", "", raw)
                    return json.loads(raw)
    except Exception as e:
        print(f"[gemini-audio] error: {e}")
    return None


async def freeshow_action(action: str, **data) -> dict:
    if not estado.freeshow_disponible:
        return {"ok": False, "reason": "freeshow_offline"}
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.post(f"{FREESHOW_URL}", json={"action": action, **data})
            return {"ok": r.status_code in (200, 204), "status": r.status_code}
    except Exception as e:
        return {"ok": False, "reason": str(e)}


async def broadcast_pantalla(pantalla: dict):
    estado.pantalla_actual = pantalla
    msg = json.dumps(pantalla)
    for ws in list(estado.publico_clients):
        try:
            await ws.send_text(msg)
        except Exception:
            estado.publico_clients.remove(ws)
    for ws in list(estado.operador_clients):
        try:
            await ws.send_text(msg)
        except Exception:
            estado.operador_clients.remove(ws)


@app.get("/estado")
async def get_estado():
    return {
        "llm_provider": LLM_PROVIDER,
        "gemini_disponible": estado.gemini_disponible,
        "freeshow_disponible": estado.freeshow_disponible,
        "whisper_disponible": estado.whisper_disponible,
        "whisper_modelo": WHISPER_MODEL_NAME if estado.whisper_disponible else None,
        "pantalla_actual": estado.pantalla_actual,
        "operadores_conectados": len(estado.operador_clients),
        "publicos_conectados": len(estado.publico_clients),
        "sugerencias_pendientes": len(estado.sugerencias_pendientes),
        "modelo": GEMINI_MODEL,
        "modo": "live" if (estado.gemini_disponible and estado.freeshow_disponible) else "demo",
    }


@app.get("/datos/versiculos")
async def get_versiculos():
    return versiculos_cache


@app.get("/datos/canciones")
async def get_canciones():
    return canciones_cache


# ─────────────────  TIMING LRC POR CANCIÓN  ─────────────────
# Cada canción puede tener un audio asociado + timestamps por línea.
# Los timing files viven en data/timings/{cancion_id}.json con formato:
# { "audio_url": "/uploads/123_tema.mp3", "timings": [0.0, 5.2, 11.4, ...] }
# (timings[i] = segundos en los que arranca la línea i de la canción)
TIMINGS_DIR = DATA_DIR / "timings"
TIMINGS_DIR.mkdir(exist_ok=True)


class TimingRequest(BaseModel):
    audio_url: Optional[str] = None
    timings: list[Optional[float]] = []  # null si esa línea no tiene timing aún


@app.get("/cancion/{cancion_id}/timing")
async def get_timing(cancion_id: str):
    if cancion_id not in canciones_cache:
        raise HTTPException(404, "Canción no encontrada")
    timing_file = TIMINGS_DIR / f"{cancion_id}.json"
    if not timing_file.exists():
        return {"audio_url": None, "timings": [], "tiene_timing": False}
    data = json.loads(timing_file.read_text(encoding="utf-8"))
    data["tiene_timing"] = True
    return data


@app.post("/cancion/{cancion_id}/timing")
async def save_timing(cancion_id: str, req: TimingRequest):
    if cancion_id not in canciones_cache:
        raise HTTPException(404, "Canción no encontrada")
    timing_file = TIMINGS_DIR / f"{cancion_id}.json"
    payload = {
        "audio_url": req.audio_url,
        "timings": req.timings,
        "actualizado": time.time(),
    }
    timing_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "guardado": payload}


@app.delete("/cancion/{cancion_id}/timing")
async def delete_timing(cancion_id: str):
    timing_file = TIMINGS_DIR / f"{cancion_id}.json"
    if timing_file.exists():
        timing_file.unlink()
    return {"ok": True}


@app.post("/detectar/texto")
async def detectar_texto(req: TextoRequest):
    """Detecta referencia bíblica o línea de canción en un texto transcripto."""
    referencia = normalizar_referencia(req.texto)
    metodo = "heuristica"

    if not referencia and estado.gemini_disponible:
        prompt = (
            "Analiza este texto transcripto del Pastor en un sermón en español. "
            "Si menciona una referencia bíblica, devuelve SOLO la referencia normalizada "
            "en formato 'LIBRO CAP:VER' (ej: 'JN 3:16', '1CO 13:4'). "
            "Si no menciona ninguna referencia, devuelve solo 'NONE'. "
            f"Texto: \"{req.texto}\""
        )
        resp = await llamar_gemini_texto(prompt)
        if resp and resp.strip() != "NONE":
            referencia = resp.strip().split("\n")[0]
            metodo = "gemini"

    cancion_match = None
    for cid, cancion in canciones_cache.items():
        for idx, linea in enumerate(cancion["letras"]):
            if not linea.strip():
                continue
            if linea.lower() in req.texto.lower() or req.texto.lower() in linea.lower():
                cancion_match = {"cancion_id": cid, "linea_index": idx, "linea": linea}
                break
        if cancion_match:
            break

    return {
        "referencia": referencia,
        "versiculo_existe": referencia in versiculos_cache if referencia else False,
        "cancion": cancion_match,
        "texto_original": req.texto,
        "metodo": metodo,
    }


@app.post("/detectar/audio")
async def detectar_audio(audio: UploadFile = File(...)):
    """Recibe chunk de audio (5-30s) y lo procesa con Gemini multimodal directo."""
    if not estado.gemini_disponible:
        raise HTTPException(503, "Gemini no disponible. Usar /detectar/texto en modo demo.")
    audio_bytes = await audio.read()
    mime = audio.content_type or "audio/wav"
    resultado = await llamar_gemini_audio(audio_bytes, mime)
    if not resultado:
        raise HTTPException(500, "Error procesando audio con Gemini")
    return resultado


# Prompt de contexto bíblico — mejora la calidad de transcripción de palabras
# poco frecuentes (nombres propios, libros, números). Whisper usa esto como
# "vocabulario esperado", no como instrucción de comportamiento.
WHISPER_INITIAL_PROMPT = (
    "Sermón cristiano evangélico en español. "
    "Posibles referencias bíblicas: Génesis, Éxodo, Levítico, Números, Deuteronomio, "
    "Josué, Jueces, Rut, Samuel, Reyes, Crónicas, Esdras, Nehemías, Ester, Job, "
    "Salmos, Proverbios, Eclesiastés, Cantares, Isaías, Jeremías, Lamentaciones, "
    "Ezequiel, Daniel, Oseas, Joel, Amós, Abdías, Jonás, Miqueas, Nahum, Habacuc, "
    "Sofonías, Hageo, Zacarías, Malaquías, Mateo, Marcos, Lucas, Juan, Hechos, "
    "Romanos, Corintios, Gálatas, Efesios, Filipenses, Colosenses, Tesalonicenses, "
    "Timoteo, Tito, Filemón, Hebreos, Santiago, Pedro, Judas, Apocalipsis. "
    "Capítulo, versículo, amén, aleluya, Cristo, Jesús, Señor, Padre, Espíritu Santo."
)


def _transcribir_whisper_sync(audio_bytes: bytes, suffix: str = ".wav") -> dict:
    """Transcribe sincrónicamente con faster-whisper. Se ejecuta en threadpool."""
    if whisper_model is None:
        raise RuntimeError("Whisper no inicializado")
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(audio_bytes)
        tmp_path = f.name
    try:
        segments, info = whisper_model.transcribe(
            tmp_path,
            language="es",
            beam_size=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
            initial_prompt=WHISPER_INITIAL_PROMPT,
        )
        texto_completo = " ".join(seg.text.strip() for seg in segments).strip()
        return {
            "texto": texto_completo,
            "idioma": info.language,
            "probabilidad_idioma": round(info.language_probability, 3),
            "duracion_segundos": round(info.duration, 2),
        }
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


@app.post("/transcribir/whisper")
async def transcribir_whisper(audio: UploadFile = File(...)):
    """Transcribe audio (audio→texto) con faster-whisper local. Sin internet, gratis."""
    if not estado.whisper_disponible or whisper_model is None:
        raise HTTPException(503, "Whisper no disponible. Verificá WHISPER_MODEL en .env")
    audio_bytes = await audio.read()
    fname = audio.filename or "audio.wav"
    suffix = "." + fname.split(".")[-1] if "." in fname else ".wav"
    try:
        resultado = await asyncio.to_thread(_transcribir_whisper_sync, audio_bytes, suffix)
        return resultado
    except Exception as e:
        raise HTTPException(500, f"Error transcribiendo: {e}")


async def broadcast_sugerencias():
    """Notifica a TODOS los operadores que la cola de sugerencias cambió."""
    msg = json.dumps({
        "tipo_msg": "sugerencias_actualizadas",
        "sugerencias": estado.sugerencias_pendientes,
    })
    for ws in list(estado.operador_clients):
        try:
            await ws.send_text(msg)
        except Exception:
            estado.operador_clients.remove(ws)


@app.post("/escuchar/pastor")
async def escuchar_pastor(audio: UploadFile = File(...)):
    """
    Pipeline NO-AUTOMÁTICO: audio del Pastor → Whisper transcribe → Gemini detecta.
    Si detecta referencia bíblica O línea de canción, agrega una SUGERENCIA a la cola
    del operador (NO toca la pantalla pública). El operador decide si lanzar o descartar.
    Si NO detecta nada útil, devuelve la transcripción pero no agrega sugerencia.
    """
    if not estado.whisper_disponible or whisper_model is None:
        raise HTTPException(503, "Whisper no disponible")

    audio_bytes = await audio.read()
    fname = audio.filename or "audio.wav"
    suffix = "." + fname.split(".")[-1] if "." in fname else ".wav"

    transcripcion = await asyncio.to_thread(_transcribir_whisper_sync, audio_bytes, suffix)
    if not transcripcion["texto"]:
        return {
            "transcripcion": transcripcion,
            "deteccion": None,
            "sugerencia_creada": False,
            "razon": "audio_sin_voz",
        }

    deteccion = await detectar_texto(TextoRequest(texto=transcripcion["texto"]))

    # SOLO crear sugerencia si hay algo accionable (referencia bíblica EN biblioteca,
    # o línea de canción EN repertorio). Si no, ignoramos silenciosamente.
    if not deteccion["versiculo_existe"] and not deteccion["cancion"]:
        return {
            "transcripcion": transcripcion,
            "deteccion": deteccion,
            "sugerencia_creada": False,
            "razon": "sin_referencia_actionable",
        }

    sugerencia = {
        "id": str(uuid.uuid4()),
        "timestamp": time.time(),
        "transcripcion": transcripcion["texto"],
        "tipo": "versiculo" if deteccion["versiculo_existe"] else "letra",
        "referencia": deteccion["referencia"] if deteccion["versiculo_existe"] else None,
        "cancion": deteccion["cancion"],
        "metodo_deteccion": deteccion["metodo"],
    }

    if sugerencia["tipo"] == "versiculo":
        v = versiculos_cache.get(sugerencia["referencia"], {})
        sugerencia["preview_titulo"] = v.get("referencia", sugerencia["referencia"])
        sugerencia["preview_texto"] = v.get("texto", "")[:120]
    else:
        c = sugerencia["cancion"]
        cancion_data = canciones_cache.get(c["cancion_id"], {})
        sugerencia["preview_titulo"] = cancion_data.get("titulo", c["cancion_id"])
        sugerencia["preview_texto"] = c["linea"]

    # Mantener cola corta (últimas 10 sugerencias) — descartar viejas
    estado.sugerencias_pendientes.append(sugerencia)
    if len(estado.sugerencias_pendientes) > 10:
        estado.sugerencias_pendientes = estado.sugerencias_pendientes[-10:]

    await broadcast_sugerencias()

    return {
        "transcripcion": transcripcion,
        "deteccion": deteccion,
        "sugerencia_creada": True,
        "sugerencia_id": sugerencia["id"],
    }


@app.get("/sugerencias")
async def get_sugerencias():
    """Devuelve la cola actual de sugerencias pendientes para el panel operador."""
    return {"sugerencias": estado.sugerencias_pendientes}


@app.post("/sugerencias/{sugerencia_id}/aprobar")
async def aprobar_sugerencia(sugerencia_id: str):
    """Operador aprueba — la sugerencia se MUESTRA en pantalla pública AHORA."""
    sug = next((s for s in estado.sugerencias_pendientes if s["id"] == sugerencia_id), None)
    if not sug:
        raise HTTPException(404, "Sugerencia no encontrada o ya consumida")

    if sug["tipo"] == "versiculo":
        await presentar_versiculo(VersiculoRequest(referencia=sug["referencia"]))
    elif sug["tipo"] == "letra":
        c = sug["cancion"]
        await presentar_letra(LetraRequest(cancion_id=c["cancion_id"], linea_index=c["linea_index"]))

    # Remover de la cola al aprobar (ya se mostró)
    estado.sugerencias_pendientes = [s for s in estado.sugerencias_pendientes if s["id"] != sugerencia_id]
    await broadcast_sugerencias()
    return {"ok": True, "mostrada": sug}


@app.post("/sugerencias/{sugerencia_id}/descartar")
async def descartar_sugerencia(sugerencia_id: str):
    """Operador descarta — la sugerencia se borra sin mostrar en pantalla."""
    before = len(estado.sugerencias_pendientes)
    estado.sugerencias_pendientes = [s for s in estado.sugerencias_pendientes if s["id"] != sugerencia_id]
    if len(estado.sugerencias_pendientes) == before:
        raise HTTPException(404, "Sugerencia no encontrada")
    await broadcast_sugerencias()
    return {"ok": True, "descartada": sugerencia_id}


@app.post("/sugerencias/limpiar")
async def limpiar_sugerencias():
    """Limpia toda la cola de sugerencias pendientes."""
    cant = len(estado.sugerencias_pendientes)
    estado.sugerencias_pendientes = []
    await broadcast_sugerencias()
    return {"ok": True, "descartadas": cant}


# ─────────────────  KARAOKE EN VIVO (Whisper escucha al grupo de cantos)  ─────────────────

def _normalizar_texto(s: str) -> str:
    """Normaliza para fuzzy-match: lowercase, sin tildes, sin puntuación, espacios colapsados."""
    import unicodedata
    s = s.lower().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _score_match(transcripcion: str, linea: str) -> float:
    """Cuántas palabras de `linea` aparecen en `transcripcion`. 0..1"""
    if not linea.strip():
        return 0.0
    palabras_linea = set(_normalizar_texto(linea).split())
    palabras_trans = set(_normalizar_texto(transcripcion).split())
    if not palabras_linea:
        return 0.0
    interseccion = palabras_linea & palabras_trans
    return len(interseccion) / len(palabras_linea)


@app.post("/escuchar/canto")
async def escuchar_canto(
    audio: UploadFile = File(...),
    cancion_id: str = "",
    linea_actual: int = 0,
):
    """
    Karaoke "salto inteligente": las letras YA están preparadas. Whisper SOLO
    decide cuándo saltar a la siguiente línea.

    Reglas estrictas para evitar saltos erróneos:
    1. Mínimo 3 palabras transcriptas (descarta silencios, ruidos, palabras sueltas)
    2. Solo considera línea actual y las 3 SIGUIENTES (nunca retrocede salvo confianza muy alta)
    3. Score de la siguiente línea debe ser AL MENOS 0.3 superior al de la actual
       (evita saltos cuando todavía están cantando la línea de ahora)
    4. Score absoluto >= 0.5 para auto-avanzar
    5. Score 0.35-0.5 → solo sugiere, no avanza (operador puede aprobar manual)
    """
    if not estado.whisper_disponible or whisper_model is None:
        raise HTTPException(503, "Whisper no disponible")
    if not cancion_id or cancion_id not in canciones_cache:
        raise HTTPException(400, f"cancion_id inválido: {cancion_id}")

    audio_bytes = await audio.read()
    fname = audio.filename or "audio.wav"
    suffix = "." + fname.split(".")[-1] if "." in fname else ".wav"

    def transcribir():
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(audio_bytes)
            tmp = f.name
        try:
            segments, info = whisper_model.transcribe(
                tmp, language="es", beam_size=3,
                vad_filter=False,
                initial_prompt="Canción de adoración cristiana en español. Letras de himnos, alabanza al Señor, Cristo Jesús, aleluya, gloria, santo.",
            )
            return " ".join(seg.text.strip() for seg in segments).strip()
        finally:
            try: os.unlink(tmp)
            except OSError: pass

    transcripcion = await asyncio.to_thread(transcribir)

    cancion = canciones_cache[cancion_id]
    letras = cancion["letras"]
    n = len(letras)

    # FILTRO 1: si Whisper transcribe muy poco, no es voz cantada — descartar
    palabras_trans = _normalizar_texto(transcripcion).split()
    if len(palabras_trans) < 3:
        return {
            "transcripcion": transcripcion,
            "linea_actual": linea_actual,
            "sugerencia_avance": None,
            "razon": "transcripcion_corta",
            "candidatos": [],
            "auto_avanzado": False,
        }

    # Score de línea actual (referencia base)
    score_actual = _score_match(transcripcion, letras[linea_actual]) if linea_actual < n else 0.0

    # Buscar próximas líneas no vacías (siguiente real, saltando vacíos)
    candidatos = []
    proxima_no_vacia = None
    for offset in range(1, 6):  # ventana de 5 líneas adelante
        idx = linea_actual + offset
        if idx >= n:
            break
        if not letras[idx].strip():
            continue
        score = _score_match(transcripcion, letras[idx])
        candidatos.append({"index": idx, "linea": letras[idx], "score": round(score, 2)})
        if proxima_no_vacia is None:
            proxima_no_vacia = idx

    # Una candidata extra: línea anterior (solo si se equivocó el operador y está cantando atrás)
    if linea_actual > 0:
        for back in range(1, 3):
            idx = linea_actual - back
            if idx < 0:
                break
            if not letras[idx].strip():
                continue
            score = _score_match(transcripcion, letras[idx])
            candidatos.append({"index": idx, "linea": letras[idx], "score": round(score, 2), "es_atras": True})
            break

    candidatos.sort(key=lambda c: c["score"], reverse=True)
    mejor = candidatos[0] if candidatos else None

    sugerencia = None
    auto_avanzado = False
    razon = "esperando"

    if mejor and mejor["score"] >= 0.35:
        es_atras = mejor.get("es_atras", False)
        # FILTRO 2: para retroceder, exigir score muy alto (0.7+)
        if es_atras:
            if mejor["score"] >= 0.7 and (mejor["score"] - score_actual) >= 0.3:
                sugerencia = mejor["index"]
                if mejor["score"] >= 0.75:
                    await presentar_letra(LetraRequest(cancion_id=cancion_id, linea_index=mejor["index"]))
                    auto_avanzado = True
                    razon = "auto_retroceso"
                else:
                    razon = "sugerencia_retroceso"
            else:
                razon = "atras_descartado"
        else:
            # FILTRO 3: para avanzar, score nuevo > score_actual + 0.2 (claro cambio de línea)
            diferencia = mejor["score"] - score_actual
            if mejor["score"] >= 0.5 and diferencia >= 0.2:
                sugerencia = mejor["index"]
                await presentar_letra(LetraRequest(cancion_id=cancion_id, linea_index=mejor["index"]))
                auto_avanzado = True
                razon = "auto_avance"
            elif mejor["score"] >= 0.35:
                sugerencia = mejor["index"]
                razon = "sugerencia"

    return {
        "transcripcion": transcripcion,
        "linea_actual": linea_actual,
        "score_actual": round(score_actual, 2),
        "sugerencia_avance": sugerencia,
        "candidatos": candidatos[:3],
        "auto_avanzado": auto_avanzado,
        "razon": razon,
    }


@app.post("/presentar/versiculo")
async def presentar_versiculo(req: VersiculoRequest):
    versiculo_data = versiculos_cache.get(req.referencia)
    pantalla = {
        "tipo": "versiculo",
        "referencia": versiculo_data["referencia"] if versiculo_data else req.referencia,
        "texto": req.texto or (versiculo_data["texto"] if versiculo_data else "Versículo no cargado"),
        "version": req.version or (versiculo_data["version"] if versiculo_data else "RV1960"),
    }
    await broadcast_pantalla(pantalla)
    fs_result = await freeshow_action("start_scripture", reference=req.referencia)
    return {"ok": True, "pantalla": pantalla, "freeshow": fs_result}


@app.post("/presentar/letra")
async def presentar_letra(req: LetraRequest):
    cancion = canciones_cache.get(req.cancion_id)
    if not cancion:
        raise HTTPException(404, "Canción no encontrada")
    letras = cancion["letras"]
    if req.linea_index >= len(letras):
        raise HTTPException(400, "Índice fuera de rango")
    linea_actual = letras[req.linea_index]
    linea_anterior = letras[req.linea_index - 1] if req.linea_index > 0 else None
    linea_siguiente = letras[req.linea_index + 1] if req.linea_index + 1 < len(letras) else None
    pantalla = {
        "tipo": "letra",
        "cancion_id": req.cancion_id,
        "cancion_titulo": cancion["titulo"],
        "linea_actual": linea_actual,
        "linea_anterior": linea_anterior,
        "linea_siguiente": linea_siguiente,
        "linea_index": req.linea_index,
        "total_lineas": len(letras),
        # Nueva: lista completa para que el frontend muestre estilo karaoke con todas
        "todas_las_lineas": letras,
    }
    await broadcast_pantalla(pantalla)
    return {"ok": True, "pantalla": pantalla}


@app.post("/presentar/limpiar")
async def presentar_limpiar():
    pantalla = {"tipo": "idle", "contenido": None}
    await broadcast_pantalla(pantalla)
    fs_result = await freeshow_action("clear_all")
    return {"ok": True, "freeshow": fs_result}


# ─────────────────  IMÁGENES Y VIDEOS ANEXOS  ─────────────────

def _safe_filename(filename: str) -> str:
    """Saneo simple del nombre de archivo (evita path traversal)."""
    name = os.path.basename(filename or "media")
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    if not name or name.startswith("."):
        name = "media_" + name
    return name[:200]


@app.post("/media/subir")
async def media_subir(archivo: UploadFile = File(...)):
    """Recibe imagen o video, lo guarda streaming (chunks 1MB) en uploads/.
    NO lo muestra automáticamente — el operador decide cuándo presentarlo.
    Soporta hasta MAX_UPLOAD_MB (default 2GB)."""
    content_type = (archivo.content_type or "").lower()
    es_imagen = content_type in ALLOWED_IMAGE_TYPES
    es_video = content_type in ALLOWED_VIDEO_TYPES

    # Si el navegador no manda content-type pero sí extensión, permitirlo igual
    if not es_imagen and not es_video:
        ext = ("." + (archivo.filename or "").rsplit(".", 1)[-1].lower()) if archivo.filename else ""
        if ext in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
            es_imagen = True
        elif ext in {".mp4", ".webm", ".mov", ".mkv", ".avi", ".3gp", ".flv", ".m4v"}:
            es_video = True

    if not es_imagen and not es_video:
        raise HTTPException(
            400,
            f"Tipo no permitido: {content_type}. Imágenes: jpg/png/webp/gif. Videos: mp4/webm/mov/mkv/avi/flv"
        )

    # Streaming: vamos guardando en archivo temporal en chunks de 1MB,
    # cortamos si supera el límite. Esto evita cargar 1GB en RAM.
    ts = int(time.time() * 1000)
    safe_name = _safe_filename(archivo.filename or "media")
    final_name = f"{ts}_{safe_name}"
    final_path = UPLOADS_DIR / final_name
    bytes_escritos = 0

    try:
        with open(final_path, "wb") as out:
            while True:
                chunk = await archivo.read(UPLOAD_CHUNK)
                if not chunk:
                    break
                bytes_escritos += len(chunk)
                if bytes_escritos > MAX_UPLOAD_BYTES:
                    out.close()
                    final_path.unlink(missing_ok=True)
                    max_mb = MAX_UPLOAD_BYTES // (1024 * 1024)
                    raise HTTPException(
                        413,
                        f"Archivo demasiado grande (>{max_mb} MB). "
                        f"Para subir más, ajustá MAX_UPLOAD_MB en .env"
                    )
                out.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        # cleanup parcial si algo falla
        final_path.unlink(missing_ok=True)
        raise HTTPException(500, f"Error guardando archivo: {e}")

    return {
        "ok": True,
        "id": final_name,
        "nombre_original": archivo.filename,
        "url": f"/uploads/{final_name}",
        "tipo": "imagen" if es_imagen else "video",
        "mime": content_type,
        "tamano_mb": round(bytes_escritos / (1024 * 1024), 2),
        "tamano_kb": round(bytes_escritos / 1024, 1),
    }


@app.get("/media/listar")
async def media_listar():
    """Lista los archivos ya subidos (para que el operador los reuse)."""
    items = []
    for f in sorted(UPLOADS_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if not f.is_file() or f.name.startswith("."):
            continue
        ext = f.suffix.lower()
        es_imagen = ext in {".jpg", ".jpeg", ".png", ".webp", ".gif"}
        es_video = ext in {".mp4", ".webm", ".mov", ".mkv"}
        if not (es_imagen or es_video):
            continue
        items.append({
            "id": f.name,
            "url": f"/uploads/{f.name}",
            "tipo": "imagen" if es_imagen else "video",
            "tamano_kb": round(f.stat().st_size / 1024, 1),
            "modificado": f.stat().st_mtime,
        })
    return {"items": items}


@app.delete("/media/{file_id}")
async def media_eliminar(file_id: str):
    """Borra un archivo subido."""
    safe_id = _safe_filename(file_id)
    target = UPLOADS_DIR / safe_id
    if not target.exists() or not target.is_file():
        raise HTTPException(404, "Archivo no encontrado")
    target.unlink()
    return {"ok": True, "eliminado": safe_id}


class MediaPresentRequest(BaseModel):
    url: str
    tipo: str  # "imagen" o "video"
    autoplay: Optional[bool] = True
    loop: Optional[bool] = False


@app.post("/presentar/media")
async def presentar_media(req: MediaPresentRequest):
    """Muestra una imagen o video en la pantalla pública (sincronizado vía WS)."""
    if req.tipo not in ("imagen", "video"):
        raise HTTPException(400, "tipo debe ser 'imagen' o 'video'")
    pantalla = {
        "tipo": "media",
        "media_tipo": req.tipo,
        "url": req.url,
        "autoplay": bool(req.autoplay),
        "loop": bool(req.loop),
    }
    await broadcast_pantalla(pantalla)
    return {"ok": True, "pantalla": pantalla}


@app.post("/demo/simular-pastor")
async def demo_simular_pastor(req: TextoRequest):
    """Demo: simula que el Pastor dijo algo. Detecta y muestra automáticamente."""
    deteccion = await detectar_texto(req)
    if deteccion["versiculo_existe"]:
        await presentar_versiculo(VersiculoRequest(referencia=deteccion["referencia"]))
        return {"deteccion": deteccion, "accion_tomada": "presentar_versiculo"}
    if deteccion["cancion"]:
        c = deteccion["cancion"]
        await presentar_letra(LetraRequest(cancion_id=c["cancion_id"], linea_index=c["linea_index"]))
        return {"deteccion": deteccion, "accion_tomada": "presentar_letra"}
    return {"deteccion": deteccion, "accion_tomada": "ninguna"}


@app.websocket("/ws/operador")
async def ws_operador(websocket: WebSocket):
    await websocket.accept()
    estado.operador_clients.append(websocket)
    await websocket.send_text(json.dumps(estado.pantalla_actual))
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in estado.operador_clients:
            estado.operador_clients.remove(websocket)


@app.websocket("/ws/publico")
async def ws_publico(websocket: WebSocket):
    await websocket.accept()
    estado.publico_clients.append(websocket)
    await websocket.send_text(json.dumps(estado.pantalla_actual))
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in estado.publico_clients:
            estado.publico_clients.remove(websocket)


@app.get("/")
async def root():
    return FileResponse(FRONTEND_DIR / "operador.html")


@app.get("/publico")
async def publico():
    return FileResponse(FRONTEND_DIR / "publico.html")


app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
