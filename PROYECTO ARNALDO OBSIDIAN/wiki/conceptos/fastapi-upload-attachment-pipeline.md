---
title: FastAPI — Pipeline de upload de archivos a Airtable via URL pública
tags: [fastapi, airtable, upload, multipart, static-files, attachment, patron-tecnico, compartido]
source_count: 1
proyectos_aplicables: [mica, arnaldo]
proyecto: compartido
---

# FastAPI — Pipeline Upload → Airtable Attachments

## Definición

Patrón para cargar archivos (PDFs, imágenes, documentos) desde un CRM frontend HTML hacia un campo `multipleAttachments` de Airtable, usando FastAPI como intermediario.

**Airtable no acepta binarios directos**: requiere una URL pública desde donde descargar el archivo.

## Flujo completo

```
Browser (FormData) 
  → POST /crm/upload (FastAPI, UploadFile)
  → guarda en /uploads/ (directorio estático)
  → retorna URL pública: https://agentes.arnaldoayalaestratega.cloud/uploads/filename.pdf
  → el caller incluye esa URL en el payload de Airtable
  → Airtable descarga el archivo desde la URL y lo almacena en su propio CDN
```

## Implementación FastAPI

### Endpoint de upload (`router.py`)

```python
import shutil
from pathlib import Path
from fastapi import APIRouter, UploadFile, File

UPLOAD_DIR = Path("/uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
BASE_URL = "https://agentes.arnaldoayalaestratega.cloud"

@router.post("/crm/upload")
async def upload_archivo(archivo: UploadFile = File(...)):
    filename = f"{uuid.uuid4()}_{archivo.filename}"
    dest = UPLOAD_DIR / filename
    with dest.open("wb") as f:
        shutil.copyfileobj(archivo.file, f)
    return {"url": f"{BASE_URL}/uploads/{filename}"}
```

### Mount estático en `main.py`

```python
from fastapi.staticfiles import StaticFiles
app.mount("/uploads", StaticFiles(directory="/uploads"), name="uploads")
```

### Payload a Airtable

```python
fields = {
    "Adjunto DNI": [{"url": url_devuelta_por_upload}]
    # Airtable descarga automáticamente desde esa URL
}
airtable.update_record("Clientes_Estudio", record_id, fields)
```

### Frontend (JS)

```javascript
async function uploadArchivoAlBackend(file) {
    const formData = new FormData();
    formData.append("archivo", file);
    const resp = await fetch("/crm/upload", { method: "POST", body: formData });
    const data = await resp.json();
    return data.url;  // URL pública del archivo
}
```

## Consideraciones

- **Persistencia**: los archivos en `/uploads/` son efímeros si el container se recrea sin volume. Para producción, configurar un volume Coolify o mover a S3/R2.
- **Seguridad**: actualmente `/uploads/` es público sin autenticación. Para documentos sensibles (DNI, escrituras), considerar presigned URLs o auth middleware.
- **Tamaño**: Airtable tiene límite de 5MB por attachment en plan gratuito, 20MB en Pro.
- **Naming**: usar UUID prefix para evitar colisiones entre subidas simultáneas.

## Fuentes que lo mencionan

- [[wiki/fuentes/sesion-2026-04-27-crm-juridico-v2]] — implementado en CRM Jurídico v2 Mica

## Notas

Este patrón es reutilizable en cualquier CRM que use Airtable como backend y necesite attachments. También aplica a Evolution (que acepta archivos base64 o URL), y con adaptaciones menores a PostgreSQL (guardar la URL en un campo TEXT).
