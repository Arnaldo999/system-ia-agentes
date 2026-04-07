---
name: airtable-expert
description: Especialista en Airtable para System IA. Activar cuando el pedido involucre leer o escribir datos en Airtable, crear filtros de búsqueda, agregar campos a tablas, entender el schema de una base, debuggear errores de API Airtable, hacer PATCH de registros, filtrar propiedades por zona o precio, guardar leads desde el bot, o cualquier operación con las bases de datos de los clientes. También activar ante "guardá en Airtable", "buscá en Airtable", "el campo no guarda", "cómo filtro por X", "qué campos tiene la tabla".
---

# SKILL: Airtable Expert

## Bases de datos activas

| Cliente | Base ID | Tablas principales |
|---------|---------|-------------------|
| Maicol (Back Urbanizaciones) | `appaDT7uwHnimVZLM` | Propiedades, Clientes, Branding, Clientes Activos |
| Robert (Lovbot inmobiliaria) | `appPSAVCmDgHOlRDp` | Propiedades (`tbly67z1oY8EFQoFj`), Clientes (`tblonoyIMAM5kl2ue`) |
| Arnaldo (personal) | `appOUtGnMYHrbLaMa` | Brandbook, Datos Proyecto |

**Token**: `AIRTABLE_TOKEN` env var — PAT con permisos de lectura/escritura sobre las bases asignadas.

## Schema — Maicol Propiedades

| Campo | Tipo | Notas |
|-------|------|-------|
| Nombre | text | Nombre del lote |
| Zona | singleSelect | San Ignacio, Gdor Roca, Apóstoles, Leandro N. Alem, Lote Urbano, Otra zona |
| Precio | number | Precio mensual en ARS (cuota) |
| Estado | singleSelect | Disponible, Vendido, Reservado |
| Descripción | longText | |
| Imagen | attachment | |

## Schema — Maicol Clientes

| Campo | Tipo | Notas |
|-------|------|-------|
| Nombre | text | |
| Teléfono | text | Formato: `5493764815689` (sin +) |
| Zona | singleSelect | igual que Propiedades |
| Objetivo | singleSelect | Inversión, Vivienda, etc. |
| Presupuesto | singleSelect | Hasta $150.000 por mes, Entre $150.000 y $200.000 por mes, Más de $200.000 por mes |
| Urgencia | singleSelect | |
| Score | singleSelect | caliente, tibio, frío |
| Email | email | capturado al final del flujo |
| Fecha | date | ISO 8601 |

## Schema — Maicol Clientes Activos

| Campo | Tipo | Notas |
|-------|------|-------|
| Nombre | text | |
| Teléfono | text | |
| Lote | text | Nombre del lote asignado |
| Monto_Cuota | currency | ARS |
| Fecha_Inicio | date | |
| Próximo_Vencimiento | date | calculado |
| Estado_Pago | singleSelect | Al día, Vencido, Por vencer |
| Cuotas_Pagadas | number | |
| Total_Cuotas | number | |

## Operaciones CRUD — Python (httpx)

### GET — buscar registros con filtro
```python
import httpx

async def _at_buscar(base_id: str, tabla: str, filtro: str = "", token: str = "") -> list[dict]:
    url = f"https://api.airtable.com/v0/{base_id}/{tabla}"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"maxRecords": 50}
    if filtro:
        params["filterByFormula"] = filtro
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(url, headers=headers, params=params)
        r.raise_for_status()
        return r.json().get("records", [])

# Ejemplo: buscar propiedades por zona y precio
filtro = "AND({Zona}='Apóstoles', {Precio}<=200000, {Estado}='Disponible')"
records = await _at_buscar(BASE_ID, "Propiedades", filtro, TOKEN)
props = [{"id": r["id"], **r["fields"]} for r in records]
```

### POST — crear registro
```python
async def _at_crear(base_id: str, tabla: str, campos: dict, token: str = "") -> str:
    url = f"https://api.airtable.com/v0/{base_id}/{tabla}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"fields": campos}
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(url, headers=headers, json=payload)
        r.raise_for_status()
        return r.json().get("id", "")

# Ejemplo: guardar nuevo lead
record_id = await _at_crear(BASE_ID, "Clientes", {
    "Nombre": "Juan Pérez",
    "Teléfono": "5493764000000",
    "Zona": "Apóstoles",
    "Score": "caliente"
}, TOKEN)
```

### PATCH — actualizar campos de registro existente
```python
async def _at_actualizar(base_id: str, tabla: str, record_id: str, campos: dict, token: str = "") -> None:
    url = f"https://api.airtable.com/v0/{base_id}/{tabla}/{record_id}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"fields": campos}
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.patch(url, headers=headers, json=payload)
        r.raise_for_status()

# Ejemplo: guardar email capturado al final del flujo
await _at_actualizar(BASE_ID, "Clientes", record_id, {"Email": "juan@email.com"}, TOKEN)
```

## Fórmulas de filtro — Airtable Formula Language

```
# Igualdad exacta (singleSelect)
{Zona}='Apóstoles'

# Rango numérico
AND({Precio}>=150000, {Precio}<=200000)

# Búsqueda parcial en texto
SEARCH('Juan', {Nombre})

# Múltiples condiciones
AND({Zona}='Lote Urbano', {Estado}='Disponible', {Precio}<=200000)

# Por teléfono (campo text)
{Teléfono}='5493764815689'

# Fecha (ISO 8601)
IS_AFTER({Próximo_Vencimiento}, TODAY())
```

## Limitaciones conocidas (LEER ANTES DE INTENTAR)

| Limitación | Workaround |
|-----------|-----------|
| singleSelect choices NO se agregan vía API con PAT | Agregar manualmente en UI de Airtable |
| Rate limit: 5 req/seg por base | Agregar `asyncio.sleep(0.2)` entre batch requests |
| Attachment upload requiere URL pública | Subir a Cloudinary primero, luego pasar URL |
| Campos de fórmula son read-only | No intentar PATCH en campos calculados |
| `date` fields requieren formato `YYYY-MM-DD` | Nunca pasar datetime con hora para campos date |

## Operaciones desde JS (CRM HTML)

```javascript
const TOKEN = 'patXXXXX';
const BASE = 'appXXXXX';

// GET con filtro
async function buscarPropiedades(zona, precioMax) {
  const formula = `AND({Zona}='${zona}', {Precio}<=${precioMax}, {Estado}='Disponible')`;
  const params = new URLSearchParams({
    filterByFormula: formula,
    maxRecords: '20'
  });
  const res = await fetch(`https://api.airtable.com/v0/${BASE}/Propiedades?${params}`, {
    headers: { Authorization: `Bearer ${TOKEN}` }
  });
  const data = await res.json();
  return data.records.map(r => ({ id: r.id, ...r.fields }));
}

// PATCH
async function actualizarEstado(recordId, campos) {
  await fetch(`https://api.airtable.com/v0/${BASE}/Clientes/${recordId}`, {
    method: 'PATCH',
    headers: { Authorization: `Bearer ${TOKEN}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ fields: campos })
  });
}
```

## Buscar record_id de un cliente por teléfono

```python
async def _at_buscar_cliente_por_phone(phone: str) -> tuple[str, dict] | None:
    records = await _at_buscar(BASE_ID, "Clientes", f"{{Teléfono}}='{phone}'", TOKEN)
    if not records:
        return None
    r = records[0]
    return r["id"], r["fields"]
```
