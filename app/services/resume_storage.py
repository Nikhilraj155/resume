from datetime import datetime
from app.database import SessionLocal
from app.models import (
    ParsedResume, PersonalInfo, Education, Experience,
    WorkHistory, ResumeSkill, ResumeCertification, ResumeLanguage
)
from app.schemas.resume import ResumeParserResponseSchema
from app.utils.logger import get_logger

logger = get_logger(__name__)


def save_resume(filename: str, data: ResumeParserResponseSchema) -> None:
    try:
        db = SessionLocal()
        try:
            resume = ParsedResume(
                filename=filename,
                created_at=datetime.utcnow().isoformat()
            )
            db.add(resume)
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
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Failed to save resume to database: {e}", exc_info=True)
