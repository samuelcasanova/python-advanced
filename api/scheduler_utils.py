from sqlalchemy_celery_beat.models import PeriodicTask, IntervalSchedule, PeriodicTaskChanged
from database import engine, SessionLocal


def setup_periodic_tasks():
    # En sqlalchemy-celery-beat, las tablas están en metadata
    metadata = PeriodicTask.__table__.metadata

    # SQLite no soporta esquemas, así que nos aseguramos de que no tengan 'celery_schema'
    for table in metadata.tables.values():
        table.schema = None

    metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # 1. Crear el intervalo de 60 segundos si no existe
        schedule = db.query(IntervalSchedule).filter_by(every=1, period='days').first()
        if not schedule:
            schedule = IntervalSchedule(every=1, period='days')
            db.add(schedule)
            db.commit()
            db.refresh(schedule)

        # 2. Crear la tarea si no existe
        task_name = "Generar resumen diario (cada día)"
        task = db.query(PeriodicTask).filter_by(name=task_name).first()
        if not task:
            # En esta versión configurada:
            # - Usamos 'discriminator' = 'intervalschedule'
            # - Usamos 'schedule_id' para enlazar con IntervalSchedule
            task = PeriodicTask(
                name=task_name,
                task='generate_daily_summary',
                discriminator='intervalschedule',
                schedule_id=schedule.id,
                args='[]',
                kwargs='{}',
                enabled=True
            )
            db.add(task)
            db.commit()

            # Notificar que el schedule ha cambiado usando el método que acepta la sesión
            PeriodicTaskChanged.update_from_session(db)
            db.commit()

    finally:
        db.close()
