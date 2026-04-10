# Directiva: Debug Worker & n8n

**Cuándo usar**: Bot no responde, error 500, webhook no llega, Airtable no guarda, Gemini devuelve basura, workflow n8n roto, deploy falló.

## Entradas requeridas

| Campo | Descripción |
|-------|-------------|
| `síntoma` | Descripción del error o comportamiento inesperado |
| `proyecto` | maicol \| prueba \| social \| lovbot-robert \| [nombre] |
| `capa` | bot \| n8n \| airtable \| deploy \| desconocido |

## Herramientas

| Recurso | Propósito |
|---------|-----------|
| `memory/debug-log.md` | Bugs conocidos y sus fixes — **leer primero** |
| `memory/bugs_integraciones.md` | Bugs de Airtable, Cal.com, Render |
| Logs Coolify UI | Ver stderr/stdout del worker en tiempo real |
| `python -m py_compile` | Verificar sintaxis antes de cualquier deploy |

## Paso 1 — Leer historial antes de investigar

```
memory/debug-log.md
memory/bugs_integraciones.md
```

Si el bug ya está documentado → aplicar el fix conocido directamente.

## Paso 2 — Árbol de diagnóstico

```
Bot no responde al mensaje
├── ¿El webhook llega al servidor?
│   ├── NO → problema DNS/URL/Coolify — verificar health endpoint
│   └── SÍ → revisar logs del worker en Coolify UI
│
├── ¿Error en los logs?
│   ├── 401 Airtable → token expirado o sin permisos
│   ├── 422 httpx   → payload mal formado (revisar campos enviados)
│   ├── timeout     → httpx sin timeout configurado, o Gemini lento
│   ├── KeyError    → campo faltante en sesión o JSON del webhook
│   └── 500 interno → leer stack trace completo en logs
│
├── ¿Bot responde dos veces?
│   └── Falta deduplicación MENSAJES_PROCESADOS — ver worker Maicol como referencia
│
└── ¿n8n workflow no ejecuta?
    ├── Toggle desactivado → activar manualmente en n8n UI
    ├── Credencial expirada → revisar nodo HTTP con credencial
    └── Error en nodo → ver ejecuciones fallidas en n8n UI
```

## Paso 3 — Fixes comunes

### Airtable 422 — campo singleSelect
```python
# MAL
"fields": {"Estado": "activo"}
# BIEN  
"fields": {"Estado": {"name": "activo"}}
```

### Airtable — campo date
```python
# Formato requerido: YYYY-MM-DD
from datetime import date
"fields": {"Fecha": date.today().isoformat()}
```

### Worker responde dos veces
```python
# Agregar al inicio del handler
if mensaje_id in MENSAJES_PROCESADOS:
    return {"status": "already_processed"}
MENSAJES_PROCESADOS.add(mensaje_id)
```

### n8n workflow no activa
→ MCP no puede activar toggles. Ir a n8n UI manualmente y activar el workflow.

### Gemini devuelve JSON malformado
```python
# Usar json.loads con fallback
try:
    resultado = json.loads(respuesta_gemini)
except json.JSONDecodeError:
    # Limpiar markdown code blocks si los incluye
    limpio = respuesta_gemini.strip().removeprefix("```json").removesuffix("```").strip()
    resultado = json.loads(limpio)
```

## Paso 4 — Ciclo auto-reparación

1. Identificar el error exacto (stack trace completo)
2. Aplicar fix en el script
3. Validar: `python -m py_compile [worker]`
4. Deploy: seguir `directives/deploy_worker.md`
5. Test: mandar "hola" al número y verificar flujo
6. **Documentar en `memory/debug-log.md`** si es un bug nuevo

## Paso 5 — Escalar al usuario si

- El error involucra tokens de pago (Gemini, Meta API) — no reintentar sin confirmar
- El stack trace apunta a una librería externa (puede ser bug de versión)
- Llevas 3 iteraciones sin resolver — describir síntoma + lo intentado

## Casos límite conocidos

- **Render**: deploy lag de 30-60s. Health puede devolver 503 durante cold start.
- **YCloud retries**: puede reenviar el mismo mensaje hasta 3 veces. Siempre deduplicar.
- **Cal.com slots**: endpoint cambia según zona horaria del cliente. Ver `bugs_integraciones.md`.
- **n8n 2.35.6**: bug conocido con nodos IF anidados. Ver `memory/debug-log.md`.
