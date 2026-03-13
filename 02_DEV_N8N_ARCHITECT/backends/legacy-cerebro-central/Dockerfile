FROM python:3.11-slim

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
