from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from api.backup import router as backup_router
from api.restore import router as restore_router
from api.servers import router as servers_router
from api.auth import router as auth_router
from api.download import router as download_router
from api.views import router as views_router
import db

app = FastAPI(title="Backup Monitor")

@app.on_event("startup")
def startup():
    db.init_db()

app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(views_router)
app.include_router(backup_router)
app.include_router(restore_router)
app.include_router(servers_router)
app.include_router(auth_router)
app.include_router(download_router)
