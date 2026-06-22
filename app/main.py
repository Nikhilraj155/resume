import os
import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.exceptions import RequestValidationError
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

load_dotenv()

from app.routes import parser, matching
from app.utils.logger import get_logger
from app.database import init_db
from app.config import settings

logger = get_logger(__name__)

app = FastAPI(
    title="Doctor Resume Parser AI Service",
    description="Microservice to parse and extract structured fields from doctor resumes using open-source NLP and regular expressions.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(CURRENT_DIR, "templates"))

app.include_router(parser.router)
app.include_router(matching.router)


@app.on_event("startup")
async def on_startup():
    logger.info("Initializing database tables...")
    try:
        init_db()
        logger.info("Database tables created successfully.")
    except Exception as e:
        logger.warning(f"Database initialization failed (non-fatal): {e}")


@app.get("/", tags=["Health"])
async def root():
    return {"message": "Doctor Resume Parser AI Service is running", "docs": "/docs"}


@app.get("/health", status_code=status.HTTP_200_OK, tags=["Health"])
async def health_check():
    spacy_loaded = False
    try:
        import spacy
        spacy_loaded = bool(spacy.util.get_installed_models())
    except Exception:
        pass

    return {
        "status": "healthy",
        "spacy_model_installed": spacy_loaded,
        "version": "1.0.0",
        "database_configured": bool(settings.database_url)
    }


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Validation failed for request {request.url.path}: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation Error",
            "message": "The request payload failed schema validation.",
            "details": exc.errors()
        }
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.critical(f"Unhandled exception on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred on the server.",
        }
    )


if __name__ == "__main__":
    port = settings.port
    logger.info(f"Starting Doctor Resume Parser Microservice on port {port}...")
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
