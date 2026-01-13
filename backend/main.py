from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from .database import engine, Base
from . import vault, proxy, usage

app = FastAPI(title="API Vault MVP")

# Create tables (dev only – use Alembic later)
Base.metadata.create_all(bind=engine)

app.include_router(vault.router)
app.include_router(proxy.router)
app.include_router(usage.router)

# Serve frontend
app.mount("/static", StaticFiles(directory="../frontend"), name="static")

@app.get("/")
def root():
    return {"message": "API Vault MVP – visit /static/index.html"}
