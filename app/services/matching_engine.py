import math
import re
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

_SEMANTIC_WEIGHT = 0.25
_SKILL_WEIGHT = 0.15
_EXPERIENCE_WEIGHT = 0.15
_CERTIFICATION_WEIGHT = 0.10
_SPECIALIZATION_WEIGHT = 0.15
_LOCATION_WEIGHT = 0.10
_ROLE_ALIGNMENT_WEIGHT = 0.10

_DOCTOR_KEYWORDS = {"physician", "doctor", "consultant", "specialist", "surgeon", "cardiologist",
    "radiologist", "anesthesiologist", "dermatologist", "neurologist", "oncologist",
    "ophthalmologist", "orthopedic", "pathologist", "pediatrician", "psychiatrist",
    "md", "mbbs", "dm", "mch", "internal medicine", "cardiology", "neurology",
    "pediatrics", "gynecology", "obstetrics", "dermatology", "psychiatry",
    "radiology", "anesthesiology", "pathology", "ophthalmology", "orthopedics",
    "oncology", "nephrology", "gastroenterology", "endocrinology", "rheumatology",
    "pulmonology", "urology", "resident", "fellow", "attending", "senior resident"}

_NURSE_KEYWORDS = {"nurse", "rn", "nursing", "cna", "lvn", "lpn", "bsc nursing", "gnm", "staff nurse"}

_SPEC_INDUSTRY_MAP = {
    "computer science": ["technology", "engineering", "software", "it", "information technology"],
    "computer": ["technology", "engineering", "software", "it"],
    "information technology": ["technology", "computer science"],
    "mechanical": ["engineering", "manufacturing", "automotive"],
    "electrical": ["engineering", "technology", "energy"],
    "electronics": ["engineering", "technology"],
    "civil": ["engineering", "construction"],
    "business administration": ["business", "management", "finance", "consulting"],
    "marketing": ["business", "advertising", "media"],
    "finance": ["business", "banking", "insurance", "accounting"],
    "accounting": ["business", "finance", "banking"],
    "cardiology": ["healthcare", "medical", "hospital", "clinical"],
    "internal medicine": ["healthcare", "medical", "hospital", "clinical"],
    "pediatrics": ["healthcare", "medical", "hospital"],
    "gynecology": ["healthcare", "medical", "hospital"],
    "obstetrics": ["healthcare", "medical", "hospital"],
    "neurology": ["healthcare", "medical", "hospital"],
    "dermatology": ["healthcare", "medical", "hospital"],
    "psychiatry": ["healthcare", "medical", "hospital"],
    "radiology": ["healthcare", "medical", "hospital"],
    "surgery": ["healthcare", "medical", "hospital"],
    "anesthesiology": ["healthcare", "medical", "hospital"],
    "pathology": ["healthcare", "medical", "hospital"],
    "ophthalmology": ["healthcare", "medical", "hospital"],
    "orthopedics": ["healthcare", "medical", "hospital"],
    "oncology": ["healthcare", "medical", "hospital"],
    "nephrology": ["healthcare", "medical", "hospital"],
    "gastroenterology": ["healthcare", "medical", "hospital"],
    "endocrinology": ["healthcare", "medical", "hospital"],
    "rheumatology": ["healthcare", "medical", "hospital"],
    "pulmonology": ["healthcare", "medical", "hospital"],
    "urology": ["healthcare", "medical", "hospital"],
    "general medicine": ["healthcare", "medical", "hospital"],
    "emergency medicine": ["healthcare", "medical", "hospital"],
    "family medicine": ["healthcare", "medical", "hospital"],
    "preventive medicine": ["healthcare", "medical", "hospital"],
}


def _normalize_cert_name(name: str) -> str:
    return re.sub(r'\s*\(.*?\)\s*', '', name).strip().lower()


def _role_alignment(resume_spec: str, resume_designation: str, resume_education: list, resume_skills: set, job_title: str) -> float:
    """Check if the candidate's role type aligns with the job role type.
    Returns 1.0 for good alignment, lower values for role-type mismatch."""
    if not job_title:
        return 1.0
    job_lower = job_title.lower()
    resume_text = " ".join(filter(None, [resume_spec or "", resume_designation or ""])).lower()
    edu_text = " ".join(e.degree or "" for e in resume_education if e).lower() if resume_education else ""
    combined_text = f"{resume_text} {edu_text}"

    is_doctor_track = any(kw in combined_text for kw in _DOCTOR_KEYWORDS)
    is_nurse_job = any(kw in job_lower for kw in _NURSE_KEYWORDS)

    if is_doctor_track and is_nurse_job:
        return 0.0
    return 1.0


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
    resume_city_lower = resume_city.lower().strip() if resume_city else ""
    resume_state_lower = resume_state.lower().strip() if resume_state else ""
    # Exact city match (either direction)
    if resume_city_lower and (resume_city_lower in jd_lower or jd_lower in resume_city_lower):
        return 1.0
    # State match in job location
    if resume_state_lower and resume_state_lower in jd_lower:
        return 0.75
    # Job location is a substring of resume city (e.g. "Java" in "Bengaluru, Java" — edge)
    if resume_city_lower and resume_city_lower.startswith(jd_lower):
        return 0.5
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
    sentences = []
    pi = resume.personal_info
    exp = resume.experience

    header_parts = []
    if pi and (pi.first_name or pi.last_name):
        header_parts.append(" ".join(filter(None, [pi.prefix, pi.first_name, pi.last_name])))
    if exp:
        if exp.current_designation:
            header_parts.append(exp.current_designation)
        if exp.current_hospital:
            header_parts.append(f"at {exp.current_hospital}")
    if header_parts:
        sentences.append(" ".join(header_parts) + ".")

    if exp:
        if exp.specialization:
            sentences.append(f"Specialization in {exp.specialization}.")
        if exp.experience_years is not None:
            sentences.append(f"{exp.experience_years} years of experience.")
        for wh in exp.work_history:
            wh_parts = []
            if wh.designation:
                wh_parts.append(wh.designation)
            if wh.employer:
                wh_parts.append(f"at {wh.employer}")
            if wh_parts:
                sentences.append("Worked as " + " ".join(wh_parts) + ".")

    if resume.education:
        edu_strs = []
        for edu in resume.education:
            parts = [p for p in [edu.degree, edu.specialization, edu.college] if p]
            if parts:
                edu_strs.append(" ".join(parts))
        if edu_strs:
            sentences.append("Education: " + ", ".join(edu_strs) + ".")

    if resume.skills:
        skills_list = [s.skill for s in resume.skills if s.skill]
        if skills_list:
            sentences.append("Skills: " + ", ".join(skills_list) + ".")

    if resume.certifications:
        certs_list = [c.certification for c in resume.certifications if c.certification]
        if certs_list:
            sentences.append("Certifications: " + ", ".join(certs_list) + ".")

    if resume.languages:
        langs_list = [l.language for l in resume.languages if l.language]
        if langs_list:
            sentences.append("Languages: " + ", ".join(langs_list) + ".")

    if pi:
        loc_parts = []
        if pi.city:
            loc_parts.append(pi.city)
        if pi.state:
            loc_parts.append(pi.state)
        if loc_parts:
            sentences.append("Location: " + ", ".join(loc_parts) + ".")

    return " ".join(sentences)


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
        resume_designation = exp.current_designation if exp else None
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
            # Normalize cert names to strip parenthetical descriptions (e.g. "BLS (Basic Life Support)" → "bls")
            jd_certs_set = set(_normalize_cert_name(c.name) for c in full_job.certifications if c.name)
            resume_certs_norm_set = set(_normalize_cert_name(c) for c in resume_certs_set)
            cert_score = _jaccard_similarity(jd_certs_set, resume_certs_norm_set)

            # Specialization match
            spec_score = 0.0
            if resume_spec:
                spec_lower = resume_spec.lower()
                # Check against industry
                if full_job.industry:
                    ind_lower = full_job.industry.lower()
                    if spec_lower in ind_lower or ind_lower in spec_lower:
                        spec_score = 1.0
                # Check against job title
                if spec_score < 1.0 and full_job.job_title:
                    title_lower = full_job.job_title.lower()
                    if spec_lower in title_lower or title_lower in spec_lower:
                        spec_score = 0.9
                # Check against job skills
                if spec_score < 0.9 and jd_skills_set:
                    if any(s in spec_lower for s in jd_skills_set) or any(spec_lower in s for s in jd_skills_set):
                        spec_score = 0.75
                # Known specialization ↔ industry mappings
                if spec_score < 0.75 and full_job.industry:
                    mapped_industries = _SPEC_INDUSTRY_MAP.get(spec_lower, [])
                    if full_job.industry.lower() in mapped_industries:
                        spec_score = 0.8

            # Location match
            loc_score = _location_match(resume_city, resume_state, full_job.location)

            # Role alignment (doctor vs nurse, etc.)
            role_score = _role_alignment(resume_spec, resume_designation, resume.education, resume_skills_set, full_job.job_title)

            # Weighted overall score
            overall = (
                _SEMANTIC_WEIGHT * semantic_sim
                + _SKILL_WEIGHT * skill_score
                + _EXPERIENCE_WEIGHT * exp_score
                + _CERTIFICATION_WEIGHT * cert_score
                + _SPECIALIZATION_WEIGHT * spec_score
                + _LOCATION_WEIGHT * loc_score
                + _ROLE_ALIGNMENT_WEIGHT * role_score
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
            matched_certs = len(jd_certs_set & resume_certs_norm_set)

            # Role alignment reason
            if role_score < 0.5:
                role_reason = f"Role type mismatch: candidate's medical qualifications do not align with '{full_job.job_title}' role"
            elif role_score < 1.0:
                role_reason = "Partial role alignment"
            else:
                role_reason = "Role type aligns with job requirements"

            reasons = MatchReasons(
                semantic=_generate_semantic_reason(semantic_sim),
                skill=_generate_skill_reason(skill_score, matched_skills, len(jd_skills_set), len(resume_skills_set)),
                experience=_generate_experience_reason(exp_score, resume_exp_years, full_job.experience_min, full_job.experience_max),
                certification=_generate_certification_reason(cert_score, matched_certs, len(jd_certs_set)),
                specialization=_generate_specialization_reason(spec_score, resume_spec, full_job.industry),
                location=_generate_location_reason(loc_score, resume_city, resume_state, full_job.location),
                role_alignment=role_reason,
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
                    role_alignment=round(role_score, 4),
                ),
                reasons=reasons,
            ))

        results.sort(key=lambda r: r.overall_score, reverse=True)
        top_results = results[:top_k]

        return top_results, candidate_name, len(top_results)
    finally:
        db.close()
