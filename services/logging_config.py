"""Configuración centralizada de logging para Atalaya Pléyades."""
import logging
import logging.handlers
from pathlib import Path

LOG_DIR = Path(__file__).parent.parent / "logs"
_configurado = False


def configurar_logging(nivel: str = "INFO") -> None:
    global _configurado
    if _configurado:
        return
    _configurado = True

    LOG_DIR.mkdir(exist_ok=True)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    consola = logging.StreamHandler()
    consola.setFormatter(fmt)

    archivo = logging.handlers.RotatingFileHandler(
        LOG_DIR / "app.log",
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=5,
        encoding="utf-8",
    )
    archivo.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(getattr(logging, nivel.upper(), logging.INFO))
    root.addHandler(consola)
    root.addHandler(archivo)

    logging.getLogger("uvicorn.access").propagate = False
