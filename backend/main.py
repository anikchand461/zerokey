# backend/main.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from .database import engine, Base, run_simple_migrations
from . import vault, proxy, usage, auth   # ← add auth
from fastapi.responses import RedirectResponse

app = FastAPI(title="Zerokey API Vault MVP")

Base.metadata.create_all(bind=engine)
run_simple_migrations()

app.include_router(vault.router)
app.include_router(proxy.router)
app.include_router(usage.router)
app.include_router(auth.router)  # ← add this

app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")
