import math
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import joinedload
from pgvector.sqlalchemy import Vector

from app.database import SessionLocal
from app.models import (
    ParsedResume, PersonalInfo, Education, Experience,
    WorkHistory, ResumeSkill, ResumeCertification,
    JobDescriptionRef, JobSkillRef, JobCertificationRef,
)
from app.services.embedding_service import embedding_service
from app.schemas.matching import (
    MatchJobsResponse, JobMatchResult, JobDetails,
    ScoreBreakdown, MatchReasons,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

_SEMANTIC_WEIGHT = 0.35
_SKILL_WEIGHT = 0.20
_EXPERIENCE_WEIGHT = 0.15
_CERTIFICATION_WEIGHT = 0.10
_SPECIALIZATION_WEIGHT = 0.10
_LOCATION_WEIGHT = 0.10


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    return max(0.0, min(1.0, dot))


def _jaccard_similarity(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    intersection = a & b
    union = a | b
    return len(intersection) / len(union)


def _experience_fit(resume_years: Optional[float], jd_min: Optional[float], jd_max: Optional[float]) -> float:
    if resume_years is None:
        return 0.0
    if jd_min is None and jd_max is None:
        return 0.5
    jd_min = jd_min or 0
    jd_max = jd_max or 30
    if jd_min <= resume_years <= jd_max:
        return 1.0
    midpoint = (jd_min + jd_max) / 2
    distance = abs(resume_years - midpoint)
    half_range = max((jd_max - jd_min) / 2, 1)
    return max(0.0, 1.0 - distance / half_range)


def _location_match(resume_city: Optional[str], resume_state: Optional[str], jd_location: Optional[str]) -> float:
    if not jd_location:
        return 0.5
    if not resume_city and not resume_state:
        return 0.0
    jd_lower = jd_location.lower()
    if resume_city and resume_city.lower() in jd_lower:
        return 1.0
    if resume_state and resume_state.lower() in jd_lower:
        return 0.75
    return 0.0


def _build_candidate_name(pi: Optional[PersonalInfo]) -> Optional[str]:
    if not pi:
        return None
    parts = []
    if pi.prefix:
        parts.append(pi.prefix)
    if pi.first_name:
        parts.append(pi.first_name)
    if pi.last_name:
        parts.append(pi.last_name)
    return " ".join(parts) if parts else None


def _build_resume_embedding_text(resume: ParsedResume) -> str:
    parts = []
    exp = resume.experience
    if exp:
        if exp.specialization:
            parts.append(exp.specialization)
        if exp.current_designation:
            parts.append(exp.current_designation)
        if exp.current_hospital:
            parts.append(exp.current_hospital)
        if exp.experience_years is not None:
            parts.append(f"{exp.experience_years} years")
        for wh in exp.work_history:
            if wh.designation:
                parts.append(wh.designation)
            if wh.employer:
                parts.append(wh.employer)
    for edu in resume.education:
        if edu.degree:
            parts.append(edu.degree)
        if edu.specialization:
            parts.append(edu.specialization)
        if edu.college:
            parts.append(edu.college)
    for skill in resume.skills:
        if skill.skill:
            parts.append(skill.skill)
    for cert in resume.certifications:
        if cert.certification:
            parts.append(cert.certification)
    for lang in resume.languages:
        if lang.language:
            parts.append(lang.language)
    pi = resume.personal_info
    if pi:
        if pi.city:
            parts.append(pi.city)
        if pi.state:
            parts.append(pi.state)
    return " ".join(parts)


def _generate_semantic_reason(score: float) -> str:
    if score >= 0.8:
        return "Excellent semantic alignment between resume and job description"
    if score >= 0.6:
        return "Good semantic alignment with job requirements"
    if score >= 0.4:
        return "Moderate semantic alignment"
    if score >= 0.2:
        return "Weak semantic alignment"
    return "Poor semantic alignment"


def _generate_skill_reason(score: float, matched: int, total_jd: int, total_resume: int) -> str:
    if total_jd == 0:
        return "No specific skills required by the job"
    if score >= 0.7:
        return f"Strong skill match: {matched} of {total_jd} required skills present"
    if score >= 0.4:
        return f"Partial skill overlap: {matched} of {total_jd} required skills matched"
    if matched > 0:
        return f"Limited skill match: only {matched} of {total_jd} required skills found"
    return "No overlapping skills with job requirements"


def _generate_experience_reason(score: float, resume_years: Optional[float], jd_min: Optional[float], jd_max: Optional[float]) -> str:
    if resume_years is None:
        return "Experience information not available"
    if jd_min is not None and jd_max is not None:
        if jd_min <= resume_years <= jd_max:
            return f"{resume_years} years of experience fits within the required {jd_min}-{jd_max} year range"
        return f"{resume_years} years of experience {'below' if resume_years < jd_min else 'above'} the preferred range"
    if jd_min is not None:
        return f"{resume_years} years of experience meets minimum requirement" if resume_years >= jd_min else f"{resume_years} years below {jd_min} year minimum"
    if jd_max is not None:
        return f"{resume_years} years of experience within maximum range" if resume_years <= jd_max else f"{resume_years} years exceeds {jd_max} year maximum"
    return f"{resume_years} years of relevant experience"


def _generate_certification_reason(score: float, matched: int, total_jd: int) -> str:
    if total_jd == 0:
        return "No certifications required by the job"
    if score >= 0.8:
        return "All required certifications are present"
    if score >= 0.5:
        return f"Most required certifications matched ({matched} of {total_jd})"
    if matched > 0:
        return f"Some certifications matched ({matched} of {total_jd})"
    return "No matching certifications found"


def _generate_specialization_reason(score: float, specialization: Optional[str], industry: Optional[str]) -> str:
    if not specialization:
        return "Specialization information not available"
    if score >= 0.75:
        return f"Specialization in '{specialization}' directly matches the role"
    if score >= 0.5:
        return f"Specialization '{specialization}' partially aligns with the job industry"
    return f"Specialization '{specialization}' does not align with the job requirements"


def _generate_location_reason(score: float, resume_city: Optional[str], resume_state: Optional[str], jd_location: Optional[str]) -> str:
    if not jd_location:
        return "No location preference specified by the job"
    if score >= 1.0:
        return f"Candidate location ({resume_city}) matches the job location"
    if score >= 0.75:
        return f"Candidate state ({resume_state}) matches the job location region"
    if resume_city:
        return f"Candidate in {resume_city} differs from job location ({jd_location})"
    return "Location information not available for comparison"


def _ensure_resume_embedding(resume: ParsedResume) -> Optional[List[float]]:
    if resume.embedding is not None:
        vec = resume.embedding
        if hasattr(vec, 'tolist'):
            return vec.tolist()
        return vec
    text = _build_resume_embedding_text(resume)
    vec = embedding_service.encode(text)
    if vec is not None:
        db = SessionLocal()
        try:
            stmt = update(ParsedResume).where(ParsedResume.id == resume.id).values(embedding=vec)
            db.execute(stmt)
            db.commit()
        except Exception as e:
            logger.warning(f"Failed to persist resume embedding: {e}")
        finally:
            db.close()
    return vec


def match_jobs(resume_id: UUID, top_k: int = 10) -> Tuple[List[JobMatchResult], Optional[str], int]:
    db = SessionLocal()
    try:
        resume = db.query(ParsedResume).options(
            joinedload(ParsedResume.personal_info),
            joinedload(ParsedResume.experience).joinedload(Experience.work_history),
            joinedload(ParsedResume.education),
            joinedload(ParsedResume.skills),
            joinedload(ParsedResume.certifications),
            joinedload(ParsedResume.languages),
        ).filter(ParsedResume.id == resume_id).first()

        if not resume:
            logger.warning(f"Resume {resume_id} not found")
            return [], None, 0

        candidate_name = _build_candidate_name(resume.personal_info)
        pi = resume.personal_info
        exp = resume.experience

        resume_skills_set = set(s.skill.lower() for s in resume.skills if s.skill)
        resume_certs_set = set(c.certification.lower() for c in resume.certifications if c.certification)
        resume_spec = exp.specialization if exp else None
        resume_exp_years = exp.experience_years if exp else None
        resume_city = pi.city if pi else None
        resume_state = pi.state if pi else None

        # Ensure resume has an embedding for pgvector search
        resume_vec = _ensure_resume_embedding(resume)

        # Determine which jobs to consider via pgvector similarity
        job_ids_with_sim = []
        if resume_vec is not None and embedding_service.is_available():
            try:
                cosine_distance = JobDescriptionRef.embedding.cosine_distance(resume_vec)
                stmt = (
                    select(JobDescriptionRef.id, cosine_distance.label("distance"))
                    .where(JobDescriptionRef.embedding.isnot(None))
                    .order_by(cosine_distance)
                    .limit(top_k * 5)
                )
                rows = db.execute(stmt).all()
                for row in rows:
                    job_id, dist = row
                    sim = 1.0 - float(dist)
                    job_ids_with_sim.append((job_id, max(0.0, sim)))
                logger.info(f"pgvector found {len(job_ids_with_sim)} candidate jobs for resume {resume_id}")
            except Exception as e:
                logger.warning(f"pgvector search failed, falling back: {e}")

        if not job_ids_with_sim:
            all_jobs = db.query(JobDescriptionRef.id).all()
            job_ids_with_sim = [(j.id, 0.0) for j in all_jobs]

        job_ids = [j_id for j_id, _ in job_ids_with_sim]
        sim_map = dict(job_ids_with_sim)

        # Load full job details with relationships
        jobs = db.query(JobDescriptionRef).options(
            joinedload(JobDescriptionRef.skills),
            joinedload(JobDescriptionRef.certifications),
            joinedload(JobDescriptionRef.education_requirements),
        ).filter(JobDescriptionRef.id.in_(job_ids)).all()

        job_map = {j.id: j for j in jobs}

        results = []
        for job_id in job_ids:
            full_job = job_map.get(job_id)
            if not full_job:
                continue

            semantic_sim = sim_map.get(job_id, 0.0)

            # Skill overlap (Jaccard between resume skills and job skills)
            jd_skills_set = set(s.skill.lower() for s in full_job.skills if s.skill)
            skill_score = _jaccard_similarity(jd_skills_set, resume_skills_set)

            # Experience fit
            exp_score = _experience_fit(resume_exp_years, full_job.experience_min, full_job.experience_max)

            # Certification match (Jaccard between resume certs and job certs)
            jd_certs_set = set(c.name.lower() for c in full_job.certifications if c.name)
            cert_score = _jaccard_similarity(jd_certs_set, resume_certs_set)

            # Specialization match
            spec_score = 0.0
            if resume_spec and full_job.industry:
                spec_lower = resume_spec.lower()
                ind_lower = full_job.industry.lower()
                if spec_lower in ind_lower or ind_lower in spec_lower:
                    spec_score = 1.0
                elif jd_skills_set:
                    if any(s in spec_lower for s in jd_skills_set) or any(spec_lower in s for s in jd_skills_set):
                        spec_score = 0.75

            # Location match
            loc_score = _location_match(resume_city, resume_state, full_job.location)

            # Weighted overall score
            overall = (
                _SEMANTIC_WEIGHT * semantic_sim
                + _SKILL_WEIGHT * skill_score
                + _EXPERIENCE_WEIGHT * exp_score
                + _CERTIFICATION_WEIGHT * cert_score
                + _SPECIALIZATION_WEIGHT * spec_score
                + _LOCATION_WEIGHT * loc_score
            )

            # Salary range string
            salary_range = None
            if full_job.salary_min is not None or full_job.salary_max is not None:
                currency = full_job.salary_currency or "USD"
                if full_job.salary_min is not None and full_job.salary_max is not None:
                    salary_range = f"{currency} {full_job.salary_min:,.0f} - {full_job.salary_max:,.0f}"
                elif full_job.salary_min is not None:
                    salary_range = f"{currency} {full_job.salary_min:,.0f}+"
                elif full_job.salary_max is not None:
                    salary_range = f"Up to {currency} {full_job.salary_max:,.0f}"

            # Count matched skills/certs for reasons
            matched_skills = len(jd_skills_set & resume_skills_set)
            matched_certs = len(jd_certs_set & resume_certs_set)

            reasons = MatchReasons(
                semantic=_generate_semantic_reason(semantic_sim),
                skill=_generate_skill_reason(skill_score, matched_skills, len(jd_skills_set), len(resume_skills_set)),
                experience=_generate_experience_reason(exp_score, resume_exp_years, full_job.experience_min, full_job.experience_max),
                certification=_generate_certification_reason(cert_score, matched_certs, len(jd_certs_set)),
                specialization=_generate_specialization_reason(spec_score, resume_spec, full_job.industry),
                location=_generate_location_reason(loc_score, resume_city, resume_state, full_job.location),
            )

            results.append(JobMatchResult(
                job=JobDetails(
                    job_id=full_job.id,
                    job_title=full_job.job_title,
                    company_name=full_job.company_name,
                    location=full_job.location,
                    industry=full_job.industry,
                    employment_type=full_job.employment_type,
                    summary=full_job.summary,
                    salary_range=salary_range,
                ),
                overall_score=round(overall, 4),
                breakdown=ScoreBreakdown(
                    semantic_similarity=round(semantic_sim, 4),
                    skill_overlap=round(skill_score, 4),
                    experience_fit=round(exp_score, 4),
                    certification_match=round(cert_score, 4),
                    specialization_match=round(spec_score, 4),
                    location_match=round(loc_score, 4),
                ),
                reasons=reasons,
            ))

        results.sort(key=lambda r: r.overall_score, reverse=True)
        top_results = results[:top_k]

        return top_results, candidate_name, len(results)
    finally:
        db.close()
