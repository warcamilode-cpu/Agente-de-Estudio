"""Backup automático de la base de datos SQLite.

Uso:
    from services.backup import hacer_backup
    hacer_backup()          # crea backups/estudio_YYYYMMDD_HHMMSS.db
    hacer_backup(retener=7) # mantiene solo los 7 más recientes
"""
import logging
import shutil
from datetime import datetime
from pathlib import Path

from database.connection import DB_PATH

log = logging.getLogger(__name__)

BACKUP_DIR = DB_PATH.parent / "backups"


def hacer_backup(retener: int = 7) -> Path | None:
    """Copia estudio.db a backups/estudio_YYYYMMDD_HHMMSS.db.

    Retorna la ruta del backup creado, o None si la DB no existe.
    Elimina los backups más viejos si hay más de `retener`.
    """
    if not DB_PATH.exists():
        log.warning("Backup: DB no encontrada en %s", DB_PATH)
        return None

    BACKUP_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = BACKUP_DIR / f"estudio_{ts}.db"

    shutil.copy2(DB_PATH, destino)
    log.info("Backup creado: %s (%.1f KB)", destino.name, destino.stat().st_size / 1024)

    _limpiar_viejos(retener)
    return destino


def _limpiar_viejos(retener: int) -> None:
    backups = sorted(BACKUP_DIR.glob("estudio_*.db"), key=lambda p: p.stat().st_mtime)
    for viejo in backups[:-retener]:
        viejo.unlink()
        log.info("Backup eliminado: %s", viejo.name)
