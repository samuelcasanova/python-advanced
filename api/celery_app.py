import os
import time
import json
import csv
from celery import Celery
from celery.schedules import crontab
import database
import models

# Configuración de Celery
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
celery = Celery("tasks", broker=REDIS_URL, backend=REDIS_URL)

# Directorio para archivos compartidos
SHARED_DIR = "/app/shared"
os.makedirs(SHARED_DIR, exist_ok=True)

# Tarea 1: Simulación de envío de email
@celery.task(name="send_notification_email")
def send_notification_email(todo_id, title):
    print(f"[CELERY] Iniciando envío de email para la tarea: {title} (ID: {todo_id})...")
    time.sleep(5)  # Simulamos retraso de red
    print(f"[CELERY] Email enviado con éxito para: {title}")
    return True

# Tarea 2: Resumen diario (Celery Beat)
@celery.task(name="generate_daily_summary")
def generate_daily_summary():
    print("[CELERY BEAT] Generando resumen diario...")
    db = database.SessionLocal()
    try:
        pending_todos = db.query(models.Todo).filter(models.Todo.completed == False).all()
        summary = {
            "date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "pending_count": len(pending_todos),
            "tasks": [{"id": t.id, "title": t.title} for t in pending_todos]
        }
        
        file_path = os.path.join(SHARED_DIR, "daily_summary.json")
        with open(file_path, "w") as f:
            json.dump(summary, f, indent=4)
            
        print(f"[CELERY BEAT] Resumen guardado en {file_path}")
    finally:
        db.close()
    return len(pending_todos)

# Tarea 3: Exportación a CSV
@celery.task(name="export_todos_to_csv")
def export_todos_to_csv():
    print("[CELERY] Iniciando exportación a CSV...")
    time.sleep(3) # Simular procesamiento pesado
    db = database.SessionLocal()
    try:
        all_todos = db.query(models.Todo).all()
        file_name = f"export_{int(time.time())}.csv"
        file_path = os.path.join(SHARED_DIR, file_name)
        
        with open(file_path, "w", newline='') as csvfile:
            fieldnames = ['id', 'title', 'description', 'completed']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for t in all_todos:
                writer.writerow({
                    'id': t.id,
                    'title': t.title,
                    'description': t.description,
                    'completed': t.completed
                })
        
        print(f"[CELERY] Exportación completada: {file_name}")
        return file_name
    finally:
        db.close()

# Configuración de tareas programadas (Beat)
celery.conf.beat_schedule = {
    'summary-every-minute': { # Lo ponemos cada minuto para que puedas verlo funcionar rápido
        'task': 'generate_daily_summary',
        'schedule': 60.0,
    },
}
celery.conf.timezone = 'UTC'
