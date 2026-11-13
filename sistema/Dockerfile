# Imagen de PreVet (PV-TEC-02): el sistema listo para correr en cualquier equipo con Docker.
# Las instrucciones paso a paso están en INSTALACION.md, en la raíz del repositorio.
FROM python:3.12-slim

# Sin archivos .pyc y con los mensajes de Django apareciendo al tiro en la consola.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Primero solo las dependencias: si no cambian, Docker reutiliza esta capa y
# volver a construir la imagen toma segundos.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Al arrancar crea o actualiza las tablas y levanta el servidor. 0.0.0.0 para
# que se pueda abrir desde el navegador del computador, fuera del contenedor.
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py runserver 0.0.0.0:8000"]
