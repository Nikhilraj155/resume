import os
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from app.schemas.resume import ResumeParserResponseSchema
from app.services.pdf_extractor import PDFExtractorService
from app.services.resume_parser import ResumeParserService
from app.services.resume_storage import save_resume
from app.utils.logger import get_logger
from app.database import SessionLocal
from app.models import ParsedResume
from datetime import datetime

logger = get_logger(__name__)

router = APIRouter(prefix="/ai", tags=["Resume Parser"])
resume_parser_service = ResumeParserService()

# Directory configuration for uploaded files
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads")

@router.post(
    "/parse-resume",
    response_model=ResumeParserResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Parse a Doctor Resume",
    description="Upload a doctor's resume in PDF and DOCX format to extract structured, normalized profile information."
)
async def parse_resume(file: UploadFile = File(...)):
    # 1. Validate file extension/type (PDF and DOCX supported)
    filename = file.filename or ""
    file_ext = os.path.splitext(filename)[1].lower()
    allowed_exts = {".pdf", ".docx"}
    allowed_types = {"application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
    
    if file_ext not in allowed_exts and file.content_type not in allowed_types:
        logger.error(f"Rejected file with invalid format: filename='{filename}', content_type='{file.content_type}'")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file format. Only PDF and DOCX files are allowed."
        )

    saved_filepath = None
    try:
        # 2. Save the uploaded file
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        saved_filepath = os.path.join(UPLOAD_DIR, unique_filename)
        
        logger.info(f"Saving uploaded file '{filename}' as '{unique_filename}'")
        await file.seek(0)
        contents = await file.read()
        
        if len(contents) == 0:
            raise ValueError("The uploaded PDF file is empty.")
            
        with open(saved_filepath, "wb") as f:
            f.write(contents)
        
        # 3. Call resume parser to parse the file
        structured_data = resume_parser_service.parse_resume(saved_filepath)
        
        # 4. Create ParsedResume record synchronously to get the ID
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
        
        # 5. Save related data synchronously (ensures data + embedding are available immediately)
        save_resume(filename, structured_data, resume_id)
        
        return structured_data

    except ValueError as ve:
        logger.error(f"Validation or parsing error: {str(ve)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        logger.critical(f"System failure while parsing resume: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while processing the resume: {str(e)}"
        )
    finally:
        # Optional: clean up the saved file to save space
        if saved_filepath and os.path.exists(saved_filepath):
            try:
                os.remove(saved_filepath)
                logger.info(f"Cleaned up temporary file: {saved_filepath}")
            except Exception as e:
                logger.warning(f"Failed to delete temporary file {saved_filepath}: {str(e)}")
