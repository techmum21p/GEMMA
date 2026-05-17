import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import email, export, patients, shifts, triage
from app.core.config import settings
from app.db.database import init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger(__name__)

_BANNER = """
╔══════════════════════════════════════════════════════════════╗
║       GEMMA — Guided Emergency & Medical Management          ║
║         Barangay Platero Health Center, City of Biñan        ║
║         Kaggle × Google DeepMind Gemma 4 Good 2026          ║
╚══════════════════════════════════════════════════════════════╝
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(_BANNER)
    logger.info("━━━ GEMMA startup sequence initiated ━━━")
    logger.info(f"  Ollama base URL : {settings.OLLAMA_BASE_URL}")
    logger.info(f"  Primary model   : {settings.GEMMA_MODEL}")
    logger.info(f"  Image model     : {settings.MEDGEMMA_MODEL}")
    logger.info(f"  Database        : {settings.DATABASE_URL}")
    logger.info("  Initializing SQLite database…")
    await init_db()
    logger.info("  ✓ Database ready")
    logger.info("━━━ GEMMA is ready — BHWs can now start triaging patients ━━━")
    yield
    logger.info("━━━ GEMMA shutting down ━━━")


app = FastAPI(
    title="GEMMA — Guided Emergency & Medical Management Assistant",
    description="AI triage decision-support PWA for Barangay Health Workers",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(triage.router)
app.include_router(patients.router)
app.include_router(shifts.router)
app.include_router(export.router)
app.include_router(email.router)

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

static_path = FRONTEND_DIR / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    html_file = FRONTEND_DIR / "templates" / "index.html"
    if html_file.exists():
        return HTMLResponse(content=html_file.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>GEMMA — Starting up...</h1>")


@app.get("/manifest.json")
async def serve_manifest():
    from fastapi.responses import FileResponse
    return FileResponse(str(FRONTEND_DIR / "static" / "manifest.json"), media_type="application/manifest+json")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "GEMMA"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.APP_HOST, port=settings.APP_PORT, reload=True)
