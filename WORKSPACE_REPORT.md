# 📂 Informe de Estructura: Workspace INGENIERO N8N
**Estado del Sistema:** Activo y Organizado 🚀
**Última Actualización:** 2026-03-13
**Relación con Proyecto:** n8n + FastAPI (Easypanel)

Este informe resume la organización actual de tu entorno de trabajo para facilitar la navegación y el mantenimiento del sistema.

---

## 🏗️ 1. Directorios Estratégicos

### 📝 `memory/` (Centro de Conocimiento)
El corazón logístico. Aquí guardamos la "verdad" de cada proyecto y cliente.
- **`nuevo-cliente-redes-sociales.md`**: El checklist obligatorio para sumar clientes.
- **`guia-ventas-micaela.md`**: Estrategia comercial presencial.
- **`restaurante-gastronomico.md`**: Documentación técnica del bot de pedidos/reservas.

### 🎯 `CAPTACION_LEADS/` (Motor de Prospección)
Donde vive la maquinaria para atraer nuevos clientes.
- **`guia_investigacion_autos_luxury.html`**: Guía técnica/comercial para el rubro automotor.
- **Scrappers**: Archivos JSON para extracción de datos de Google Maps.

### 💎 `PROPUESTAS/` (Ventas y Cierre)
Material listo para entregar que demuestra el valor de System IA.
- **PDFs Temáticos**: WhatsApp, CRM, Redes Sociales.
- **Presentaciones HTML**: Dashboards y Speeches interactivos.

---

## 💻 2. Núcleo Tecnológico (Codebase)

- **`system-ia-agentes/`**: Repositorio del "Cerebro" FastAPI en Render. Aquí están los workers de IA.
- **`system-ia-cerebro-central/`**: Lógica de orquestación central de la agencia.
- **`n8n-mcp / n8n-skills`**: Herramientas que permiten a la IA interactuar con n8n con precisión quirúrgica.

---

## 🤖 3. Reglas y Gobernanza de IA

- **`.agents/` & `.claude/`**: Directorios con las reglas que definen mis habilidades como tu ingeniero experto en n8n.
- **`CLAUDE.md`**: Reglas de estilo y prohibiciones técnicas (JSON puro, sin placeholders, etc.).
- **`ai.context.json`**: Mapa de contexto para que la IA no pierda el hilo de los proyectos activos.

---

## 🧭 4. Resumen de Flujo /INIT

Para cualquier tarea nueva, el sistema sigue este orden:
1. **Identificar**: ¿Es comercial (`PROPUESTAS`) o técnico (`memory`)?
2. **Consultar**: Leer los archivos en `memory/` correspondientes.
3. **Ejecutar**: Usar las herramientas MCP para n8n o modificar el código en `system-ia-agentes`.
4. **Validar**: Bucle de validación multi-nivel antes de dar por terminada la tarea.

---
**Informe generado por Antigravity.** El workspace se encuentra en estado óptimo.
