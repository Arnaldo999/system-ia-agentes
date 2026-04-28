"""
BANT scoring — extracción de señales y cálculo de score
========================================================
Lógica reusable para calificar leads según metodología BANT
(Budget / Authority / Need / Timeline) desde texto conversacional.

Diseñado para ser canal-agnóstico:
  - WhatsApp: el worker pasa el último mensaje + contexto BANT acumulado
  - Voz: el endpoint pasa la transcripción del turno + contexto previo

Devuelve score "caliente" / "tibio" / "frio" + flags de qué información
ya se capturó (para que el agente sepa qué falta preguntar).
"""

import re
from typing import Optional

CALIENTE = "caliente"
TIBIO = "tibio"
FRIO = "frio"

_PRESUPUESTO_PATTERNS = {
    "hata_50k": [r"\b(hasta|menos)\s*(de\s*)?(50|cincuenta)\s*(mil|k)?\b",
                 r"\$?\s*([0-9]+)\.?000\s*$", r"\b30\s*mil\b", r"\b40\s*mil\b"],
    "50k_100k": [r"\b([6-9]0|cien)\s*mil\b", r"\b50\s*a\s*100\b", r"\b80k\b"],
    "100k_200k": [r"\b1[0-9]{2}\s*mil\b", r"\b100\s*a\s*200\b", r"\b150k\b"],
    "mas_200k": [r"\bm[aá]s\s*de\s*200\b", r"\b[2-9][0-9]{2}\s*mil\b", r"\b[1-9]\s*mill[oó]n"],
}

_URGENCIA_HIGH = [
    r"\burgente\b", r"\bya\b", r"\binmediato\b", r"\besta\s*semana\b",
    r"\beste\s*mes\b", r"\bahora\b", r"\bcuanto\s*antes\b",
]
_URGENCIA_LOW = [
    r"\bel?\s*a[ñn]o\s*que\s*viene\b", r"\bm[aá]s\s*adelante\b",
    r"\bsin\s*apuro\b", r"\bsolo\s*viendo\b", r"\bcuriosidad\b",
]

_AUTHORITY_HIGH = [
    r"\bsoy\s+(el|la)\s+(due[ñn]o|titular|comprador)\b",
    r"\bdecido\s+yo\b", r"\bes\s+para\s+m[ií]\b",
]
_AUTHORITY_LOW = [
    r"\bpara\s+un\s+amigo\b", r"\bpara\s+mi\s+pap[aá]\b",
    r"\bconsulto\s+por\b", r"\btengo\s+que\s+preguntar\b",
]


def extract_signals(message: str, history: Optional[list[str]] = None) -> dict:
    """Extrae señales BANT del mensaje + historial.

    Returns:
        {
            "presupuesto": str | None,    # bucket "hata_50k" etc.
            "urgencia": "alta" | "baja" | None,
            "authority": "alta" | "baja" | None,
            "need_tipo": str | None,      # "casa" / "departamento" / etc.
            "need_operacion": str | None, # "venta" / "alquiler"
            "need_zona": str | None,
        }
    """
    full = (message or "").lower()
    if history:
        full += " " + " ".join((h or "").lower() for h in history)

    signals = {
        "presupuesto": None, "urgencia": None, "authority": None,
        "need_tipo": None, "need_operacion": None, "need_zona": None,
    }

    for bucket, patterns in _PRESUPUESTO_PATTERNS.items():
        if any(re.search(p, full) for p in patterns):
            signals["presupuesto"] = bucket
            break

    if any(re.search(p, full) for p in _URGENCIA_HIGH):
        signals["urgencia"] = "alta"
    elif any(re.search(p, full) for p in _URGENCIA_LOW):
        signals["urgencia"] = "baja"

    if any(re.search(p, full) for p in _AUTHORITY_HIGH):
        signals["authority"] = "alta"
    elif any(re.search(p, full) for p in _AUTHORITY_LOW):
        signals["authority"] = "baja"

    if re.search(r"\bdepartamento\b|\bdepto\b|\bdpto\b", full):
        signals["need_tipo"] = "departamento"
    elif re.search(r"\bcasa\b", full):
        signals["need_tipo"] = "casa"
    elif re.search(r"\blote\b|\bterreno\b", full):
        signals["need_tipo"] = "lote"
    elif re.search(r"\bph\b", full):
        signals["need_tipo"] = "ph"

    if re.search(r"\balquil(ar|er)\b|\brent(ar|a)\b", full):
        signals["need_operacion"] = "alquiler"
    elif re.search(r"\bcomprar\b|\bventa\b|\badquir(ir|iendo)\b", full):
        signals["need_operacion"] = "venta"

    return signals


def score_lead(signals: dict) -> str:
    """Calcula score caliente/tibio/frio según señales acumuladas.

    Reglas simples:
      - Caliente: presupuesto + urgencia alta + authority alta
      - Frio: urgencia baja o authority baja explícitas
      - Tibio: el resto (default)
    """
    if signals.get("urgencia") == "baja" or signals.get("authority") == "baja":
        return FRIO
    has_budget = bool(signals.get("presupuesto"))
    has_urgency = signals.get("urgencia") == "alta"
    has_authority = signals.get("authority") == "alta"
    has_need = bool(signals.get("need_tipo")) or bool(signals.get("need_operacion"))
    score_count = sum([has_budget, has_urgency, has_authority, has_need])
    if score_count >= 3:
        return CALIENTE
    if score_count >= 1:
        return TIBIO
    return FRIO


def missing_fields(signals: dict) -> list[str]:
    """Lista de campos BANT que aún faltan (para guiar al agente)."""
    missing = []
    if not signals.get("presupuesto"):
        missing.append("presupuesto")
    if not signals.get("need_tipo"):
        missing.append("tipo_propiedad")
    if not signals.get("need_operacion"):
        missing.append("operacion")
    if not signals.get("need_zona"):
        missing.append("zona")
    if not signals.get("urgencia"):
        missing.append("urgencia")
    return missing
