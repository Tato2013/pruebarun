import cv2
import os
import time
import base64
import threading
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
import telegram
from telegram import InputFile
import requests
from google.cloud import storage
import io


# Configurar Gemini AI
GOOGLE_API_KEY = "AIzaSyA9XPSNUrazfJEGGepN6c0wMIbFKtBMqf8"  
os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY
gemini_model = ChatGoogleGenerativeAI(model="gemini-2.0-flash-lite")

#TOKEN = '8055850538:AAHjWPI4-by_f17x5TYlCOKLJEjFXtS2sew'
#CHAT_ID = '2064406703'
TOKEN = '7769702723:AAFQeomDaRlZWEaLnzaYAr0oHO2dk_I-ESQ'

CHAT_ID = '-1002632538686'

bot = telegram.Bot(token=TOKEN)

# Carpetas y archivos de salida
#THEFT_FRAME_FOLDER = "theft_frames"
#os.makedirs(THEFT_FRAME_FOLDER, exist_ok=True)
#OUTPUT_FILE = "observations.txt"

# Configuración de tiempo
last_sent_time = 0
SEND_INTERVAL = 1  # Captura cada 4 segundos

frame_list = []

def send_image_to_telegram(image_base64, message):
    """Envía una imagen base64 y un mensaje a Telegram"""
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    
    # Convertir la imagen base64 a bytes
    image_data = base64.b64decode(image_base64)
    files = {
        'photo': ('image.jpg', image_data, 'image/jpeg')
    }
    payload = {
        'chat_id': CHAT_ID,
        'caption': message  # El mensaje que quieres enviar junto con la imagen
    }
    
    response = requests.post(url, data=payload, files=files)
    
    # Si hay un error en la respuesta, lo muestra
    if response.status_code != 200:
        print(f"Error al enviar la imagen: {response.status_code}")
    else:
        print("Imagen enviada correctamente.")

def analyze_with_gemini(frame, timestamp):
    """Envía un frame clave a Gemini AI para analizar hurto."""
    try:
        # Convertir el frame a base64 en memoria
        _, buffer = cv2.imencode('.jpg', frame)
        base64_image = base64.b64encode(buffer).decode("utf-8")

        message = HumanMessage(
            content=[

                {"type": "text", "text": """
                Observe the **Shelving area of this store** and respond in a structured format.

                If any item from the store is taken and concealed in a wallet/purse/under clothing, it constitutes an act 
                of shoplifting detected(**"Yes"**), provide details of the **suspect**.

                NO More Details  
                
                | Suspicious Activity shoplifting Counter | Observed? (Yes/No) | Suspect Description (If Yes) |

                |--------------------------------------|--------------------|-----------------------------|

                | Item stolen from the store?      |                    |                             |

                If theft is detected, describe the **clothing, appearance, and any identifiable features** of the suspect.
                Otherwise, leave the details column empty.
                """},

                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}

            ]
        )

        response = gemini_model.invoke([message])
        observation = response.content.strip()

        print(f"🔍 Respuesta de Gemini: {observation}")

        # Verificar explícitamente si dice "Yes"
        if "| Yes" in observation:
            message = f"Observación de hurto detectada:\n{observation}\nHora: {timestamp}"
            send_image_to_telegram(base64_image, message)  # Enviar la imagen en base64 a Telegram

            # Escribir observación en archivo de texto
            #with open(OUTPUT_FILE, "a", encoding="utf-8") as file:
            #    file.write(f"{timestamp} - {observation}\n")

            print(f"✅ Observación de hurto guardada: {observation}")

    except Exception as e:
        print(f"❌ Error analyzing image: {e}")

def process_frame(frame):
    """Procesa el frame y lo envía a Gemini cada 4 segundos."""
    global last_sent_time

    if frame is None or frame.size == 0:
        print("⚠️ Frame vacío, saltando...")
        return

    current_time = time.time()
    if current_time - last_sent_time >= SEND_INTERVAL:
        last_sent_time = current_time

        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        
        # Almacenar el frame en la lista
        frame_list.append((frame, timestamp))

        # Enviar los frames uno por uno a Gemini
        for frame, timestamp in frame_list:
            ai_thread = threading.Thread(target=analyze_with_gemini, args=(frame, timestamp))
            ai_thread.daemon = True
            ai_thread.start()

        # Limpiar la lista de frames después de procesarlos
        frame_list.clear()

def start_monitoring(video_file):
    """Procesa video en tiempo real y detecta hurto."""
    cap = cv2.VideoCapture(video_file)
    if not cap.isOpened():
        print("❌ Error: No se pudo abrir el video.")
        return

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.resize(frame, (1020, 500))
        process_frame(frame)

    cap.release()
    print("✅ Monitoring Completed.")

if __name__ == "__main__":
    client = storage.Client()

    # Obtener el bucket
    bucket_name = "shoplitf-videos"
    bucket = client.get_bucket(bucket_name)

    # Obtener todos los blobs (archivos) del bucket
    blobs = bucket.list_blobs()

    # Filtrar solo los videos con las extensiones .mp4, .avi, .mov
    videos = [blob.name for blob in blobs if blob.name.endswith(('.mp4', '.avi', '.mov'))]

    # Verificar si no se encontraron videos en el bucket
    if not videos:
        print("❌ No se encontraron videos en el bucket.")
        exit(1)

    # Procesar cada video
    for video in videos:
        print(f"Procesando video: {video}")
        
        # Obtener el objeto blob
        blob = bucket.blob(video)

        # Leer el video directamente en memoria
        video_stream = io.BytesIO()
        blob.download_to_file(video_stream)

        # Volver a posicionar el puntero del flujo en el inicio para OpenCV
        video_stream.seek(0)

        # Llamar a la función para procesar el video
        start_monitoring(video_stream)

    print("✅ Procesamiento finalizado.")