from fastapi import FastAPI
from app.database import engine

app = FastAPI()

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
