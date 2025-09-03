import sqlite3
from sqlmodel import SQLModel
from app.models import Alarm, Osoblje, Comm
import os

def check_table_structure(db_path, model_class):
    table_name = model_class.__tablename__
    expected_fields = set(model_class.model_fields.keys())
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(f"PRAGMA table_info({table_name})")
        existing_fields = {row[1] for row in cur.fetchall()}
    missing = expected_fields - existing_fields
    extra = existing_fields - expected_fields
    return missing, extra

def check_all_tables(db_path):
    problems = []
    for model in [Alarm, Osoblje, Comm]:
        missing, extra = check_table_structure(db_path, model)
        if missing or extra:
            problems.append((model.__tablename__, missing, extra))
    return problems

def drop_and_create_table(db_path, model_class):
    table_name = model_class.__tablename__
    with sqlite3.connect(db_path) as conn:
        conn.execute(f"DROP TABLE IF EXISTS {table_name}")
    SQLModel.metadata.tables[table_name].create(bind=None, checkfirst=False)
