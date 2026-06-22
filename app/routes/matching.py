import asyncio
from fastapi import APIRouter, HTTPException, status
from uuid import UUID

from app.schemas.matching import MatchJobsRequest, MatchJobsResponse, JobMatchResult
from app.tasks import match_jobs_task
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
        async_result = match_jobs_task.delay(str(request.resume_id), request.top_k)
        result = await asyncio.to_thread(async_result.get, timeout=120)

        if result["candidate_name"] is None and result["total"] == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Resume with ID '{request.resume_id}' not found.",
            )

        return MatchJobsResponse(
            resume_id=UUID(result["resume_id"]),
            candidate_name=result["candidate_name"],
            matches=[JobMatchResult(**m) for m in result["matches"]],
            total_jobs=result["total"],
        )
    except HTTPException:
        raise
    except asyncio.TimeoutError:
        logger.error(f"Job matching timed out for resume {request.resume_id}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Job matching timed out. Please try again.",
        )
    except Exception as e:
        logger.critical(f"Job matching failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred during job matching.",
        )
