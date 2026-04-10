---
name: debug-worker
description: Diagnóstico y reparación de workers FastAPI y workflows n8n de System IA. Activar ante cualquier error, falla, comportamiento inesperado o bug: "el bot no responde", "falló el deploy", "el webhook no llega", "Airtable no guarda", "Gemini devuelve basura", "el workflow se rompe", "error 500", "no funciona", "se cayó", "debug", "falla", "falló". Leer memory/debug-log.md primero.
---

# SKILL: Debug Worker & n8n

## Paso 1: Leer el historial de bugs conocidos

```
memory/debug-log.md   ← bugs documentados y sus fixes
```

## Árbol de diagnóstico rápido

```
Bot no responde al mensaje
├── ¿El webhook llega al servidor?
│   ├── NO → problema de URL/DNS/Coolify
│   └── SI → revisar logs del worker
│
├── ¿Error en los logs?
│   ├── 401 Airtable → token expirado o sin permisos
│   ├── 422 httpx → payload mal formado
│   ├── timeout → httpx sin timeout, o Gemini lento
│   └── KeyError → campo faltante en sesión o JSON
│
├── ¿Bot responde dos veces?
│   └── Falta deduplicación MENSAJES_PROCESADOS
│
├── ¿Bot repite el mismo step?
│   └── `sesion["step"]` no se actualiza antes de enviar
│
└── ¿Bot usa datos incorrectos (zona, precio)?
    └── Número no convertido a texto antes de guardar en sesión
        → Verificar MAPA_ZONA, MAPA_PRESUPUESTO, etc.
```

## Bugs conocidos — soluciones documentadas

### 1. Airtable singleSelect falla silenciosamente
**Síntoma**: PATCH/POST no guarda el campo, no hay error  
**Causa**: El valor no existe en las opciones del singleSelect  
**Fix**: Verificar opciones en Airtable UI. NO se pueden agregar vía API con PAT estándar.

### 2. YCloud reintenta webhooks → doble mensaje
**Síntoma**: El bot responde dos veces al mismo mensaje  
**Fix**:
```python
MENSAJES_PROCESADOS: set[str] = set()

msg_id = msg.get("id", "")
if msg_id in MENSAJES_PROCESADOS:
    return {"status": "duplicate"}
MENSAJES_PROCESADOS.add(msg_id)
if len(MENSAJES_PROCESADOS) > 1000:
    MENSAJES_PROCESADOS.clear()
```

### 3. Meta Graph API retorna 401
**Causa A**: Token de System User no asignado al WABA antes de generarlo  
**Fix A**: En Business Manager → Sistema de usuarios → Asignar al WABA "Roberto" → Regenerar token  
**Causa B**: Token vencido (60 días por defecto)  
**Fix B**: Regenerar token en BM → cargar en Coolify

### 4. Coolify env var no se aplica
**Síntoma**: Worker usa valor viejo o vacío  
**Fix**: Verificar en Coolify UI que la var existe Y que el servicio se redesplegó después de guardar

### 5. Gemini devuelve texto con formato extra
**Síntoma**: Scoring devuelve "caliente." o "**caliente**" en vez de "caliente"  
**Fix**:
```python
resultado = await _call_gemini_text(prompt)
# Limpiar
resultado = resultado.lower().strip().strip("*").strip(".").strip()
```

### 6. httpx timeout en producción
**Síntoma**: 504 o error de red intermitente  
**Fix**: Siempre especificar timeout explícito:
```python
async with httpx.AsyncClient(timeout=15) as c:  # Airtable/YCloud
async with httpx.AsyncClient(timeout=30) as c:  # Gemini
```

### 7. n8n webhook: datos bajo `$json.body` vs `$json`
**Síntoma**: Campo undefined en nodo n8n  
**Fix**: En n8n, datos de webhook SIEMPRE bajo `$json.body`, no `$json` directamente:
```javascript
// MAL
const phone = $json.phone;
// BIEN
const phone = $json.body.phone;
```

### 8. Cal.com slots vacíos
**Causa**: Zona horaria mal configurada en la llamada a la API  
**Fix**: Pasar `timeZone=America/Argentina/Posadas` en el request de slots

## Comandos de diagnóstico

```bash
# Ver logs del worker en Coolify (desde terminal con acceso SSH al VPS)
docker logs [nombre-contenedor] --tail 100 -f

# Test local del worker
cd 01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Simular webhook YCloud localmente
curl -X POST http://localhost:8000/maicol/webhook \
  -H "Content-Type: application/json" \
  -d '{"message":{"id":"test123","from":"5493764000000","text":{"body":"hola"}}}'

# Simular webhook Meta localmente  
curl -X POST http://localhost:8000/meta/webhook \
  -H "Content-Type: application/json" \
  -d '{"entry":[{"changes":[{"value":{"messages":[{"id":"mid1","from":"5491234567","text":{"body":"hola"}}],"metadata":{"phone_number_id":"735319949657644"}}}]}]}]}'

# Test Airtable directo
curl -H "Authorization: Bearer $AIRTABLE_TOKEN" \
  "https://api.airtable.com/v0/appaDT7uwHnimVZLM/Clientes?maxRecords=3"

# Validar workflow n8n con MCP
# (usar herramienta mcp__n8n__n8n_validate_workflow con profile: "runtime")
```

## Debug n8n — pasos

```
1. Abrir workflow en UI
2. Activar "Always Output Data" en nodo fallido
3. Ejecutar con "Execute step" en el nodo problemático
4. Revisar OUTPUT — si está vacío, el nodo anterior no pasó datos
5. Verificar expresiones: usar {{ $json.body.campo }} para webhooks
6. Si error de validación: usar mcp__n8n__n8n_validate_workflow profile="runtime"
7. Fix → validate → fix (2-3 iteraciones es normal)
```

## Checklist post-fix

- [ ] ¿El fix resuelve el síntoma sin romper otro step?
- [ ] ¿Se probó con un mensaje real o simulado?
- [ ] ¿Se actualizó `memory/debug-log.md` con el bug y el fix?
- [ ] ¿Se hizo commit y push si el fix es en código?
- [ ] ¿Coolify redesplegó correctamente?

## Formato para documentar en memory/debug-log.md

```markdown
## [Fecha] — [Worker/Workflow] — [Síntoma breve]
**Causa**: [explicación técnica]
**Fix aplicado**: [código o configuración]
**Prevención**: [cómo evitarlo en el futuro]
```
