from fastapi.middleware.cors import CORSMiddleware
from app.api import auth, projects, documents, requirements, export, analysis, graph, chat
from fastapi import FastAPI
from app.database import engine, Base
from app import models

Base.metadata.create_all(bind=engine)

app = FastAPI(title="ReqMind AI")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(projects.router)
# Muskaan
app.include_router(documents.router)
app.include_router(requirements.router)
app.include_router(export.router)
# Krrish
app.include_router(analysis.router)
app.include_router(graph.router)
app.include_router(chat.router)

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
