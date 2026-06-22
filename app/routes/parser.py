import os
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from app.schemas.resume import ResumeParserResponseSchema
from app.services.resume_parser import ResumeParserService
from app.tasks import store_resume_data_task
from app.utils.logger import get_logger
from app.database import SessionLocal
from app.models import ParsedResume
from app.config import settings
from datetime import datetime

logger = get_logger(__name__)

router = APIRouter(prefix="/ai", tags=["Resume Parser"])
resume_parser_service = ResumeParserService()

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads")

MAX_UPLOAD_BYTES = settings.max_upload_size_mb * 1024 * 1024

ALLOWED_EXTS = {".pdf", ".docx"}
ALLOWED_TYPES = {"application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}


@router.post(
    "/parse-resume",
    response_model=ResumeParserResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Parse a Doctor Resume",
    description="Upload a doctor's resume in PDF and DOCX format to extract structured, normalized profile information."
)
async def parse_resume(file: UploadFile = File(...)):
    filename = file.filename or ""
    file_ext = os.path.splitext(filename)[1].lower()

    if file_ext not in ALLOWED_EXTS and file.content_type not in ALLOWED_TYPES:
        logger.error(f"Rejected file with invalid format: filename='{filename}', content_type='{file.content_type}'")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file format. Only PDF and DOCX files are allowed."
        )

    saved_filepath = None
    try:
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        saved_filepath = os.path.join(UPLOAD_DIR, unique_filename)

        logger.info(f"Saving uploaded file '{filename}' as '{unique_filename}'")
        await file.seek(0)

        size = 0
        with open(saved_filepath, "wb") as f:
            while True:
                chunk = await file.read(65536)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise ValueError(f"File exceeds maximum size of {settings.max_upload_size_mb}MB")
                f.write(chunk)

        if size == 0:
            raise ValueError("The uploaded file is empty.")

        structured_data = await run_in_threadpool(resume_parser_service.parse_resume, saved_filepath)

        resume_id = uuid.uuid4()
        db = SessionLocal()
        try:
            resume = ParsedResume(
                id=resume_id,
                filename=filename,
                created_at=datetime.utcnow().isoformat()
            )
            db.add(resume)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

        structured_data.id = str(resume_id)

        store_resume_data_task.delay(filename, structured_data.model_dump(), str(resume_id))

        return structured_data

    except ValueError as ve:
        logger.error(f"Validation or parsing error: {ve}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.critical(f"System failure while parsing resume: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while processing the resume."
        )
    finally:
        if saved_filepath and os.path.exists(saved_filepath):
            try:
                os.remove(saved_filepath)
            except Exception as e:
                logger.warning(f"Failed to delete temporary file {saved_filepath}: {e}")
