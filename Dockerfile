FROM python:3.11-slim

WORKDIR /app

# Copiamos requerimientos y los instalamos
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos nuestra API
COPY main.py .

# Exponemos el puerto 8000 para Easypanel
EXPOSE 8000

# Iniciamos el servidor de forma que Easypanel lo lea sin problemas
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
