from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.backup import router as backup_router
from api.restore import router as restore_router
from api.servers import router as servers_router
from api.auth import router as auth_router
import db

app = FastAPI(title="Backup Monitor")

@app.on_event("startup")
def startup():
    db.init_db()

app.include_router(backup_router)
app.include_router(restore_router)
app.include_router(servers_router)
app.include_router(auth_router)
