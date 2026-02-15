from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List
import os

import models
import schemas
import database
import celery_app

# Crear tablas
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="To-Do List API with Celery")


def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/todos", response_model=List[schemas.Todo])
def get_todos(db: Session = Depends(get_db)):
    return db.query(models.Todo).all()


@app.post("/todos", response_model=schemas.Todo, status_code=201)
def create_todo(todo: schemas.TodoCreate, db: Session = Depends(get_db)):
    db_todo = models.Todo(**todo.model_dump())
    db.add(db_todo)
    db.commit()
    db.refresh(db_todo)

    # Disparar tarea de Celery (Notificación Fake)
    celery_app.send_notification_email.delay(db_todo.id, db_todo.title)

    return db_todo


@app.get("/todos/{todo_id}", response_model=schemas.Todo)
def get_todo(todo_id: int, db: Session = Depends(get_db)):
    db_todo = db.query(models.Todo).filter(models.Todo.id == todo_id).first()
    if db_todo is None:
        raise HTTPException(status_code=404, detail="Todo not found")
    return db_todo


@app.put("/todos/{todo_id}", response_model=schemas.Todo)
def update_todo(todo_id: int, updated_todo: schemas.TodoCreate, db: Session = Depends(get_db)):
    db_todo = db.query(models.Todo).filter(models.Todo.id == todo_id).first()
    if db_todo is None:
        raise HTTPException(status_code=404, detail="Todo not found")
    for key, value in updated_todo.model_dump().items():
        setattr(db_todo, key, value)

    db.commit()
    db.refresh(db_todo)
    return db_todo


@app.delete("/todos/{todo_id}", status_code=204)
def delete_todo(todo_id: int, db: Session = Depends(get_db)):
    db_todo = db.query(models.Todo).filter(models.Todo.id == todo_id).first()
    if db_todo is None:
        raise HTTPException(status_code=404, detail="Todo not found")
    db.delete(db_todo)
    db.commit()
    return

# --- Endpoints de Celery Export ---


@app.post("/export", status_code=202)
def trigger_export():
    task = celery_app.export_todos_to_csv.delay()
    return {"task_id": task.id, "status": "Pending"}


@app.get("/export/{task_id}")
def get_export_status(task_id: str):
    task_result = celery_app.celery.AsyncResult(task_id)

    response = {
        "task_id": task_id,
        "status": task_result.status,
        "result": None
    }

    if task_result.status == "SUCCESS":
        response["result"] = f"/export/{task_id}/download"

    return response


@app.get("/export/{task_id}/download")
def download_export(task_id: str):
    task_result = celery_app.celery.AsyncResult(task_id)
    if task_result.status != "SUCCESS":
        raise HTTPException(status_code=400, detail="Task not finished or failed")

    file_name = task_result.result
    file_path = os.path.join(celery_app.SHARED_DIR, file_name)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(path=file_path, filename=file_name, media_type='text/csv')


@app.get("/health")
def health_check():
    return {"status": "ok"}
