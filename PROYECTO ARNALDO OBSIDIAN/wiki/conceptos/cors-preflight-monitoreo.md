---
title: "CORS preflight como check de monitoreo"
tags: [cors, monitoreo, patrones, seguridad, alertas]
source_count: 1
proyectos_aplicables: [arnaldo, robert, mica]
---

# CORS preflight como check de monitoreo

## Definición

Patrón de monitoreo que valida no solo que un backend responde, sino que **acepta correctamente requests cross-origin del frontend que se espera que lo consuma**.

Un backend puede estar `running:healthy` pero seguir bloqueando al frontend por configuración CORS incompleta. Sin un check específico de preflight CORS, el monitoreo dice "todo OK" mientras el cliente real ve "Failed to fetch".

## Cómo se implementa

```python
def check_cors_preflight(backend_url: str, origin: str, request_method: str = "GET"):
    """
    Hace un preflight OPTIONS al backend simulando el browser.
    Falla si:
    - Status no es 200/204
    - Falta header Access-Control-Allow-Origin
    - El header no contiene el origin esperado ni '*'
    """
    headers = {
        "Origin": origin,
        "Access-Control-Request-Method": request_method,
    }
    response = requests.options(backend_url, headers=headers, timeout=10)

    if response.status_code not in [200, 204]:
        return False, f"HTTP {response.status_code}"

    acao = response.headers.get("Access-Control-Allow-Origin", "")
    if acao != origin and acao != "*":
        return False, f"ACAO esperado={origin}, recibido={acao or '(vacío)'}"

    return True, f"CORS ok (ACAO={acao})"
```

## Cuándo es crítico tenerlo

- Frontend en dominio distinto del backend (caso típico de [[crm-v2-modelo-robert]] y [[crm-v2-modelo-mica]] que viven en Vercel y pegan a backends Coolify).
- Backend tiene whitelist explícita de origins (no `*`).
- El equipo agrega/quita orígenes con frecuencia (clientes nuevos = origins nuevos).

## Caso real que motivó el patrón (2026-04-22)

El CRM de [[maicol]] (`crm.backurbanizaciones.com`) dejó de cargar datos. El backend FastAPI [[arnaldo-ayala|Arnaldo]] estaba `running:healthy` (pasaba el check tradicional de "responde 200"), pero su `CORSMiddleware` no tenía el dominio del CRM en `allow_origins`. Los preflight OPTIONS recibían respuesta sin header `Access-Control-Allow-Origin` y el browser bloqueaba todos los fetch.

**El cliente avisó antes que el monitor.** A partir de ese día se sumaron checks de preflight CORS por cada CRM cliente.

## Implementación actual en el ecosistema

Ver [[sistema-auditoria]]. Los siguientes checks usan este patrón:

- `maicol_crm_cors` → preflight `OPTIONS https://agentes.arnaldoayalaestratega.cloud/clientes/arnaldo/maicol/crm/propiedades` con Origin `https://crm.backurbanizaciones.com`.
- `robert_crm_cors` → preflight `OPTIONS https://agentes.lovbot.ai/health` con Origin `https://crm.lovbot.ai`.
- `mica_crm_cors` → preflight equivalente para Mica (deshabilitado hasta dominio prod definido).

## Reglas operativas

1. **Por cada frontend nuevo en dominio externo**, sumar un check de preflight CORS al monitor.
2. **El Origin debe ser el dominio público real del frontend** (no `localhost`, no IP).
3. **Aceptar tanto el origin específico como `*`** como respuesta válida (algunos backends permisivos).
4. **El timeout debe ser corto** (10s) — si el preflight tarda más, ya hay otro problema.

## Fuentes que lo mencionan

- [[wiki/fuentes/sesion-2026-04-22]] — origen del patrón
