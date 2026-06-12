import uuid
from sqlalchemy import Column, String, Float, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class ParsedResume(Base):
    __tablename__ = "parsed_resumes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String(255), nullable=False)
    created_at = Column(Text, nullable=False)

    personal_info = relationship("PersonalInfo", uselist=False, back_populates="resume", cascade="all, delete-orphan")
    education = relationship("Education", back_populates="resume", cascade="all, delete-orphan")
    experience = relationship("Experience", uselist=False, back_populates="resume", cascade="all, delete-orphan")
    skills = relationship("ResumeSkill", back_populates="resume", cascade="all, delete-orphan")
    certifications = relationship("ResumeCertification", back_populates="resume", cascade="all, delete-orphan")
    languages = relationship("ResumeLanguage", back_populates="resume", cascade="all, delete-orphan")


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

    resume = relationship("ParsedResume", back_populates="personal_info")


class Education(Base):
    __tablename__ = "education"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resume_id = Column(UUID(as_uuid=True), ForeignKey("parsed_resumes.id", ondelete="CASCADE"), nullable=False)
    degree = Column(String(100), nullable=True)
    specialization = Column(String(200), nullable=True)
    college = Column(String(300), nullable=True)
    start_year = Column(String(10), nullable=True)
    end_year = Column(String(10), nullable=True)

    resume = relationship("ParsedResume", back_populates="education")


class Experience(Base):
    __tablename__ = "experience"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resume_id = Column(UUID(as_uuid=True), ForeignKey("parsed_resumes.id", ondelete="CASCADE"), nullable=False)
    specialization = Column(String(200), nullable=True)
    experience_years = Column(Float, nullable=True)
    current_designation = Column(String(300), nullable=True)
    current_hospital = Column(String(300), nullable=True)
    registration_number = Column(String(100), nullable=True)

    resume = relationship("ParsedResume", back_populates="experience")
    work_history = relationship("WorkHistory", back_populates="experience", cascade="all, delete-orphan")


class WorkHistory(Base):
    __tablename__ = "work_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    experience_id = Column(UUID(as_uuid=True), ForeignKey("experience.id", ondelete="CASCADE"), nullable=False)
    designation = Column(String(300), nullable=True)
    employer = Column(String(300), nullable=True)
    start_date = Column(String(50), nullable=True)
    end_date = Column(String(50), nullable=True)

    experience = relationship("Experience", back_populates="work_history")


class ResumeSkill(Base):
    __tablename__ = "resume_skills"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resume_id = Column(UUID(as_uuid=True), ForeignKey("parsed_resumes.id", ondelete="CASCADE"), nullable=False)
    skill = Column(String(200), nullable=False)

    resume = relationship("ParsedResume", back_populates="skills")


class ResumeCertification(Base):
    __tablename__ = "resume_certifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resume_id = Column(UUID(as_uuid=True), ForeignKey("parsed_resumes.id", ondelete="CASCADE"), nullable=False)
    certification = Column(String(300), nullable=False)

    resume = relationship("ParsedResume", back_populates="certifications")


class ResumeLanguage(Base):
    __tablename__ = "resume_languages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resume_id = Column(UUID(as_uuid=True), ForeignKey("parsed_resumes.id", ondelete="CASCADE"), nullable=False)
    language = Column(String(100), nullable=False)

    resume = relationship("ParsedResume", back_populates="languages")
