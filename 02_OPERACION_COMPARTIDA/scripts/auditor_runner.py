"""
Auditor Runner — Orquestador principal Fase 2
=============================================
Importa y ejecuta todos los auditores activos.
Consolida resultados y envía reporte a Telegram solo si hay alertas.
Diseñado para correr via cron diario a las 8am ARG (UTC-3 = 11:00 UTC).

Uso:
    python auditor_runner.py

Cron:
    0 11 * * * /path/venv/bin/python /path/scripts/auditor_runner.py >> /var/log/auditor_runner.log 2>&1

Variables de entorno requeridas:
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    (las variables de cada auditor se cargan desde sus propios módulos)

Auditores activos (Fase 2.2):
    - auditor_infra      → n8n Mica + Lovbot health
    - auditor_workflows  → workflows críticos × 3 instancias

Auditores pendientes (se agregan en fases siguientes):
    - auditor_ycloud     (Fase 2.3)
    - auditor_tokens     (Fase 2.3)
    - auditor_evolution  (Fase 2.4)
    - auditor_meta_provider (Fase 2.4)
    - auditor_crm        (Fase 2.5)
"""

import os
import datetime
import traceback
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]
REQUEST_TIMEOUT    = 10

# ── Auditores activos ─────────────────────────────────────────────────────────
# Para agregar un auditor nuevo: importarlo y añadirlo a esta lista.

import auditor_infra
import auditor_workflows

AUDITORES = [
    auditor_infra,
    auditor_workflows,
]

# ── Telegram ──────────────────────────────────────────────────────────────────

def _enviar_telegram(mensaje: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id":    TELEGRAM_CHAT_ID,
            "text":       mensaje,
            "parse_mode": "HTML",
        }, timeout=REQUEST_TIMEOUT)
    except Exception as e:
        print(f"[runner] ERROR enviando Telegram: {e}")


# ── Formato del reporte ───────────────────────────────────────────────────────

ICONOS_TIPO = {
    "infraestructura_caida":  "❌",
    "workflow_inactivo":      "⏸",
    "workflow_inexistente":   "❓",
    "ejecucion_con_error":    "🔴",
}

TITULOS_AUDITOR = {
    "infra":     "🏗️ Infraestructura",
    "workflows": "📋 Workflows",
    "ycloud":    "📡 YCloud",
    "tokens":    "🔐 Tokens",
    "evolution": "💬 Evolution API",
    "meta":      "🌐 Meta Tech Provider",
    "crm":       "🗄️ CRM / Tenants",
}

def _formatear_reporte(resultados: list[dict], fecha: str) -> str:
    total_alertas = sum(len(r["alertas"]) for r in resultados)
    lineas = [f"🔍 <b>AUDITORÍA DIARIA</b> — {fecha}", ""]

    for r in resultados:
        titulo = TITULOS_AUDITOR.get(r["auditor"], r["auditor"].upper())
        if r.get("error_runner"):
            lineas.append(f"{titulo}: ⚠️ error al ejecutar — {r['error_runner']}")
            continue
        if r["ok"]:
            lineas.append(f"{titulo}: ✅ OK")
        else:
            lineas.append(f"{titulo}:")
            for a in r["alertas"]:
                icono = ICONOS_TIPO.get(a.get("tipo", ""), "⚠️")
                nombre = a.get("nombre") or a.get("servicio") or "—"
                detalle = a.get("detalle", "")
                instancia = f" [{a['instancia']}]" if "instancia" in a else ""
                lineas.append(f"  {icono} {nombre}{instancia} — {detalle}")

    lineas.append("")
    lineas.append(f"⚠️ <b>{total_alertas} alerta{'s' if total_alertas != 1 else ''} detectada{'s' if total_alertas != 1 else ''}</b> — revisá el panel")
    return "\n".join(lineas)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    fecha = datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=-3))
    ).strftime("%d/%m/%Y %H:%M ARG")

    print(f"[runner] Iniciando auditoría — {fecha}")

    resultados = []
    for auditor in AUDITORES:
        nombre = getattr(auditor, "__name__", str(auditor)).split(".")[-1]
        try:
            resultado = auditor.run()
            resultados.append(resultado)
            estado = "✅ OK" if resultado["ok"] else f"❌ {len(resultado['alertas'])} alertas"
            print(f"[runner] {nombre}: {estado}")
        except Exception as e:
            tb = traceback.format_exc()
            print(f"[runner] ERROR en {nombre}: {e}\n{tb}")
            resultados.append({
                "auditor":      nombre.replace("auditor_", ""),
                "ok":           False,
                "alertas":      [],
                "error_runner": str(e),
            })

    total_alertas = sum(len(r["alertas"]) for r in resultados)
    errores_runner = sum(1 for r in resultados if r.get("error_runner"))

    if total_alertas == 0 and errores_runner == 0:
        print("[runner] Todo OK — sin alertas, no se envía Telegram")
        return

    reporte = _formatear_reporte(resultados, fecha)
    _enviar_telegram(reporte)
    print(f"[runner] Reporte enviado — {total_alertas} alertas, {errores_runner} errores runner")


if __name__ == "__main__":
    main()
