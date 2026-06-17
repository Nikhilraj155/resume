import uuid
from app.database import SessionLocal
from app.models import (
    ParsedResume, PersonalInfo, Education, Experience,
    WorkHistory, ResumeSkill, ResumeCertification, ResumeLanguage
)
from app.schemas.resume import ResumeParserResponseSchema
from app.utils.logger import get_logger
from sqlalchemy import update
from app.services.embedding_service import embedding_service

logger = get_logger(__name__)


def save_resume(filename: str, data: ResumeParserResponseSchema, resume_id: uuid.UUID) -> None:
    try:
        db = SessionLocal()
        try:
            resume = db.query(ParsedResume).filter(ParsedResume.id == resume_id).first()
            if not resume:
                logger.error(f"Resume {resume_id} not found in database")
                return
            db.flush()

            if data.personal_info:
                pi = data.personal_info
                db.add(PersonalInfo(
                    resume_id=resume.id,
                    prefix=pi.prefix,
                    first_name=pi.first_name,
                    last_name=pi.last_name,
                    email=pi.email,
                    phone=pi.phone,
                    city=pi.city,
                    state=pi.state,
                    country=pi.country
                ))

            for edu in data.education:
                db.add(Education(
                    resume_id=resume.id,
                    degree=edu.degree,
                    specialization=edu.specialization,
                    college=edu.college,
                    start_year=edu.start_year,
                    end_year=edu.end_year
                ))

            exp = data.experience
            exp_row = Experience(
                resume_id=resume.id,
                specialization=exp.specialization,
                experience_years=exp.experience_years,
                current_designation=exp.current_designation,
                current_hospital=exp.current_hospital,
                registration_number=exp.registration_number
            )
            db.add(exp_row)
            db.flush()

            for wh in exp.work_history:
                db.add(WorkHistory(
                    experience_id=exp_row.id,
                    designation=wh.designation,
                    employer=wh.employer,
                    start_date=wh.start_date,
                    end_date=wh.end_date
                ))

            for skill in data.skills:
                db.add(ResumeSkill(resume_id=resume.id, skill=skill))

            for cert in data.certifications:
                db.add(ResumeCertification(resume_id=resume.id, certification=cert))

            for lang in data.languages:
                db.add(ResumeLanguage(resume_id=resume.id, language=lang))

            db.commit()
            logger.info(f"Saved parsed resume {resume.id} for file: {filename}")

            # Generate embedding
            try:
                parts = []
                exp = data.experience
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
                for edu in data.education:
                    if edu.degree:
                        parts.append(edu.degree)
                    if edu.specialization:
                        parts.append(edu.specialization)
                    if edu.college:
                        parts.append(edu.college)
                for skill in data.skills:
                    parts.append(skill)
                for cert in data.certifications:
                    parts.append(cert)
                for lang in data.languages:
                    parts.append(lang)
                pi = data.personal_info
                if pi:
                    if pi.city:
                        parts.append(pi.city)
                    if pi.state:
                        parts.append(pi.state)

                embedding_text = " ".join(parts)
                embedding_vec = embedding_service.encode(embedding_text)
                if embedding_vec is not None:
                    stmt = update(ParsedResume).where(ParsedResume.id == resume.id).values(embedding=embedding_vec)
                    db.execute(stmt)
                    db.commit()
                    logger.debug(f"Embedding stored for resume {resume.id}")
                else:
                    logger.warning(f"Embedding skipped for resume {resume.id} (encode returned None)")
            except Exception as e:
                logger.warning(f"Embedding generation failed for resume {resume.id} (non-fatal): {e}")
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Failed to save resume to database: {e}", exc_info=True)
