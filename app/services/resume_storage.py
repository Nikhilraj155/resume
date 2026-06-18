import uuid
import json
from sqlalchemy import update
from app.database import SessionLocal
from app.models import (
    ParsedResume, PersonalInfo, Education, Experience,
    WorkHistory, WorkHistoryResponsibility, ResumeSkill,
    ResumeCertification, ResumeLanguage, ResumePublication,
)
from app.schemas.resume import ResumeParserResponseSchema
from app.utils.logger import get_logger
from app.services.embedding_service import embedding_service
from app.services.embedding_utils import build_embedding_text_from_schema

logger = get_logger(__name__)


def save_resume(filename: str, data: ResumeParserResponseSchema, resume_id: uuid.UUID) -> None:
    try:
        db = SessionLocal()
        try:
            resume = db.query(ParsedResume).filter(ParsedResume.id == resume_id).first()
            if not resume:
                logger.error(f"Resume {resume_id} not found in database")
                return

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
                    country=pi.country,
                    linkedin=pi.linkedin,
                    social_links=json.dumps(pi.social_links) if pi.social_links else None,
                    profile_summary=pi.profile_summary,
                ))

            if data.education:
                db.bulk_insert_mappings(Education, [
                    dict(
                        resume_id=resume.id,
                        degree=edu.degree,
                        specialization=edu.specialization,
                        college=edu.college,
                        university=edu.university,
                        start_year=edu.start_year,
                        end_year=edu.end_year,
                        gpa=edu.gpa,
                        percentage=edu.percentage,
                        board=edu.board,
                        level=edu.level,
                    )
                    for edu in data.education
                ])

            exp = data.experience
            exp_row = Experience(
                resume_id=resume.id,
                specialization=exp.specialization,
                experience_years=exp.experience_years,
                current_designation=exp.current_designation,
                current_hospital=exp.current_hospital,
                current_department=exp.current_department,
                registration_number=exp.registration_number,
                registration_council=exp.registration_council,
                registration_year=exp.registration_year,
            )
            db.add(exp_row)
            db.flush()

            if exp.work_history:
                for wh in exp.work_history:
                    wh_row = WorkHistory(
                        experience_id=exp_row.id,
                        designation=wh.designation,
                        employer=wh.employer,
                        employer_city=wh.employer_city,
                        department=wh.department,
                        start_date=wh.start_date,
                        end_date=wh.end_date,
                        duration_months=wh.duration_months,
                        employment_type=wh.employment_type,
                    )
                    db.add(wh_row)
                    db.flush()

                    if wh.responsibilities:
                        db.bulk_insert_mappings(WorkHistoryResponsibility, [
                            dict(
                                work_history_id=wh_row.id,
                                responsibility=resp,
                            )
                            for resp in wh.responsibilities
                        ])

            # Skills - categorized
            if data.skills:
                skill_rows = []
                for cat in ["clinical", "technical", "soft_skills"]:
                    skills_list = getattr(data.skills, cat, [])
                    for skill in skills_list:
                        skill_rows.append(dict(resume_id=resume.id, skill=skill, category=cat))
                if skill_rows:
                    db.bulk_insert_mappings(ResumeSkill, skill_rows)

            # Certifications - structured
            if data.certifications:
                db.bulk_insert_mappings(ResumeCertification, [
                    dict(
                        resume_id=resume.id,
                        name=cert.name,
                        abbreviation=cert.abbreviation,
                        issuer=cert.issuer,
                        year=cert.year,
                        description=cert.description,
                    )
                    for cert in data.certifications
                ])

            # Languages - with proficiency
            if data.languages:
                db.bulk_insert_mappings(ResumeLanguage, [
                    dict(
                        resume_id=resume.id,
                        language=lang.language,
                        proficiency=lang.proficiency,
                    )
                    for lang in data.languages
                ])

            # Publications
            if data.publications:
                db.bulk_insert_mappings(ResumePublication, [
                    dict(
                        resume_id=resume.id,
                        title=pub.title,
                        journal=pub.journal,
                        year=pub.year,
                        authors=json.dumps(pub.authors) if pub.authors else None,
                        doi=pub.doi,
                    )
                    for pub in data.publications
                ])

            db.commit()
            logger.info(f"Saved parsed resume {resume.id} for file: {filename}")
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Failed to save resume to database: {e}", exc_info=True)


def store_embedding(resume_id: uuid.UUID, data: ResumeParserResponseSchema) -> None:
    db = SessionLocal()
    try:
        embedding_text = build_embedding_text_from_schema(data)
        embedding_vec = embedding_service.encode(embedding_text)
        if embedding_vec is not None:
            stmt = update(ParsedResume).where(ParsedResume.id == resume_id).values(embedding=embedding_vec)
            db.execute(stmt)
            db.commit()
            logger.debug(f"Embedding stored for resume {resume_id}")
        else:
            logger.warning(f"Embedding skipped for resume {resume_id} (encode returned None)")
    except Exception as e:
        logger.warning(f"Embedding generation failed for resume {resume_id} (non-fatal): {e}")
    finally:
        db.close()
