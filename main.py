import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv

load_dotenv()

from database.connection import init_db
from routers import ai_router, notas_router, flashcards_router, topics_router, dashboard_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Agente de Estudio", lifespan=lifespan)

app.include_router(ai_router.router)
app.include_router(notas_router.router)
app.include_router(flashcards_router.router)
app.include_router(topics_router.router)
app.include_router(dashboard_router.router)

app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/")
def raiz():
    return FileResponse("frontend/index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=os.getenv("APP_HOST", "0.0.0.0"),
        port=int(os.getenv("APP_PORT", 8000)),
        reload=True,
    )
