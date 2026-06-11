import os
import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.exceptions import RequestValidationError
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

# Load env variables at startup
load_dotenv()

from app.routes import parser
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Initialize FastAPI App
app = FastAPI(
    title="Doctor Resume Parser AI Service",
    description="Microservice to parse and extract structured fields from doctor resumes using open-source NLP and regular expressions.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup Templates Directory
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(CURRENT_DIR, "templates"))

# Include Routers
app.include_router(parser.router)

# Root Endpoint: Serves HTML Testing Frontend
@app.get("/", response_class=HTMLResponse, tags=["UI"])
async def render_ui(request: Request):
    """
    Serves the premium interactive 4-step wizard frontend.
    """
    logger.info("Serving frontend dashboard index.html to client")
    return templates.TemplateResponse("index.html", {"request": request})

# Health Check Endpoint
@app.get("/health", status_code=status.HTTP_200_OK, tags=["Health"])
async def health_check():
    """
    Service health check endpoint.
    """
    # Check if spacy model can be loaded
    spacy_loaded = False
    try:
        import spacy
        spacy_loaded = bool(spacy.util.get_installed_models())
    except Exception:
        pass
        
    return {
        "status": "healthy",
        "spacy_model_installed": spacy_loaded,
        "version": "1.0.0"
    }

# Global Exception Handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Custom handler for validation errors.
    """
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
    """
    Custom handler for unhandled backend exceptions.
    """
    logger.critical(f"Unhandled exception on {request.method} {request.url.path}: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred on the server.",
            "details": str(exc) if os.getenv("LOG_LEVEL") == "DEBUG" else None
        }
    )

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    logger.info(f"Starting Doctor Resume Parser Microservice on port {port}...")
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
