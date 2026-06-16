from fastapi import APIRouter, HTTPException, status
from uuid import UUID

from app.schemas.matching import MatchJobsRequest, MatchJobsResponse
from app.services.matching_engine import match_jobs
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/ai", tags=["Job Matching"])


@router.post(
    "/match-jobs",
    response_model=MatchJobsResponse,
    status_code=status.HTTP_200_OK,
    summary="Match Resume to Job Descriptions",
    description=(
        "Find the best job descriptions for a given parsed resume using "
        "semantic similarity (pgvector), skill overlap, experience fit, "
        "certification match, specialization match, and location match."
    ),
)
async def match_jobs_endpoint(request: MatchJobsRequest):
    try:
        matches, candidate_name, total = match_jobs(request.resume_id, request.top_k)

        if candidate_name is None and total == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Resume with ID '{request.resume_id}' not found.",
            )

        return MatchJobsResponse(
            resume_id=request.resume_id,
            candidate_name=candidate_name,
            matches=matches,
            total_jobs=total,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.critical(f"Job matching failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Matching failed: {str(e)}",
        )
