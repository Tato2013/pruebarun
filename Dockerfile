FROM python:3.11.3

# Establecer el directorio de trabajo dentro del contenedor
WORKDIR /app

# Copiar los archivos de requisitos
COPY /app/requirements.txt .

# Instalar dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código de la aplicación
COPY . .

# Exponer el puerto 8080
EXPOSE 8080

# Comando para ejecutar la aplicación
CMD ["python", "prueba-docker.py"]
