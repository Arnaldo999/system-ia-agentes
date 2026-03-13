# 🍖 Sistema IA Gastronómico — Memoria del Proyecto

> Última actualización: 2026-03-03  
> Estado: ✅ En producción (Render + Airtable)

---

## 🏗️ Arquitectura del Sistema

```
WhatsApp → n8n (Router) → FastAPI (Render) → Gemini 2.5 Flash Lite
                                    ↓
                              Airtable (Reservas + Conversaciones)
```

| Componente | Tecnología | URL/Ruta |
|---|---|---|
| **Bot conversacional** | FastAPI + Gemini 2.5 Flash Lite | `https://system-ia-agentes.onrender.com/gastronomico/basico/mensaje` |
| **Router principal** | n8n (Easypanel) | Detecta opción 4 → envía a restaurante |
| **Base de datos** | Airtable | `appdA5rJOmtVvpDrx` (Base: Automatizacion-Restaurantes) |
| **Código fuente** | GitHub | `github.com/Arnaldo999/system-ia-agentes` |
| **Worker file** | Python | `workers/gastronomico/worker.py` |

---

## 🤖 Tipo de Agente: Gemini con Historial

**No es máquina de estados.** Es un agente Gemini real con:
- **System prompt completo** (rol, menú, reglas, casos especiales)
- **Historial de conversación** guardado en Airtable (`conversaciones_activas.datos_pedido` como JSON)
- **Function calling simulado** vía línea `ACCION: {...}` al final de cada respuesta
- **Modelo:** `gemini-2.5-flash-lite`

> ⚠️ Versiones anteriores a 2.5 NO funcionan en esta cuenta de Gemini.

---

## 📊 Tablas de Airtable (Arquitectura Relacional CRM)

### 1. `Clientes` (El CRM Central)
| Campo | Tipo | Descripción |
|---|---|---|
| `Teléfono` | **Primary Field** (Text) | Identificador único del cliente (+54911...) |
| `Nombre` | Text | Nombre completo / Apodo |
| `Email` | Email | Para campañas de marketing |
| `Fecha de Cumpleaños` | Date | Para automatizaciones de regalos |
| `Pedidos` | Link to `pedidos` | Permite múltiples registros |
| `Reservas` | Link to `Reservas` | Permite múltiples registros |
| `Fecha de ultima Interaccion`| Last Modified Time | Tracking de retención de clientes |

### 2. `Reservas`
| Campo | Tipo | Descripción |
|---|---|---|
| `ID Reserva` | **Primary Field** (Text/Auto) | RSV-XXXXX |
| `Clientes` | Link to `Clientes` | **SIN múltiples registros** |
| `Nombre del Cliente` | Lookup | Trae `Nombre` de `Clientes` |
| `Fecha y Hora` | Date with time | Cuándo es la reserva |
| `Cantidad de Personas` | Number | Pax |
| `Nro_Mesa` | Text/Number | Lo llena manualmente el Host en el salón |
| `Estado` | Single Select | "pendiente" / "confirmada" / "cancelada" |
| `Especificaciones` | Text | Notas adicionales (alergias, etc.) |

### 3. `pedidos` (Delivery/Takeaway)
| Campo | Tipo | Descripción |
|---|---|---|
| `ID Pedido` | **Primary Field** (Autonumber) | Autonumeración o PED-XXXXX |
| `Clientes` | Link to `Clientes` | **SIN múltiples registros** |
| `Nombre del Cliente` | Lookup | Trae `Nombre` de `Clientes` |
| `Teléfono del Cliente` | Lookup | Trae `Teléfono` de `Clientes` (Vista rápida cajero) |
| `detalle` | Text | Descripción del pedido |
| `total_ars` | Number | Total en ARS |
| `estado_pago` | Single Select | "pendiente" / "confirmado" |
| `estado_entrega` | Single Select | "pendiente" / "en cocina" / "enviado" |

### 4. `conversaciones_activas`
| Campo | Tipo | Descripción |
|---|---|---|
| `telefono` | Text | Identificador del chat |
| `estado_actual` | Text | "activo" |
| `datos_pedido` | Long Text | JSON con historial: `[{"role":"user","content":"..."},...]` |
| `plan_activo` | Text | "basic" |

---

## 🗺️ Flujo de Navegación del Bot

```
📱 Cliente escribe → Bienvenida

🏠 MENÚ PRINCIPAL
  1️⃣ Ver el Menú del día
  2️⃣ Hacer una reserva
  3️⃣ Cancelar una reserva
  4️⃣ Modificar una reserva
  5️⃣ Hacer un pedido con seña
  0️⃣ Volver aquí siempre

  ↓ Opción 1
📋 CATEGORÍAS
  1️⃣ Platos Principales 🥩
  2️⃣ Entradas 🥗
  3️⃣ Postres 🍰
  4️⃣ Cafetería ☕
  5️⃣ Bebidas 🍷
  0️⃣ Menú principal

  ↓ Elige categoría
🍽️ ÍTEMS (3 por categoría con precio)
  0️⃣ Volver a categorías | 00 Menú principal
```

---

## 💡 Lecciones Aprendidas / Reglas Críticas

### Regla de Confirmación de Reservas
**El agente NUNCA confirma que la reserva fue guardada.** Solo dice "Procesando su reserva...". FastAPI ejecuta `at_crear_reserva()`, verifica el código HTTP 200, y solo entonces envía la confirmación real con el número de reserva. Si falla, envía error honesto.

### Flujo técnico de acción:
```python
# Agente genera texto + "ACCION: {...}"
# FastAPI separa texto de ACCION
# FastAPI ejecuta at_crear_reserva()
# Si ok=True → usa mensaje_confirmacion de FastAPI (NO del agente)
# Si ok=False → usa mensaje_error honesto
```

### Historial en Airtable
El campo `datos_pedido` guarda una **lista JSON** de hasta 20 turnos:
```json
[
  {"role": "user", "content": "Hola"},
  {"role": "model", "content": "¡Bienvenido!..."},
  ...
]
```
Si el campo tiene formato viejo (dict `{}`), se reinicia automáticamente.

### Bugs resueltos (2026-03-03)

**cancelar_reserva no tocaba Airtable:**
- Causa: la función `ejecutar_accion` para `cancelar_reserva` solo notificaba al dueño sin hacer ningún PATCH
- Fix 1: agregar búsqueda + PATCH en `Especificaciones` con nota "CANCELADA el..."
- Fix 2: la búsqueda `AND({Nombre}=..., {telefono}=...)` fallaba por case-sensitivity. Se cambió a buscar solo por `{telefono}` (sort Fecha DESC, maxRecords 1)

**Bot cuestionaba fechas innecesariamente:**
- Causa: prompt decía "SIEMPRE verificá el día de semana matemáticamente"
- Fix: solo verificar si el cliente menciona explícitamente nombre de día + fecha contradictoria, o si el día es lunes (cerrado)

**Delivery no calculaba en el mismo turno:**
- Causa: el agente interpretaba los pasos del prompt como turnos separados y decía "procederé a calcular..."
- Fix: instrucción explícita "en ese MISMO mensaje hacé las tres cosas juntas" + "⚠️ NUNCA digas procederé a calcular"

**Opción 5 era "Reserva con seña 30%" en vez de "Delivery con seña 10%":**
- Fix: reescribir opción 5 completamente → delivery con seña del 10%, flujo: ítems → total+seña+alias → comprobante → dirección → crear_pedido

---

## 🎭 Personalidad del Agente

- **Nombre:** Alberto
- **Tono:** Cordial, profesional, español neutro
- **PROHIBIDO:** "che", "vos", "dale", "genial", "bárbaro", "re", "copado", "pibe"
- **Permitido:** Trato de "usted" o "tú" según el contexto
- **Emojis:** Máximo 1-2 por mensaje

---

## 🍽️ Menú Demo (La Parrilla de Don Alberto)

| Categoría | Platos | Precio ARS |
|---|---|---|
| Platos Principales | Asado de Tira (400gr) + papas | 6.800 |
| | Bife de Chorizo (300gr) + ensalada | 7.500 |
| | Bondiola Braseada + puré de calabaza | 5.900 |
| Entradas | Provoleta fundida | 2.500 |
| | Empanadas Tucumanas (3 un.) | 2.700 |
| | Tabla de Fiambres | 4.500 |
| Postres | Flan Casero + dulce de leche | 1.500 |
| | Mousse de Chocolate | 1.600 |
| | Panqueques + dulce de leche | 1.800 |
| Cafetería | Café Espresso | 800 |
| | Cortado + medialunas (2) | 1.200 |
| | Submarino | 1.100 |
| Bebidas | Vino Malbec (copa) | 2.200 |
| | Cerveza Artesanal (pint) | 1.800 |
| | Limonada con menta | 1.200 |

- Horario: **Martes a Domingo** — Almuerzo 12-16hs, Cena 20-00hs. **Lunes cerrado.**
- Alias pago seña: `donalberto.parrilla`

---

## 🔗 Endpoints Disponibles

| Endpoint | Método | Descripción |
|---|---|---|
| `/gastronomico/basico/mensaje` | POST | Endpoint principal del bot |
| `/gastronomico/debug/airtable` | GET | Verifica conexión con Airtable |
| `/gastronomico/debug/test-reserva` | GET | Crea reserva de prueba |
| `/gastronomico/debug/reset/{telefono}` | GET | Borra historial del teléfono |

---

## 📋 Variables de Entorno Requeridas (Render)

```
GEMINI_API_KEY=...
AIRTABLE_API_KEY=patL8VOuEL6GadewF...
AIRTABLE_BASE_ID=appdA5rJOmtVvpDrx
NUMERO_DUENO=549376...
EVOLUTION_API_URL=...       (opcional, para notificar al dueño)
EVOLUTION_INSTANCE=...      (opcional)
EVOLUTION_API_KEY=...       (opcional)
```

---

## ✅ Plan BÁSICO — Estado actual (2026-03-03)

- [x] Menú interactivo por categorías (2 pasos)
- [x] Hacer reserva → guarda en Airtable con nro RSV-XXXXX
- [x] Cancelar reserva → PATCH sobre fila existente (búsqueda por teléfono)
- [x] Modificar reserva → PATCH sobre fila existente
- [x] Delivery sin seña → calcula total + pide dirección en 1 turno → guarda en tabla pedidos
- [x] Delivery con seña (opción 5) → 10% del total → alias → comprobante → dirección → crear_pedido
- [x] Anti-alucinaciones: "Procesando..." + FastAPI confirma con resultado real
- [x] Notificación al dueño en cada acción (requiere Evolution API configurada)

## 🚧 Pendiente / Post-Demo

- [ ] Botones interactivos de WhatsApp (sendList / sendButtons) desde n8n
- [ ] Verificación real de comprobante de seña (recibir imagen)
- [ ] Notificación al dueño por WhatsApp (Evolution API — vars configuradas pero sin instancia)
- [ ] Limpiar endpoints /debug antes de producción real
- [ ] Multi-cliente: extraer menú y datos desde Airtable/Supabase por `cliente_id`
