# Usa una imagen base de Python
FROM python:3.9

# Establece el directorio de trabajo dentro del contenedor
WORKDIR /app

# Copia el archivo de requisitos al contenedor
COPY requirements.txt requirements.txt

# Instala las dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Copia todos los archivos de la aplicación al contenedor
COPY . .

# Exponer el puerto en el que se ejecutará la aplicación
EXPOSE 5000

# Comando por defecto para ejecutar la aplicación
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "master_app:app"]
