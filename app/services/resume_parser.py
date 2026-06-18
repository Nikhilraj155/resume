import os
import re
from typing import List, Dict, Any, Optional

from app.schemas.resume import (
    ResumeParserResponseSchema,
    PersonalInfoSchema,
    EducationItemSchema,
    ExperienceSchema,
    WorkHistoryItemSchema
)
from app.services.pdf_extractor import PDFExtractorService
from app.services.spacy_parser import SpacyParserService
from app.services.medical_skill_extractor import MedicalSkillExtractorService
from app.services.experience_calculator import ExperienceCalculatorService

from app.constants.medical_constants import (
    CERTIFICATIONS,
    LANGUAGES,
    DEGREE_KEYWORDS,
    SPECIALIZATION_KEYWORDS
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Heuristics lists
KNOWN_COUNTRIES = {"india", "united states", "usa", "united kingdom", "uk", "canada", "australia", "germany", "uae", "singapore"}
KNOWN_STATES = {
    "maharashtra", "massachusetts", "california", "texas", "new york", "tamil nadu", 
    "karnataka", "delhi", "gujarat", "florida", "illinois", "pennsylvania", "ohio", 
    "kerala", "telangana", "andhra pradesh", "west bengal"
}
KNOWN_CITIES = {"bengaluru", "bangalore", "mumbai", "pune", "delhi", "new delhi", "hyderabad", "chennai", "kolkata", "ahmedabad", "jaipur", "lucknow", "noida", "gurgaon", "chandigarh", "indore", "bhopal", "surat", "kochi", "goa", "nagpur", "patna", "thane", "agra", "varanasi", "nashik", "meerut", "rajkot", "vadodara", "vijayawada", "mangalore", "mysore"}


def _clean_location_string(raw: str) -> str:
    """Strip email, phone, URLs, social handles, pipe-separated junk from a location string,
    returning just the most likely city/place name."""
    if not raw:
        return raw
    cleaned = raw
    # Remove email addresses
    cleaned = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '', cleaned)
    # Remove phone numbers
    cleaned = re.sub(r'\+?\d{1,4}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4,6}', '', cleaned)
    # Remove URLs
    cleaned = re.sub(r'https?://\S+', '', cleaned)
    cleaned = re.sub(r'www\.\S+', '', cleaned)
    # Remove social handles (#handle, @handle)
    cleaned = re.sub(r'[#@]\w+', '', cleaned)
    # Remove pipe-separated segments - keep the last one (likely the city)
    if '|' in cleaned:
        segments = [s.strip() for s in cleaned.split('|') if s.strip()]
        valid_segments = [s for s in segments if not any(c in s for c in ['@', '#', '+', '.com', '.in'])]
        if valid_segments:
            cleaned = valid_segments[-1]
        else:
            cleaned = segments[-1]
    # Extract just alphabetic words
    words = re.findall(r'[A-Za-z]+', cleaned)
    # Check against known cities first
    for word in words:
        if word.lower() in KNOWN_CITIES:
            return word.title()
    # Fall back to the last word with 3+ characters (most likely the city)
    for word in reversed(words):
        if len(word) >= 3:
            return word.title()
    # Last resort: return the first substantial word
    for word in words:
        if len(word) >= 2:
            return word.title()
    return cleaned.strip()

class ResumeParserService:
    def __init__(self):
        self.spacy_parser = SpacyParserService()

    def _parse_work_history(self, experience_text: str) -> list:
        """
        Parses work history from the experience section.

        Expected line format from the PDF extractor:
          "Designation, Dept  StartDate - EndDate"   (designation line with inline dates)
          "- bullet..."                               (bullet points — skipped)
          "continuation of bullet"                   (wrapped bullet lines — skipped)
          "Employer Name, City"                       (employer line: standalone, contains hospital keyword)

        A new job block starts when a designation line with a date range is found.
        The employer is the first standalone non-bullet line after the bullets.
        """
        if not experience_text.strip():
            return []

        DATE_RANGE = re.compile(
            r'((?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?'
            r'|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)'
            r'\s+(?:19|20)\d{2}|(?:19|20)\d{2})'
            r'\s*[-–—]\s*'
            r'((?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?'
            r'|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)'
            r'\s+(?:19|20)\d{2}|(?:19|20)\d{2}|present|current|now|till date|ongoing)',
            re.IGNORECASE
        )
        EMPLOYER_KEYWORDS = ["hospital", "clinic", "medical", "centre", "center", "healthcare",
                             "health", "nursing", "institute", "foundation", "pvt", "ltd", "college"]

        lines = [l.strip() for l in experience_text.split('\n') if l.strip()]

        blocks: list[dict] = []
        in_bullet = False  # True while we're inside a bullet item (including wrapped lines)

        for line in lines:
            is_bullet_start = line.startswith('-') or line.startswith('•')

            if is_bullet_start:
                in_bullet = True
                continue

            dr_match = DATE_RANGE.search(line)
            if dr_match:
                # New job block starts here
                in_bullet = False
                before_date = line[:dr_match.start()].strip().rstrip('(').strip()

                # Try to split "Designation - Employer, City" on the first ' - ' or ' – '
                employer = None
                designation = before_date
                sep = re.search(r'\s[-–]\s', before_date)
                if sep:
                    left_part = before_date[:sep.start()].strip()
                    right_part = before_date[sep.end():].strip()
                    if any(kw in right_part.lower() for kw in EMPLOYER_KEYWORDS):
                        designation = left_part
                        employer = right_part.split(',')[0].strip()  # drop city suffix
                    elif any(kw in left_part.lower() for kw in EMPLOYER_KEYWORDS):
                        designation = right_part
                        employer = left_part.split(',')[0].strip()

                blocks.append({
                    'designation': designation.rstrip(',').strip() or None,
                    'start_date': dr_match.group(1).strip(),
                    'end_date': dr_match.group(2).strip(),
                    'employer': employer,
                })
                continue

            if in_bullet:
                # Wrapped continuation of a bullet — skip
                continue

            # Standalone line (not a bullet, not a designation line)
            if blocks and blocks[-1]['employer'] is None:
                if any(kw in line.lower() for kw in EMPLOYER_KEYWORDS):
                    # Full employer name; strip city if 3+ comma parts
                    parts = [p.strip() for p in line.split(',')]
                    blocks[-1]['employer'] = parts[0] if len(parts) >= 3 else line

        return [
            WorkHistoryItemSchema(
                designation=b['designation'],
                employer=b['employer'],
                start_date=b['start_date'],
                end_date=b['end_date'],
            )
            for b in blocks
        ]

    def _segment_text(self, text: str) -> Dict[str, str]:
        """
        Segments the resume text into sections based on typical headers.
        """
        lines = [line.strip() for line in text.split("\n")]
        sections = {
            "header": [],
            "experience": [],
            "education": [],
            "skills": [],
            "certifications": [],
            "projects": [],
            "other": []
        }
        
        current_section = "header"
        
        for line in lines:
            if not line:
                continue
            line_lower = line.lower().strip()
            # Clean punctuation for header matching
            cleaned_header = re.sub(r'[^\w\s]', '', line_lower).strip()
            
            # Identify section transitions
            if any(h == cleaned_header or cleaned_header.startswith(h) for h in ["work experience", "experience", "employment", "professional history", "career history", "work history"]) and len(cleaned_header) < 40:
                current_section = "experience"
                continue
            elif any(h == cleaned_header or cleaned_header.startswith(h) for h in ["education", "academic", "qualifications", "credentials", "academic background"]) and len(cleaned_header) < 40:
                current_section = "education"
                continue
            elif any(h == cleaned_header or cleaned_header.startswith(h) for h in ["technical skills", "skills", "clinical skills", "key skills", "professional skills", "expertise"]) and len(cleaned_header) < 40:
                current_section = "skills"
                continue
            elif any(h == cleaned_header or cleaned_header.startswith(h) for h in ["certifications", "licenses", "credentials", "courses"]) and len(cleaned_header) < 40:
                current_section = "certifications"
                continue
            elif any(h == cleaned_header or cleaned_header.startswith(h) for h in ["projects", "academic projects", "key projects", "projects during internship"]) and len(cleaned_header) < 40:
                current_section = "projects"
                continue
                
            sections[current_section].append(line)
            
        return {k: "\n".join(v) for k, v in sections.items()}

    def parse_resume(self, filepath: str) -> ResumeParserResponseSchema:
        """
        Parses a medical resume from a PDF or DOCX file using open-source tools
        (PyMuPDF, python-docx, spaCy, and Regex) and structured heuristics.
        """
        logger.info(f"Starting open-source parse execution for: {filepath}")
        
        # 1. Extract Text
        ext = os.path.splitext(filepath)[1].lower()
        if ext == '.docx':
            text = PDFExtractorService.extract_text_from_docx(filepath)
        else:
            text = PDFExtractorService.extract_text(filepath)
        normalized_text = " ".join(text.split())
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        
        # Segment text into logical sections
        sections = self._segment_text(text)

        # 2. Extract Name using spaCy / heuristics
        prefix, first_name, last_name = self.spacy_parser.extract_name_details(text)

        # 3. Extract Entities using spaCy (Locations and Organizations)
        entities = self.spacy_parser.extract_entities(text)
        
        # Heuristics to classify City, State, Country
        city = None
        state = None
        country = None

        # Collect all raw header lines for fallback extraction
        header_text = sections.get("header", "")
        header_lines = []
        if header_text:
            header_lines = [line.strip() for line in header_text.split("\n") if line.strip()]

        # First, try to parse from the header block (lines 2-4 usually contain address)
        if header_lines:
            for line in header_lines[1:4]:
                parts = [p.strip() for p in line.split(",") if p.strip()]
                if len(parts) >= 2:
                    raw_city = parts[0].strip()
                    raw_state_or_country = parts[1].strip()

                    # Skip if city looks like a degree/qualification (e.g. "MBBS", "MD")
                    if any(re.search(rf'\b{re.escape(d)}\b', raw_city, re.IGNORECASE) for d in DEGREE_KEYWORDS):
                        continue
                    # Skip if state looks like a degree/qualification
                    if any(re.search(rf'\b{re.escape(d)}\b', raw_state_or_country, re.IGNORECASE) for d in DEGREE_KEYWORDS):
                        continue

                    # Check if extracted city is clean (only letters/spaces) or garbled
                    if re.match(r'^[A-Za-z\s]+$', raw_city):
                        city = raw_city.title()
                    else:
                        # City field is garbled — try to extract a clean city name
                        cleaned = _clean_location_string(raw_city)
                        if cleaned and len(cleaned) >= 2:
                            city = cleaned
                        else:
                            # Search header lines for known city names
                            for hl in header_lines:
                                for known in KNOWN_CITIES:
                                    if re.search(rf'(?<![A-Za-z]){re.escape(known)}(?![A-Za-z])', hl, re.IGNORECASE):
                                        city = known.title()
                                        break
                                if city:
                                    break

                    part2_lower = raw_state_or_country.lower()
                    if part2_lower in KNOWN_COUNTRIES:
                        country = parts[1].title()
                    elif part2_lower in KNOWN_STATES:
                        state = parts[1].title()
                    else:
                        state = parts[1].title()

                    if len(parts) >= 3:
                        part3_lower = parts[2].lower()
                        if part3_lower in KNOWN_COUNTRIES:
                            country = parts[2].title()
                        elif part3_lower in KNOWN_STATES and not state:
                            state = parts[2].title()

                    if city:
                        break

        # If city still missing or garbled, fall back to spaCy GPE entities
        gpe_entities = entities.get("GPE", [])
        for gpe in gpe_entities:
            gpe_lower = gpe.lower()
            if gpe_lower in KNOWN_COUNTRIES:
                if not country:
                    country = gpe
            elif gpe_lower in KNOWN_STATES:
                if not state:
                    state = gpe
            else:
                if not city:
                    city = gpe

        # General fallbacks from text search
        if not country:
            for c in KNOWN_COUNTRIES:
                if re.search(rf"\b{re.escape(c)}\b", normalized_text, re.IGNORECASE):
                    country = c.upper() if c in ["usa", "uk", "uae"] else c.title()
                    break
        if not state:
            for s in KNOWN_STATES:
                if re.search(rf"\b{re.escape(s)}\b", normalized_text, re.IGNORECASE):
                    state = s.title()
                    break

        # 4. Extract Email & Phone using Regex
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', normalized_text)
        email = email_match.group(0) if email_match else None

        phone_match = re.search(r'(\+?\d{1,4}[-.\s]?)?(\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4,6}', normalized_text)
        phone = phone_match.group(0) if phone_match else None

        # Assemble Personal Info
        personal_info = PersonalInfoSchema(
            prefix=prefix,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            city=city,
            state=state,
            country=country
        )

        # 5. Extract Education Items
        education_items = []
        education_text = sections.get("education", "")
        if education_text:
            edu_lines = [line.strip() for line in education_text.split("\n") if line.strip()]
            for idx, line in enumerate(edu_lines):
                found_degree = None
                for deg in DEGREE_KEYWORDS:
                    if re.search(rf"\b{re.escape(deg)}\b", line, re.IGNORECASE):
                        found_degree = deg
                        break
                
                if found_degree:
                    context_lines = edu_lines[idx: idx+3]
                    context_text = " ".join(context_lines)
                    
                    # Extract College
                    college = None
                    for context_line in context_lines:
                        if any(kw in context_line.lower() for kw in ["college", "university", "school", "institute", "hospital", "academy", "vidyapeeth", "vishwavidyalaya", "gurukul", "vidyalaya"]):
                            c_part = context_line
                            if "|" in c_part:
                                c_part = c_part.split("|")[0].strip()
                            
                            # Clean up if it contains the degree string itself
                            c_part_clean = re.sub(rf"\b{re.escape(found_degree)}\b", "", c_part, flags=re.IGNORECASE).strip()
                            # Clean up other prefix characters
                            c_part_clean = re.sub(r'^[–\-|]+', '', c_part_clean).strip()
                            
                            # Remove anything before and including first '-' or '–' or '|' or ':' if it contains the degree/metadata
                            if any(dash in c_part_clean for dash in ["–", "-", "|", ":"]):
                                split_parts = re.split(r'[-–—|:]', c_part_clean, maxsplit=1)
                                if len(split_parts) > 1 and len(split_parts[1].strip()) > 3:
                                    c_part_clean = split_parts[1].strip()
                            
                            # Strip remaining brackets/CBSE patterns
                            c_part_clean = re.sub(r'^\s*[\(\[A-Za-z0-9\s\)\]\-\–\|]+[–\-–\|]', '', c_part_clean).strip()
                            c_part_clean = re.sub(r'^\s*\([^\)]*\)\s*', '', c_part_clean).strip()
                            
                            college = c_part_clean if len(c_part_clean) > 3 else c_part.strip()
                            break
                            
                    if not college:
                        # Check ORG entities matching the context
                        for org in entities.get("ORG", []):
                            if org in context_text and any(kw in org.lower() for kw in ["college", "university", "school", "institute", "hospital", "academy"]):
                                college = org
                                break

                    # Extract Years (4-digit numbers) from the same line as degree or college first
                    years_found = []
                    # Check college line
                    if college:
                        for context_line in context_lines:
                            if college in context_line:
                                years_found = re.findall(r'\b(19\d{2}|20\d{2})\b', context_line)
                                if years_found:
                                    break
                    # Fallback to degree line
                    if not years_found:
                        years_found = re.findall(r'\b(19\d{2}|20\d{2})\b', line)
                    # Fallback to entire context
                    if not years_found:
                        years_found = re.findall(r'\b(19\d{2}|20\d{2})\b', context_text)

                    years = [int(yr) for yr in years_found]
                    start_year = None
                    end_year = None
                    if len(years) >= 2:
                        years = sorted(list(set(years)))
                        start_year = str(years[0])
                        end_year = str(years[1])
                    elif len(years) == 1:
                        end_year = str(years[0])

                    # Extract Specialization
                    specialization = None
                    for spec_kw in SPECIALIZATION_KEYWORDS:
                        if re.search(rf"\b{re.escape(spec_kw)}\b", context_text, re.IGNORECASE):
                            specialization = spec_kw
                            break

                    education_items.append(
                        EducationItemSchema(
                            degree=found_degree,
                            specialization=specialization,
                            college=college,
                            start_year=start_year,
                            end_year=end_year
                        )
                    )

        # Remove duplicate education items
        seen_edu = set()
        unique_education = []
        for edu in education_items:
            key = (edu.degree.lower() if edu.degree else "", edu.college.lower() if edu.college else "")
            if key not in seen_edu:
                seen_edu.add(key)
                unique_education.append(edu)

        # 6. Extract Experience
        # Calculate experience ONLY from the experience section to avoid counting education years
        experience_text = sections.get("experience", "")
        if experience_text:
            exp_years = ExperienceCalculatorService.calculate_experience(experience_text)
        else:
            # Fallback to whole text if no section segment found
            exp_years = ExperienceCalculatorService.calculate_experience(text)

        # Experience Specialization
        experience_spec = None
        for spec_kw in SPECIALIZATION_KEYWORDS:
            if re.search(rf"\b{re.escape(spec_kw)}\b", normalized_text, re.IGNORECASE):
                experience_spec = spec_kw
                break

        # Current Designation & Hospital/Employer
        current_designation = None
        current_hospital = None
        
        if experience_text:
            exp_lines = [line.strip() for line in experience_text.split("\n") if line.strip()]
            if exp_lines:
                first_exp_line = exp_lines[0]
                parts = []
                if "|" in first_exp_line:
                    parts = [p.strip() for p in first_exp_line.split("|")]
                elif " - " in first_exp_line:
                    parts = [p.strip() for p in first_exp_line.split(" - ")]
                elif " – " in first_exp_line:
                    parts = [p.strip() for p in first_exp_line.split(" – ")]
                elif " at " in first_exp_line.lower():
                    parts = [p.strip() for p in re.split(r'\s+at\s+', first_exp_line, flags=re.IGNORECASE)]
                elif "," in first_exp_line:
                    parts = [p.strip() for p in first_exp_line.split(",")]
                    
                if len(parts) >= 2:
                    current_designation = parts[0]
                    current_hospital = parts[1]
                    if "," in current_hospital:
                        current_hospital = current_hospital.split(",")[0].strip()
                        
        # General fallback if not found from section parsing
        if not current_designation:
            designation_keywords = ["resident", "medical officer", "consultant", "attending", "surgeon", "physician", "fellow", "practitioner", "specialist", "intern"]
            for line in lines:
                if any(re.search(rf"\b{re.escape(ds)}\b", line, re.IGNORECASE) for ds in designation_keywords):
                    if len(line) < 80 and not any(kw in line.lower() for kw in ["college", "university", "school"]):
                        current_designation = line
                        break
                        
        if not current_hospital:
            hospital_keywords = ["hospital", "clinic", "medical center", "healthcare", "nursing home", "health system", "pvt", "ltd"]
            for line in lines:
                if any(re.search(rf"\b{re.escape(hp)}\b", line, re.IGNORECASE) for hp in hospital_keywords):
                    if len(line) < 80:
                        current_hospital = line
                        break

        # Registration Number regex (State/MCI Medical Council)
        reg_number = None
        reg_match = re.search(
            r'\b(?:registration|reg|license|lic|council)\.?\s*(?:no|number)?[:.\s\-#]+([A-Z0-9\-/]{4,15})\b', 
            normalized_text, 
            re.IGNORECASE
        )
        if reg_match:
            reg_number = reg_match.group(1)

        experience = ExperienceSchema(
            specialization=experience_spec,
            experience_years=exp_years,
            current_designation=current_designation,
            current_hospital=current_hospital,
            registration_number=reg_number,
            work_history=self._parse_work_history(experience_text)
        )

        # 7. Extract Skills
        skills = MedicalSkillExtractorService.extract_skills(text)

        # 8. Extract Certifications
        certifications = []
        for cert in CERTIFICATIONS:
            if re.search(rf"\b{re.escape(cert)}\b", normalized_text, re.IGNORECASE):
                certifications.append(cert)

        # 9. Extract Languages
        languages = []
        for lang in LANGUAGES:
            if re.search(rf"\b{re.escape(lang)}\b", normalized_text, re.IGNORECASE):
                languages.append(lang)

        # Build Response
        return ResumeParserResponseSchema(
            personal_info=personal_info,
            education=unique_education,
            experience=experience,
            skills=skills,
            certifications=certifications,
            languages=languages
        )
