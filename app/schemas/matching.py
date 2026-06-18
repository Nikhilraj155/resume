from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID


class MatchJobsRequest(BaseModel):
    resume_id: UUID = Field(..., description="UUID of the parsed resume to match against")
    top_k: int = Field(default=10, ge=1, le=50, description="Number of top matching jobs to return")


class ScoreBreakdown(BaseModel):
    semantic_similarity: float = 0.0
    skill_overlap: float = 0.0
    experience_fit: float = 0.0
    certification_match: float = 0.0
    specialization_match: float = 0.0
    location_match: float = 0.0
    role_alignment: float = 1.0


class MatchReasons(BaseModel):
    semantic: str = ""
    skill: str = ""
    experience: str = ""
    certification: str = ""
    specialization: str = ""
    location: str = ""
    role_alignment: str = ""


class JobDetails(BaseModel):
    job_id: UUID
    job_title: Optional[str] = None
    company_name: Optional[str] = None
    location: Optional[str] = None
    industry: Optional[str] = None
    employment_type: Optional[str] = None
    summary: Optional[str] = None
    salary_range: Optional[str] = None


class JobMatchResult(BaseModel):
    job: JobDetails
    overall_score: float
    breakdown: ScoreBreakdown
    reasons: MatchReasons


class MatchJobsResponse(BaseModel):
    resume_id: UUID
    candidate_name: Optional[str] = None
    matches: List[JobMatchResult] = Field(default_factory=list)
    total_jobs: int = 0
