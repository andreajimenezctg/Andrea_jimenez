import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

db_name = os.getenv('DB_NAME')
db_user = os.getenv('DB_USER')
db_password = os.getenv('DB_PASSWORD')
db_host = os.getenv('DB_HOST')
db_port = os.getenv('DB_PORT')

print(f"Intentando conectar a {db_name} con el usuario {db_user} en {db_host}:{db_port}...")

try:
    conn = psycopg2.connect(
        dbname=db_name,
        user=db_user,
        password=db_password,
        host=db_host,
        port=db_port
    )
    print("✅ Conexión exitosa a la base de datos")
    conn.close()
except Exception as e:
    print(f"❌ Error al conectar: {e}")
    try:
        # Intentar obtener el mensaje de error con la codificación adecuada
        print(f"Error (repr): {repr(e)}")
    except:
        pass
