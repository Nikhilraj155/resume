import uuid
from typing import List

from app.celery_app import celery_app
from app.schemas.resume import ResumeParserResponseSchema
from app.schemas.matching import JobMatchResult
from app.services.resume_storage import save_resume, store_embedding
from app.services.matching_engine import match_jobs
from app.utils.logger import get_logger

logger = get_logger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60, acks_late=True)
def store_resume_data_task(
    self,
    filename: str,
    structured_data_dict: dict,
    resume_id_str: str,
):
    resume_id = uuid.UUID(resume_id_str)
    structured_data = ResumeParserResponseSchema.model_validate(structured_data_dict)
    structured_data.id = resume_id_str

    try:
        save_resume(filename, structured_data, resume_id)
        logger.info(f"Resume data saved for {resume_id}")
    except Exception as e:
        logger.error(f"Failed to save resume data for {resume_id}: {e}", exc_info=True)
        raise self.retry(exc=e)

    try:
        store_embedding(resume_id, structured_data)
        logger.info(f"Embedding stored for {resume_id}")
    except Exception as e:
        logger.warning(f"Embedding storage failed for {resume_id} (non-fatal): {e}")

    return resume_id_str


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30, acks_late=True)
def match_jobs_task(
    self,
    resume_id_str: str,
    top_k: int = 10,
) -> dict:
    resume_id = uuid.UUID(resume_id_str)

    try:
        matches, candidate_name, total = match_jobs(resume_id, top_k)
    except Exception as e:
        logger.error(f"Job matching failed for {resume_id}: {e}", exc_info=True)
        raise self.retry(exc=e)

    return {
        "matches": [m.model_dump() for m in matches],
        "candidate_name": candidate_name,
        "total": total,
        "resume_id": resume_id_str,
    }
