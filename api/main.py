from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List
import os
from sqlalchemy_celery_beat.models import PeriodicTask, IntervalSchedule, PeriodicTaskChanged

import models
import schemas
import database
import celery_app
import scheduler_utils

# Crear tablas
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="To-Do List API with Celery")


@app.on_event("startup")
def startup_event():
    scheduler_utils.setup_periodic_tasks()
    print("Periodic tasks initialized.")


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


# --- Endpoints de Gestión del Scheduler ---

@app.get("/scheduler/tasks", response_model=List[schemas.PeriodicTaskSchema])
def list_scheduled_tasks(db: Session = Depends(get_db)):
    tasks = db.query(PeriodicTask).all()
    result = []
    for t in tasks:
        # En esta versión, el intervalo está en model_intervalschedule
        interval = 0
        if t.model_intervalschedule:
            interval = t.model_intervalschedule.every

        result.append(schemas.PeriodicTaskSchema(
            name=t.name,
            task=t.task,
            interval_seconds=interval,
            enabled=t.enabled
        ))
    return result


@app.post("/scheduler/tasks", response_model=schemas.PeriodicTaskSchema)
def create_scheduled_task(task_data: schemas.PeriodicTaskSchema, db: Session = Depends(get_db)):
    try:
        # 1. Asegurar o crear el intervalo
        schedule = db.query(IntervalSchedule).filter_by(
            every=task_data.interval_seconds,
            period='seconds'
        ).first()

        if not schedule:
            schedule = IntervalSchedule(every=task_data.interval_seconds, period='seconds')
            db.add(schedule)
            db.flush()

        # 2. Crear o actualizar la tarea
        periodic_task = db.query(PeriodicTask).filter_by(name=task_data.name).first()
        if periodic_task:
            periodic_task.task = task_data.task
            periodic_task.discriminator = 'intervalschedule'
            periodic_task.schedule_id = schedule.id
            periodic_task.enabled = task_data.enabled
        else:
            periodic_task = PeriodicTask(
                name=task_data.name,
                task=task_data.task,
                discriminator='intervalschedule',
                schedule_id=schedule.id,
                enabled=task_data.enabled,
                args='[]',
                kwargs='{}'
            )
            db.add(periodic_task)

        db.flush()

        # 3. Notificar al scheduler que hubo un cambio
        PeriodicTaskChanged.update_from_session(db, commit=False)
        db.commit()

        return schemas.PeriodicTaskSchema(
            name=periodic_task.name,
            task=periodic_task.task,
            interval_seconds=task_data.interval_seconds,
            enabled=periodic_task.enabled
        )
    except Exception as e:
        db.rollback()
        print(f"Error creating/updating task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/scheduler/tasks/{task_name}")
def delete_scheduled_task(task_name: str, db: Session = Depends(get_db)):
    try:
        periodic_task = db.query(PeriodicTask).filter_by(name=task_name).first()
        if not periodic_task:
            raise HTTPException(status_code=404, detail="Task not found")

        db.delete(periodic_task)

        # Notificar cambio y hacer commit
        PeriodicTaskChanged.update_from_session(db, commit=False)
        db.commit()

        return {"message": f"Task {task_name} deleted"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
