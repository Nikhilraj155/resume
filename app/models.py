import uuid
from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, String, Float, Boolean, ForeignKey, Text, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class ParsedResume(Base):
    __tablename__ = "parsed_resumes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String(255), nullable=False)
    created_at = Column(Text, nullable=False)
    embedding = Column(Vector(384), nullable=True)

    personal_info = relationship("PersonalInfo", uselist=False, back_populates="resume", cascade="all, delete-orphan")
    education = relationship("Education", back_populates="resume", cascade="all, delete-orphan")
    experience = relationship("Experience", uselist=False, back_populates="resume", cascade="all, delete-orphan")
    skills = relationship("ResumeSkill", back_populates="resume", cascade="all, delete-orphan")
    certifications = relationship("ResumeCertification", back_populates="resume", cascade="all, delete-orphan")
    languages = relationship("ResumeLanguage", back_populates="resume", cascade="all, delete-orphan")
    publications = relationship("ResumePublication", back_populates="resume", cascade="all, delete-orphan")


class PersonalInfo(Base):
    __tablename__ = "personal_info"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resume_id = Column(UUID(as_uuid=True), ForeignKey("parsed_resumes.id", ondelete="CASCADE"), nullable=False)
    prefix = Column(String(20), nullable=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)
    linkedin = Column(String(255), nullable=True)
    social_links = Column(Text, nullable=True)
    profile_summary = Column(Text, nullable=True)

    resume = relationship("ParsedResume", back_populates="personal_info")


class Education(Base):
    __tablename__ = "education"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resume_id = Column(UUID(as_uuid=True), ForeignKey("parsed_resumes.id", ondelete="CASCADE"), nullable=False)
    degree = Column(String(100), nullable=True)
    specialization = Column(String(200), nullable=True)
    college = Column(String(300), nullable=True)
    university = Column(String(300), nullable=True)
    start_year = Column(String(10), nullable=True)
    end_year = Column(String(10), nullable=True)
    gpa = Column(String(20), nullable=True)
    percentage = Column(String(20), nullable=True)
    board = Column(String(50), nullable=True)
    level = Column(String(20), nullable=True)

    resume = relationship("ParsedResume", back_populates="education")


class Experience(Base):
    __tablename__ = "experience"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resume_id = Column(UUID(as_uuid=True), ForeignKey("parsed_resumes.id", ondelete="CASCADE"), nullable=False)
    specialization = Column(String(200), nullable=True)
    experience_years = Column(Float, nullable=True)
    current_designation = Column(String(300), nullable=True)
    current_hospital = Column(String(300), nullable=True)
    current_department = Column(String(200), nullable=True)
    registration_number = Column(String(100), nullable=True)
    registration_council = Column(String(200), nullable=True)
    registration_year = Column(Integer, nullable=True)

    resume = relationship("ParsedResume", back_populates="experience")
    work_history = relationship("WorkHistory", back_populates="experience", cascade="all, delete-orphan")


class WorkHistory(Base):
    __tablename__ = "work_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    experience_id = Column(UUID(as_uuid=True), ForeignKey("experience.id", ondelete="CASCADE"), nullable=False)
    designation = Column(String(300), nullable=True)
    employer = Column(String(300), nullable=True)
    employer_city = Column(String(100), nullable=True)
    department = Column(String(200), nullable=True)
    start_date = Column(String(50), nullable=True)
    end_date = Column(String(50), nullable=True)
    duration_months = Column(Integer, nullable=True)
    employment_type = Column(String(50), nullable=True)

    experience = relationship("Experience", back_populates="work_history")
    responsibilities = relationship("WorkHistoryResponsibility", back_populates="work_history", cascade="all, delete-orphan")


class WorkHistoryResponsibility(Base):
    __tablename__ = "work_history_responsibilities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    work_history_id = Column(UUID(as_uuid=True), ForeignKey("work_history.id", ondelete="CASCADE"), nullable=False)
    responsibility = Column(Text, nullable=False)

    work_history = relationship("WorkHistory", back_populates="responsibilities")


class ResumeSkill(Base):
    __tablename__ = "resume_skills"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resume_id = Column(UUID(as_uuid=True), ForeignKey("parsed_resumes.id", ondelete="CASCADE"), nullable=False)
    skill = Column(String(200), nullable=False)
    category = Column(String(20), nullable=True)

    resume = relationship("ParsedResume", back_populates="skills")


class ResumeCertification(Base):
    __tablename__ = "resume_certifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resume_id = Column(UUID(as_uuid=True), ForeignKey("parsed_resumes.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(300), nullable=False)
    abbreviation = Column(String(50), nullable=True)
    issuer = Column(String(300), nullable=True)
    year = Column(Integer, nullable=True)
    description = Column(Text, nullable=True)

    resume = relationship("ParsedResume", back_populates="certifications")


class ResumeLanguage(Base):
    __tablename__ = "resume_languages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resume_id = Column(UUID(as_uuid=True), ForeignKey("parsed_resumes.id", ondelete="CASCADE"), nullable=False)
    language = Column(String(100), nullable=False)
    proficiency = Column(String(20), nullable=True)

    resume = relationship("ParsedResume", back_populates="languages")


class ResumePublication(Base):
    __tablename__ = "resume_publications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resume_id = Column(UUID(as_uuid=True), ForeignKey("parsed_resumes.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(500), nullable=True)
    journal = Column(String(300), nullable=True)
    year = Column(Integer, nullable=True)
    authors = Column(Text, nullable=True)
    doi = Column(String(200), nullable=True)

    resume = relationship("ParsedResume", back_populates="publications")


# ── Job Description Reference Models (read-only, map to ai-service_2 tables) ──


class JobDescriptionRef(Base):
    __tablename__ = "job_descriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    original_text = Column(Text, nullable=False)
    job_title = Column(String(300), nullable=True)
    company_name = Column(String(300), nullable=True)
    location = Column(String(300), nullable=True)
    employment_type = Column(String(100), nullable=True)
    salary_min = Column(Float, nullable=True)
    salary_max = Column(Float, nullable=True)
    salary_currency = Column(String(10), nullable=True)
    experience_min = Column(Float, nullable=True)
    experience_max = Column(Float, nullable=True)
    summary = Column(Text, nullable=True)
    industry = Column(String(100), nullable=True)
    requirements = Column(Text, nullable=True)
    keywords = Column(Text, nullable=True)
    created_at = Column(Text, nullable=False)
    embedding = Column(Vector(384), nullable=True)

    skills = relationship("JobSkillRef", back_populates="job")
    education_requirements = relationship("JobEducationRequirementRef", back_populates="job")
    certifications = relationship("JobCertificationRef", back_populates="job")
    responsibilities = relationship("JobResponsibilityRef", back_populates="job")


class JobSkillRef(Base):
    __tablename__ = "job_skills"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("job_descriptions.id", ondelete="CASCADE"), nullable=False)
    skill = Column(String(200), nullable=False)
    is_required = Column(Boolean, default=True)
    category = Column(String(20), nullable=True)

    job = relationship("JobDescriptionRef", back_populates="skills")


class JobEducationRequirementRef(Base):
    __tablename__ = "job_education_requirements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("job_descriptions.id", ondelete="CASCADE"), nullable=False)
    degree = Column(String(200), nullable=True)
    required = Column(Boolean, default=True)

    job = relationship("JobDescriptionRef", back_populates="education_requirements")


class JobCertificationRef(Base):
    __tablename__ = "job_certifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("job_descriptions.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(300), nullable=True)
    required = Column(Boolean, default=True)

    job = relationship("JobDescriptionRef", back_populates="certifications")


class JobResponsibilityRef(Base):
    __tablename__ = "job_responsibilities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("job_descriptions.id", ondelete="CASCADE"), nullable=False)
    responsibility = Column(Text, nullable=True)

    job = relationship("JobDescriptionRef", back_populates="responsibilities")
