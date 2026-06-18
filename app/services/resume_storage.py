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

            # Generate embedding using natural language for better semantic understanding
            try:
                sentences = []
                pi = data.personal_info
                exp = data.experience

                if pi and (pi.first_name or pi.last_name):
                    name = " ".join(filter(None, [pi.prefix, pi.first_name, pi.last_name]))
                else:
                    name = None

                header_parts = []
                if name:
                    header_parts.append(name)
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

                if data.education:
                    edu_strs = []
                    for edu in data.education:
                        parts = [p for p in [edu.degree, edu.specialization, edu.college] if p]
                        if parts:
                            edu_strs.append(" ".join(parts))
                    if edu_strs:
                        sentences.append("Education: " + ", ".join(edu_strs) + ".")

                if data.skills:
                    sentences.append("Skills: " + ", ".join(data.skills) + ".")

                if data.certifications:
                    sentences.append("Certifications: " + ", ".join(data.certifications) + ".")

                if data.languages:
                    sentences.append("Languages: " + ", ".join(data.languages) + ".")

                if pi:
                    loc_parts = []
                    if pi.city:
                        loc_parts.append(pi.city)
                    if pi.state:
                        loc_parts.append(pi.state)
                    if loc_parts:
                        sentences.append("Location: " + ", ".join(loc_parts) + ".")

                embedding_text = " ".join(sentences)
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
