# Testing Policy

## Tipos de Pruebas

1. **Pruebas Manuales / Ad-hoc (`scripts/manual_tests/`)**:
   Scripts usados para verificar integraciones, ver schemas de respuestas de APIs (n8n, Airtable, Meta) o realizar pruebas rápidas exploratorias.
   - Estos archivos se encuentran en `scripts/manual_tests/`.
   - Se ejecutan manualmente con `python scripts/manual_tests/<nombre_archivo>.py`.

2. **Pruebas Automáticas (`tests/`)**:
   Pruebas unitarias o de integración diseñadas para ser corridas mediante un framework de pruebas (ej. `pytest`).
   - Estos archivos van en la carpeta `tests/`.
   - Se ejecutan con `pytest tests/`.

## Regla Estricta: Cero Secretos en Código (No Secrets Policy)

Por seguridad del sistema y de los clientes, **está terminantemente prohibido hardcodear** dentro del código de este repositorio:
- Tokens de acceso (Meta, Twilio, ElevenLabs, OpenAI, Vapi, etc.).
- Personal Access Tokens (PATs) o Base IDs críticos de Airtable/Supabase.
- Teléfonos reales de clientes o usuarios.
- Contraseñas o Keys de bases de datos.

### Qué hacer en su lugar
Si un script necesita acceder a un entorno o hacer un llamado de API:
1. Usar variables de entorno (`os.getenv("NOMBRE_VARIABLE")`).
2. Cargar las variables usando `python-dotenv` si es necesario, apuntando a un archivo local `.env` que contenga las credenciales.
3. Declarar el nombre de la variable en el archivo `.env.example` en la raíz (sin el valor real) para que el resto del equipo sepa qué variable debe configurar localmente.

### Validación Continua
Antes de hacer commit, se debe ejecutar el chequeo anti-secretos para verificar que no se nos haya escapado un token:
```bash
./scripts/check_secrets.sh
```
