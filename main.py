import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from dotenv import load_dotenv

load_dotenv()

from services.logging_config import configurar_logging
configurar_logging(nivel=os.getenv("LOG_NIVEL", "INFO"))

from database.connection import init_db
from routers import ai_router, notas_router, flashcards_router, topics_router, dashboard_router
from routers import documentos_router, plan_router, cuaderno_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

app = FastAPI(title="Agente de Estudio", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": True, "detail": exc.detail, "code": exc.status_code},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": True, "detail": "Error interno del servidor", "code": 500},
    )


app.include_router(ai_router.router)
app.include_router(notas_router.router)
app.include_router(flashcards_router.router)
app.include_router(topics_router.router)
app.include_router(dashboard_router.router)
app.include_router(documentos_router.router)
app.include_router(plan_router.router)
app.include_router(cuaderno_router.router)

app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/health")
def health_check():
    from datetime import datetime
    from database.connection import db
    db_status = "ok"
    try:
        with db() as conn:
            conn.execute("SELECT 1").fetchone()
    except Exception:
        db_status = "error"
    llm_status = "ok" if os.getenv("ANTHROPIC_API_KEY") else "sin_configurar"
    return {
        "status": "ok" if db_status == "ok" else "degradado",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "db": db_status,
        "llm": llm_status,
    }


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
