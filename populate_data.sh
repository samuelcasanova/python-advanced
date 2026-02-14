#!/bin/bash

BASE_URL="http://localhost:8080"

echo "Esperando a que la API esté disponible..."
until curl -s "$BASE_URL/health" | grep -q 'ok'; do
  sleep 1
done

echo -e "\nInsertando datos de ejemplo...\n"

# Tarea 1
curl -X POST "$BASE_URL/todos" \
     -H "Content-Type: application/json" \
     -d '{"title": "Configurar infraestructura", "description": "FastAPI, Docker Compose y Nginx", "completed": true}'
echo -e "\n"

# Tarea 2
curl -X POST "$BASE_URL/todos" \
     -H "Content-Type: application/json" \
     -d '{"title": "Implementar Celery", "description": "Configurar workers para tareas en segundo plano", "completed": false}'
echo -e "\n"

# Tarea 3
curl -X POST "$BASE_URL/todos" \
     -H "Content-Type: application/json" \
     -d '{"title": "Añadir base de datos", "description": "Migrar del almacenamiento en memoria a PostgreSQL", "completed": false}'
echo -e "\n"

echo "Verificando lista de tareas:"
curl -X GET "$BASE_URL/todos"
echo -e "\n"

echo "¡Hecho!"
