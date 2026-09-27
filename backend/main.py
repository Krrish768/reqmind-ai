from app.api import auth, projects
from fastapi import FastAPI
from app.database import engine, Base
from app import models

Base.metadata.create_all(bind=engine)

app = FastAPI()

app.include_router(auth.router)
app.include_router(projects.router)

@app.get("/")
def read_root():
    return {"message": "ReqMind AI backend is running!"}

@app.get("/db-check")
def db_check():
    try:
        connection = engine.connect()
        connection.close()
        return {"status": "Database connected successfully!"}
    except Exception as e:
        return {"status": "Database connection failed", "error": str(e)}
