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

class EducationItemSchema(BaseModel):
    degree: Optional[str] = Field(None, description="Normalized degree name (MBBS, MD, MS, DM, MCh, DNB, BDS, MDS)")
    specialization: Optional[str] = Field(None, description="Area of specialization")
    college: Optional[str] = Field(None, description="Name of the university/college")
    start_year: Optional[str] = Field(None, description="Start year of the education")
    end_year: Optional[str] = Field(None, description="End/graduation year of the education")

class WorkHistoryItemSchema(BaseModel):
    designation: Optional[str] = Field(None, description="Job title/role")
    employer: Optional[str] = Field(None, description="Hospital, clinic, or institution")
    start_date: Optional[str] = Field(None, description="Start date of this role")
    end_date: Optional[str] = Field(None, description="End date of this role")

class ExperienceSchema(BaseModel):
    specialization: Optional[str] = Field(None, description="Area of clinical/medical specialization")
    experience_years: Optional[float] = Field(None, description="Calculated total years of experience as a number")
    current_designation: Optional[str] = Field(None, description="Current job title/role")
    current_hospital: Optional[str] = Field(None, description="Current hospital, clinic, or institution of employment")
    registration_number: Optional[str] = Field(None, description="Medical registration/license number")
    work_history: List[WorkHistoryItemSchema] = Field(default_factory=list, description="List of all individual work experience entries")

class ResumeParserResponseSchema(BaseModel):
    id: Optional[str] = Field(None, description="Unique resume ID (UUID)")
    personal_info: PersonalInfoSchema
    education: List[EducationItemSchema] = Field(default_factory=list)
    experience: ExperienceSchema
    skills: List[str] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)
