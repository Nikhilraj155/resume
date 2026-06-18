from pydantic import BaseModel, Field
from typing import List, Optional


class PersonalInfoSchema(BaseModel):
    prefix: Optional[str] = Field(None, description="Supported honorific prefix, currently only Dr")
    first_name: Optional[str] = Field(None, description="First name of the doctor")
    last_name: Optional[str] = Field(None, description="Last name of the doctor")
    email: Optional[str] = Field(None, description="Email address")
    phone: Optional[str] = Field(None, description="Contact phone number")
    city: Optional[str] = Field(None, description="City of residence")
    state: Optional[str] = Field(None, description="State of residence")
    country: Optional[str] = Field(None, description="Country of residence")
    linkedin: Optional[str] = Field(None, description="LinkedIn profile handle or URL")
    social_links: List[str] = Field(default_factory=list, description="Other social profile links")
    profile_summary: Optional[str] = Field(None, description="Professional summary/objective paragraph")


class EducationItemSchema(BaseModel):
    degree: Optional[str] = Field(None, description="Normalized degree name (MBBS, MD, MS, DM, MCh, DNB, BDS, MDS)")
    specialization: Optional[str] = Field(None, description="Area of specialization (e.g. Cardiology, Oral Surgery)")
    college: Optional[str] = Field(None, description="College or institution name")
    university: Optional[str] = Field(None, description="University name")
    start_year: Optional[str] = Field(None, description="Start year of the education")
    end_year: Optional[str] = Field(None, description="End/graduation year of the education")
    gpa: Optional[str] = Field(None, description="GPA score (e.g. 8.8/10)")
    percentage: Optional[str] = Field(None, description="Percentage score (e.g. 94.5%)")
    board: Optional[str] = Field(None, description="Examination board (e.g. CBSE, ICSE, IB)")
    level: Optional[str] = Field(None, description="Education level: postgraduate, graduate, school")


class WorkHistoryItemSchema(BaseModel):
    designation: Optional[str] = Field(None, description="Job title/role")
    employer: Optional[str] = Field(None, description="Hospital, clinic, or institution")
    employer_city: Optional[str] = Field(None, description="City of the employer")
    department: Optional[str] = Field(None, description="Department or unit")
    start_date: Optional[str] = Field(None, description="Start date of this role")
    end_date: Optional[str] = Field(None, description="End date of this role")
    duration_months: Optional[int] = Field(None, description="Duration in months")
    responsibilities: List[str] = Field(default_factory=list, description="Bullet-point responsibilities")
    employment_type: Optional[str] = Field(None, description="Full-time, Part-time, Locum, Internship, etc.")


class ExperienceSchema(BaseModel):
    specialization: Optional[str] = Field(None, description="Area of clinical/medical specialization")
    experience_years: Optional[float] = Field(None, description="Calculated total years of experience as a number")
    current_designation: Optional[str] = Field(None, description="Current job title/role")
    current_hospital: Optional[str] = Field(None, description="Current hospital, clinic, or institution of employment")
    current_department: Optional[str] = Field(None, description="Current department")
    registration_number: Optional[str] = Field(None, description="Medical registration/license number")
    registration_council: Optional[str] = Field(None, description="Medical council that issued registration")
    registration_year: Optional[int] = Field(None, description="Year of registration")
    work_history: List[WorkHistoryItemSchema] = Field(default_factory=list, description="List of all individual work experience entries")


class CertificationSchema(BaseModel):
    name: Optional[str] = Field(None, description="Full certification name")
    abbreviation: Optional[str] = Field(None, description="Abbreviated form (e.g. ACLS, BLS, ICOI)")
    issuer: Optional[str] = Field(None, description="Issuing organization")
    year: Optional[int] = Field(None, description="Year obtained")
    description: Optional[str] = Field(None, description="Additional details")


class LanguageSchema(BaseModel):
    language: Optional[str] = Field(None, description="Language name")
    proficiency: Optional[str] = Field(None, description="Proficiency level: Fluent, Native, Intermediate, Basic")


class SkillCategorySchema(BaseModel):
    clinical: List[str] = Field(default_factory=list, description="Clinical/medical skills")
    technical: List[str] = Field(default_factory=list, description="Technical & software skills")
    soft_skills: List[str] = Field(default_factory=list, description="Soft skills & interpersonal abilities")


class PublicationSchema(BaseModel):
    title: Optional[str] = Field(None, description="Publication title")
    journal: Optional[str] = Field(None, description="Journal or conference name")
    year: Optional[int] = Field(None, description="Publication year")
    authors: List[str] = Field(default_factory=list, description="List of authors")
    doi: Optional[str] = Field(None, description="Digital Object Identifier")


class MetadataSchema(BaseModel):
    parsed_at: Optional[str] = Field(None, description="ISO timestamp of parsing")
    parser_version: Optional[str] = Field(None, description="Parser version identifier")
    file_type: Optional[str] = Field(None, description="Original file type (pdf, docx)")
    last_updated: Optional[str] = Field(None, description="Last updated date from resume text")


class ResumeParserResponseSchema(BaseModel):
    id: Optional[str] = Field(None, description="Unique resume ID (UUID)")
    personal_info: PersonalInfoSchema
    education: List[EducationItemSchema] = Field(default_factory=list)
    experience: ExperienceSchema
    skills: SkillCategorySchema = Field(default_factory=SkillCategorySchema)
    certifications: List[CertificationSchema] = Field(default_factory=list)
    languages: List[LanguageSchema] = Field(default_factory=list)
    publications: List[PublicationSchema] = Field(default_factory=list)
    metadata: Optional[MetadataSchema] = None
