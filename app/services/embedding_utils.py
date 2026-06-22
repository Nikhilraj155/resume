from typing import List, Optional

from app.models import ParsedResume, PersonalInfo
from app.schemas.resume import ResumeParserResponseSchema


def build_embedding_text_from_resume(resume: ParsedResume) -> str:
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
        certs_list = [c.name for c in resume.certifications if c.name]
        if certs_list:
            sentences.append("Certifications: " + ", ".join(certs_list) + ".")

    if resume.languages:
        langs_list = []
        for l in resume.languages:
            if l.language:
                if l.proficiency:
                    langs_list.append(f"{l.language} ({l.proficiency})")
                else:
                    langs_list.append(l.language)
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


def build_embedding_text_from_schema(data: ResumeParserResponseSchema) -> str:
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

    # Skills from categorized structure
    if data.skills:
        all_skills = []
        for cat in ["clinical", "technical", "soft_skills"]:
            skills_list = getattr(data.skills, cat, [])
            all_skills.extend(skills_list)
        if all_skills:
            sentences.append("Skills: " + ", ".join(all_skills) + ".")

    if data.certifications:
        certs_list = [c.name for c in data.certifications if c.name]
        if certs_list:
            sentences.append("Certifications: " + ", ".join(certs_list) + ".")

    if data.languages:
        langs_list = []
        for l in data.languages:
            if l.language:
                if l.proficiency:
                    langs_list.append(f"{l.language} ({l.proficiency})")
                else:
                    langs_list.append(l.language)
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
