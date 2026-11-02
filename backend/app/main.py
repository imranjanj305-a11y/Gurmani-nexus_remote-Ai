from fastapi import FastAPI

from .database import Base, engine
from .routers import auth, devices

app = FastAPI(title="Germani AI Nexus API", version="0.1.0")


@app.on_event("startup")
def create_tables() -> None:
    # For production use the SQL migration in database/migrations.
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(devices.router)
