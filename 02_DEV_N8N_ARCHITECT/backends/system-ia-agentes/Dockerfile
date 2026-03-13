FROM python:3.11-slim

# Instalar fuentes tipográficas para Pillow (slides de carrusel)
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-dejavu-core wget unzip \
    && mkdir -p /app/fonts \
    && wget -q -O /tmp/Inter.zip "https://github.com/rsms/inter/releases/download/v4.1/Inter-4.1.zip" \
    && unzip -j /tmp/Inter.zip "Inter-4.1/InterDesktop/Inter-Bold.otf" -d /app/fonts/ 2>/dev/null || true \
    && unzip -j /tmp/Inter.zip "Inter-4.1/InterDesktop/Inter-Regular.otf" -d /app/fonts/ 2>/dev/null || true \
    && rm -f /tmp/Inter.zip \
    && apt-get purge -y wget unzip && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Directorio de trabajo en el servidor
WORKDIR /app

# Copiar el archivo de requerimientos e instalar las librerías
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo nuestro código (main.py) adentro del contenedor
COPY . .

# El puerto estándar que usa FastAPI
EXPOSE 8000

# El comando que enciende la aplicación usando Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
