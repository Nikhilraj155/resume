import os
import re
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from app.schemas.resume import (
    ResumeParserResponseSchema,
    PersonalInfoSchema,
    EducationItemSchema,
    ExperienceSchema,
    WorkHistoryItemSchema,
    CertificationSchema,
    LanguageSchema,
    SkillCategorySchema,
    MetadataSchema,
)
from app.services.pdf_extractor import PDFExtractorService
from app.services.spacy_parser import SpacyParserService
from app.services.medical_skill_extractor import MedicalSkillExtractorService
from app.services.experience_calculator import ExperienceCalculatorService

from app.constants.medical_constants import (
    CERTIFICATION_KEYWORDS,
    LANGUAGES,
    LANGUAGE_PROFICIENCY_KEYWORDS,
    DEGREE_KEYWORDS,
    SPECIALIZATION_KEYWORDS,
    SKILL_SECTION_HEADERS,
    POSTGRADUATE_DEGREES,
    GRADUATE_DEGREES,
    SCHOOL_DEGREES,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

KNOWN_COUNTRIES = {"india", "united states", "usa", "united kingdom", "uk", "canada", "australia", "germany", "uae", "singapore"}
KNOWN_STATES = {
    "maharashtra", "massachusetts", "california", "texas", "new york", "tamil nadu",
    "karnataka", "delhi", "gujarat", "florida", "illinois", "pennsylvania", "ohio",
    "kerala", "telangana", "andhra pradesh", "west bengal",
}
KNOWN_CITIES = {"bengaluru", "bangalore", "mumbai", "pune", "delhi", "new delhi", "hyderabad", "chennai", "kolkata", "ahmedabad", "jaipur", "lucknow", "noida", "gurgaon", "chandigarh", "indore", "bhopal", "surat", "kochi", "goa", "nagpur", "patna", "thane", "agra", "varanasi", "nashik", "meerut", "rajkot", "vadodara", "vijayawada", "mangalore", "mysore"}

_DATE_RANGE_PATTERN = re.compile(
    r'((?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?'
    r'|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)'
    r'\s+(?:19|20)\d{2}|(?:19|20)\d{2})'
    r'\s*[-–—]\s*'
    r'((?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?'
    r'|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)'
    r'\s+(?:19|20)\d{2}|(?:19|20)\d{2}|present|current|now|till date|ongoing)',
    re.IGNORECASE
)

_EDU_YEAR_RANGE = re.compile(r'(?P<start>(?:19|20)\d{2})\s*[-–—]+\s*(?P<end>(?:19|20)\d{2})')
_GPA_PATTERN = re.compile(r'(?:GPA|gpa|grade|score)\s*[:.]?\s*([\d.]+(?:/\d{1,2})?)')
_PERCENTAGE_PATTERN = re.compile(r'(\d{2}\.\d)%')
_BOARD_PATTERN = re.compile(r'\b(CBSE|ICSE|IB|IGCSE|SSC|HSC|State Board)\b', re.IGNORECASE)
_LINKEDIN_PATTERN = re.compile(r'(?:linkedin|linked-in)[:\s]*(?:https?://(?:www\.)?linkedin\.com/in/)?([\w-]+)', re.IGNORECASE)
_CERT_YEAR_PATTERN = re.compile(r'(?<!\d)((?:19|20)\d{2})(?!\d)')
_LANG_PROF_PATTERN = re.compile(r'\((\w+)\)')
_HYPHEN_WRAP = re.compile(r'(\w)-\s*\n\s*(\w)')
_CONTROL_CHARS = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x80-\x9f]')


def _clean_location_string(raw: str) -> str:
    if not raw:
        return raw
    cleaned = raw
    cleaned = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '', cleaned)
    cleaned = re.sub(r'\+?\d{1,4}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4,6}', '', cleaned)
    cleaned = re.sub(r'https?://\S+', '', cleaned)
    cleaned = re.sub(r'www\.\S+', '', cleaned)
    cleaned = re.sub(r'[#@]\w+', '', cleaned)
    if '|' in cleaned:
        segments = [s.strip() for s in cleaned.split('|') if s.strip()]
        valid_segments = [s for s in segments if not any(c in s for c in ['@', '#', '+', '.com', '.in'])]
        if valid_segments:
            cleaned = valid_segments[-1]
        else:
            cleaned = segments[-1]
    words = re.findall(r'[A-Za-z]+', cleaned)
    for word in words:
        if word.lower() in KNOWN_CITIES:
            return word.title()
    for word in reversed(words):
        if len(word) >= 3:
            return word.title()
    for word in words:
        if len(word) >= 2:
            return word.title()
    return cleaned.strip()


def _get_education_level(degree: str) -> Optional[str]:
    if not degree:
        return None
    deg_upper = degree.strip().upper()
    for pg in POSTGRADUATE_DEGREES:
        if deg_upper.startswith(pg.upper()) or pg.upper().startswith(deg_upper):
            return "postgraduate"
    for g in GRADUATE_DEGREES:
        if deg_upper.startswith(g.upper()) or g.upper().startswith(deg_upper):
            return "graduate"
    for sc in SCHOOL_DEGREES:
        if deg_upper.startswith(sc.upper()) or sc.upper().startswith(deg_upper):
            return "school"
    return "graduate"


def _has_degree_keyword(text: str, exclude: Optional[str] = None) -> bool:
    for deg in DEGREE_KEYWORDS:
        if exclude and deg.lower() == exclude.lower():
            continue
        if re.search(rf"\b{re.escape(deg)}\b", text, re.IGNORECASE):
            return True
    return False


class ResumeParserService:
    def __init__(self):
        self.spacy_parser = SpacyParserService()
        self.medical_skill_extractor = MedicalSkillExtractorService()

    def _parse_work_history(self, experience_text: str) -> list:
        if not experience_text.strip():
            return []

        EMPLOYER_KEYWORDS = ["hospital", "clinic", "medical", "centre", "center", "healthcare",
                             "health", "nursing", "institute", "foundation", "pvt", "ltd", "college"]

        lines = [l.strip() for l in experience_text.split('\n') if l.strip()]

        blocks: list[dict] = []
        in_bullet = False
        current_responsibilities = []

        for line in lines:
            is_bullet_start = line.startswith('-') or line.startswith('•') or line.startswith('▪') or line.startswith('–')
            dr_match = _DATE_RANGE_PATTERN.search(line)

            if is_bullet_start and not dr_match:
                in_bullet = True
                bullet_text = re.sub(r'^[•▪–\-]\s*', '', line).strip()
                if bullet_text:
                    current_responsibilities.append(bullet_text)
                continue

            if in_bullet and not dr_match:
                if any(kw in line.lower() for kw in EMPLOYER_KEYWORDS) and ',' in line:
                    in_bullet = False
                    if blocks:
                        p = [x.strip() for x in line.split(',')]
                        blocks[-1]['employer'] = p[0]
                    continue
                current_responsibilities.append(line)
                continue

            if dr_match:
                if current_responsibilities and blocks:
                    blocks[-1]['responsibilities'] = current_responsibilities
                current_responsibilities = []
                in_bullet = False

                before_date = line[:dr_match.start()].strip().rstrip('(').strip()

                employer = None
                designation = before_date
                sep = re.search(r'\s[-–]\s', before_date)
                if sep:
                    left_part = before_date[:sep.start()].strip()
                    right_part = before_date[sep.end():].strip()
                    if any(kw in right_part.lower() for kw in EMPLOYER_KEYWORDS):
                        designation = left_part
                        employer = right_part.split(',')[0].strip()
                    elif any(kw in left_part.lower() for kw in EMPLOYER_KEYWORDS):
                        designation = right_part
                        employer = left_part.split(',')[0].strip()

                blocks.append({
                    'designation': designation.rstrip(',').strip() or None,
                    'start_date': dr_match.group(1).strip(),
                    'end_date': dr_match.group(2).strip(),
                    'employer': employer,
                    'responsibilities': [],
                })
                continue

            if in_bullet:
                continue

            if blocks and blocks[-1]['employer'] is None:
                if any(kw in line.lower() for kw in EMPLOYER_KEYWORDS):
                    parts = [p.strip() for p in line.split(',')]
                    blocks[-1]['employer'] = parts[0] if len(parts) >= 3 else line

        if current_responsibilities and blocks:
            blocks[-1]['responsibilities'] = current_responsibilities

        result = []
        for b in blocks:
            wh = WorkHistoryItemSchema(
                designation=b['designation'],
                employer=b['employer'],
                start_date=b['start_date'],
                end_date=b['end_date'],
                responsibilities=b['responsibilities'],
            )
            result.append(wh)

        return result

    def _segment_text(self, text: str) -> Dict[str, str]:
        lines = [line.strip() for line in text.split("\n")]
        sections = {
            "header": [],
            "summary": [],
            "experience": [],
            "education": [],
            "skills": [],
            "certifications": [],
            "projects": [],
            "other": [],
        }

        current_section = "header"

        for line in lines:
            if not line:
                continue
            line_lower = line.lower().strip()
            cleaned_header = re.sub(r'[^\w\s]', '', line_lower).strip()

            if any(h == cleaned_header or cleaned_header.startswith(h) for h in ["professional summary", "summary", "profile", "about me", "career objective", "objective"]) and len(cleaned_header) < 40:
                current_section = "summary"
                continue
            elif any(h == cleaned_header or cleaned_header.startswith(h) for h in ["work experience", "experience", "employment", "professional history", "career history", "work history"]) and len(cleaned_header) < 40:
                current_section = "experience"
                continue
            elif any(h == cleaned_header or cleaned_header.startswith(h) for h in ["education", "academic", "qualifications", "credentials", "academic background"]) and len(cleaned_header) < 40:
                current_section = "education"
                continue
            elif any(h == cleaned_header or cleaned_header.startswith(h) for h in ["technical skills", "skills", "clinical skills", "key skills", "professional skills", "expertise"]) and len(cleaned_header) < 40:
                current_section = "skills"
                continue
            elif any(h == cleaned_header or cleaned_header.startswith(h) for h in ["certifications", "licenses", "certifications & memberships", "certifications & licenses", "credentials", "courses"]) and len(cleaned_header) < 40:
                current_section = "certifications"
                continue
            elif any(h == cleaned_header or cleaned_header.startswith(h) for h in ["projects", "academic projects", "key projects", "projects during internship"]) and len(cleaned_header) < 40:
                current_section = "projects"
                continue

            sections[current_section].append(line)

        return {k: "\n".join(v) for k, v in sections.items()}

    def _parse_profile_summary(self, sections: Dict[str, str]) -> Optional[str]:
        summary_text = sections.get("summary", "").strip()
        if summary_text:
            lines = [l for l in summary_text.split("\n") if l.strip()]
            if lines:
                return " ".join(lines[:5])
        return None

    def _parse_linkedin(self, text: str, header_lines: List[str]) -> Optional[str]:
        for line in header_lines:
            m = _LINKEDIN_PATTERN.search(line)
            if m:
                handle = m.group(1).strip()
                if handle:
                    return handle
        m = _LINKEDIN_PATTERN.search(text)
        if m:
            return m.group(1).strip()
        return None

    def _parse_education(self, sections: Dict[str, str], entities: Dict) -> List[EducationItemSchema]:
        items = []
        education_text = sections.get("education", "")
        if not education_text:
            return items

        edu_lines = [line.strip() for line in education_text.split("\n") if line.strip()]
        for idx, line in enumerate(edu_lines):
            found_degree = None
            for deg in DEGREE_KEYWORDS:
                if re.search(rf"\b{re.escape(deg)}\b", line, re.IGNORECASE):
                    found_degree = deg
                    break

            if not found_degree:
                continue

            context_lines = [line]
            for i in range(idx + 1, min(idx + 3, len(edu_lines))):
                cl = edu_lines[i]
                if _has_degree_keyword(cl, exclude=found_degree):
                    break
                context_lines.append(cl)
            context_text = " ".join(context_lines)

            start_year = None
            end_year = None
            yr_pair = _EDU_YEAR_RANGE.search(context_text)
            if yr_pair:
                start_year = yr_pair.group("start")
                end_year = yr_pair.group("end")
            else:
                years_found = re.findall(r'\b(19\d{2}|20\d{2})\b', context_text)
                years = sorted(set(int(y) for y in years_found))
                if len(years) >= 2:
                    start_year = str(years[0])
                    end_year = str(years[1])
                elif len(years) == 1:
                    end_year = str(years[0])

            gpa = None
            gpa_m = _GPA_PATTERN.search(context_text)
            if gpa_m:
                gpa = gpa_m.group(1)

            percentage = None
            pct_m = _PERCENTAGE_PATTERN.search(context_text)
            if pct_m:
                percentage = pct_m.group(1)

            board = None
            board_m = _BOARD_PATTERN.search(context_text)
            if board_m:
                board = board_m.group(1)

            college = None
            university = None
            specialization = None

            after_year = context_text
            if yr_pair:
                after_year = context_text[yr_pair.end():].strip()
            else:
                after_year = re.sub(r'^\s*(?:19|20)\d{2}\s*[-–—]+\s*(?:19|20)\d{2}\s*', '', after_year).strip()
                after_year = re.sub(r'^\s*(?:19|20)\d{2}\s*', '', after_year).strip()

            after_degree = re.sub(rf'^\s*{re.escape(found_degree)}\s*[-–—]?\s*', '', after_year, flags=re.IGNORECASE).strip()

            if ',' in after_degree:
                parts = [p.strip() for p in after_degree.split(',')]
                before_comma = parts[0]
                for i, p in enumerate(parts):
                    if any(kw in p.lower() for kw in ["college", "university", "school", "institute", "hospital", "academy"]):
                        candidate = p
                        candidate = _GPA_PATTERN.sub('', candidate).strip()
                        candidate = _PERCENTAGE_PATTERN.sub('', candidate).strip()
                        candidate = _BOARD_PATTERN.sub('', candidate).strip()
                        candidate = re.sub(r'\s+', ' ', candidate).strip().rstrip(',').strip()
                        candidate = re.sub(r'\s*\(\s*\)\s*', '', candidate).strip()
                        candidate = re.sub(r'\s*\((?:PCB|PCM|CBSE|ICSE|IB|IGCSE|SSC|HSC|State\s*Board|Biology|Maths|Science|Commerce|Arts|Humanities)[^)]*\)\s*', ' ', candidate, flags=re.IGNORECASE).strip()
                        candidate = re.sub(r'\s+', ' ', candidate).strip()
                        for spec_kw in SPECIALIZATION_KEYWORDS:
                            candidate = re.sub(rf'^{re.escape(spec_kw)}\s*', '', candidate, flags=re.IGNORECASE).strip()
                        college = candidate
                        if "university" in candidate.lower():
                            university = college
                        break
            else:
                before_comma = after_degree.strip()

            if not college:
                for cl in context_lines:
                    if any(kw in cl.lower() for kw in ["college", "university", "school", "institute", "hospital", "academy"]):
                        c_clean = cl
                        c_clean = re.sub(rf"\b{re.escape(found_degree)}\b", "", c_clean, flags=re.IGNORECASE).strip()
                        c_clean = _GPA_PATTERN.sub('', c_clean).strip()
                        c_clean = _PERCENTAGE_PATTERN.sub('', c_clean).strip()
                        c_clean = _BOARD_PATTERN.sub('', c_clean).strip()
                        c_clean = re.sub(r'^[–\-|,\s]+', '', c_clean).strip()
                        c_clean = re.sub(r'\s*\(\s*\)\s*', '', c_clean).strip()
                        c_clean = re.sub(r'\s*\((?:PCB|PCM|CBSE|ICSE|IB|IGCSE|SSC|HSC|State\s*Board|Biology|Maths|Science|Commerce|Arts|Humanities)[^)]*\)\s*', ' ', c_clean, flags=re.IGNORECASE).strip()
                        c_clean = re.sub(r'\s+', ' ', c_clean).strip()
                        for spec_kw in SPECIALIZATION_KEYWORDS:
                            c_clean = re.sub(rf'^{re.escape(spec_kw)}\s*', '', c_clean, flags=re.IGNORECASE).strip()
                        if c_clean and len(c_clean) > 3:
                            college = c_clean
                            if "university" in college.lower():
                                university = college
                        break

            if not college:
                for org in entities.get("ORG", []):
                    if org in context_text and any(kw in org.lower() for kw in ["college", "university", "school", "institute", "hospital", "academy"]):
                        college = org
                        break

            spec_text = before_comma if 'before_comma' in dir() else after_degree
            if ',' in after_degree:
                spec_text = after_degree.split(',')[0].strip()
            else:
                spec_text = after_degree.strip()
            for spec_kw in SPECIALIZATION_KEYWORDS:
                if re.search(rf"\b{re.escape(spec_kw)}\b", spec_text, re.IGNORECASE):
                    specialization = spec_kw
                    break
            if not specialization:
                for spec_kw in SPECIALIZATION_KEYWORDS:
                    if re.search(rf"\b{re.escape(spec_kw)}\b", context_text, re.IGNORECASE):
                        specialization = spec_kw
                        break

            level = _get_education_level(found_degree)

            items.append(EducationItemSchema(
                degree=found_degree,
                specialization=specialization,
                college=college,
                university=university,
                start_year=start_year,
                end_year=end_year,
                gpa=gpa,
                percentage=percentage,
                board=board,
                level=level,
            ))

        seen = set()
        unique = []
        for edu in items:
            key = (edu.degree.lower() if edu.degree else "", edu.college.lower() if edu.college else "")
            if key not in seen:
                seen.add(key)
                unique.append(edu)
        return unique

    def _parse_categorized_skills_and_languages(self, sections: Dict[str, str]) -> Tuple[SkillCategorySchema, List[LanguageSchema]]:
        categories = {"clinical": [], "technical": [], "soft_skills": []}
        languages = []

        skills_text = sections.get("skills", "")
        if not skills_text.strip():
            return SkillCategorySchema(), languages

        lines = skills_text.split("\n")
        current_category = None
        seen_languages_header = False

        for i, line in enumerate(lines):
            line_lower = line.lower().strip()
            if not line_lower:
                continue

            if "last updated" in line_lower or "updated on" in line_lower or "updated:" in line_lower:
                continue

            if line_lower.startswith("languages") or line_lower == "languages":
                seen_languages_header = True
                current_category = None
                content = re.sub(r'^languages\s*', '', line, flags=re.IGNORECASE).strip()
                if content:
                    self._extract_languages_from_text(content, languages)
                continue

            if seen_languages_header:
                if any(line_lower.startswith(h) for h in SKILL_SECTION_HEADERS["soft_skills"]):
                    seen_languages_header = False
                    current_category = "soft_skills"
                    content = re.sub(r'^soft skills\s*', '', line, flags=re.IGNORECASE).strip()
                    content = re.sub(r'^soft\s*', '', content, flags=re.IGNORECASE).strip()
                    if content:
                        categories["soft_skills"].extend(self._split_skills(content))
                    continue
                self._extract_languages_from_text(line, languages)
                continue

            found_cat = None
            for cat, headers in SKILL_SECTION_HEADERS.items():
                for h in headers:
                    if line_lower.startswith(h) or line_lower == h:
                        found_cat = cat
                        break
                if found_cat:
                    break

            if found_cat:
                current_category = found_cat
                content = re.sub(rf'^{re.escape(h)}\s*', '', line, flags=re.IGNORECASE) if found_cat else line
                content = re.sub(r'^[:\s]*', '', content).strip()
                if content:
                    categories[current_category].extend(self._split_skills(content))
                continue

            if current_category and line:
                categories[current_category].extend(self._split_skills(line))

        for cat in categories:
            cleaned = []
            for skill in categories[cat]:
                skill = skill.strip().rstrip(',').strip()
                skill = re.sub(r'\s+', ' ', skill)
                if skill and len(skill) > 1:
                    cleaned.append(skill)
            categories[cat] = cleaned

        return SkillCategorySchema(
            clinical=categories["clinical"],
            technical=categories["technical"],
            soft_skills=categories["soft_skills"],
        ), languages

    def _split_skills(self, text: str) -> List[str]:
        if not text:
            return []
        text = re.sub(r'^[•▪–\-]\s*', '', text).strip()
        parts = [s.strip() for s in re.split(r'[,;]', text) if s.strip()]
        return parts

    def _extract_languages_from_text(self, text: str, languages: List):
        parts = [p.strip() for p in re.split(r'[,;]', text) if p.strip()]
        for part in parts:
            part = re.sub(r'^[•▪–\-]\s*', '', part).strip()
            part = re.sub(r'\s+', ' ', part).strip()
            lang_name = part
            proficiency = None
            prof_m = _LANG_PROF_PATTERN.search(part)
            if prof_m:
                prof_text = prof_m.group(1).lower()
                proficiency = LANGUAGE_PROFICIENCY_KEYWORDS.get(prof_text, prof_text.title())
                lang_name = _LANG_PROF_PATTERN.sub('', part).strip()
            lang_name = lang_name.strip().rstrip(',').strip()
            if lang_name and len(lang_name) > 1:
                languages.append(LanguageSchema(
                    language=lang_name,
                    proficiency=proficiency,
                ))

    def _parse_structured_certifications(self, sections: Dict[str, str]) -> List[CertificationSchema]:
        certs = []
        cert_text = sections.get("certifications", "")
        if not cert_text.strip():
            return certs

        lines = [l.strip() for l in cert_text.split("\n") if l.strip()]
        for line in lines:
            line = re.sub(r'^[•▪▸–\-]\s*', '', line).strip()
            if not line:
                continue

            if re.match(r'^\(?(?:GPA|gpa|grade|score)[:\s]*[\d./]+\%?\)?$', line):
                continue
            if re.match(r'^\(\d{2}\.\d%\)$', line):
                continue
            if re.match(r'^[\d./]+%\)?$', line.strip('()')):
                continue
            if re.match(r'^\([\w\s]+:\s*[\d./]+\)$', line) and any(kw in line.lower() for kw in ['gpa', 'grade', 'score', 'percentage']):
                continue

            name = line
            issuer = None
            year = None
            abbreviation = None

            abbr_m = re.search(r'\(([A-Z]+)\)', line[:len(line)//2])
            if abbr_m:
                abbreviation = abbr_m.group(1)

            year_m = _CERT_YEAR_PATTERN.search(line)
            if year_m:
                year = int(year_m.group(1))

            name_no_year = _CERT_YEAR_PATTERN.sub('', line).strip() if year_m else line
            name_no_year = name_no_year.strip().rstrip(',').strip()

            sep_match = re.search(r'\s[–\-]\s', name_no_year)
            if sep_match:
                name_part = name_no_year[:sep_match.start()].strip()
                issuer_part = name_no_year[sep_match.end():].strip()
                if issuer_part and len(issuer_part) > 3 and not issuer_part.startswith('('):
                    name = name_part
                    issuer = issuer_part

            certs.append(CertificationSchema(
                name=name,
                abbreviation=abbreviation,
                issuer=issuer,
                year=year,
            ))

        return certs

    def parse_resume(self, filepath: str) -> ResumeParserResponseSchema:
        logger.info(f"Starting open-source parse execution for: {filepath}")

        ext = os.path.splitext(filepath)[1].lower()
        if ext == '.docx':
            text = PDFExtractorService.extract_text_from_docx(filepath)
        else:
            text = PDFExtractorService.extract_text(filepath)
        text = _HYPHEN_WRAP.sub(r'\1\2', text)
        text = _CONTROL_CHARS.sub('', text)
        normalized_text = " ".join(text.split())
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        sections = self._segment_text(text)

        prefix, first_name, last_name = self.spacy_parser.extract_name_details(text)
        entities = self.spacy_parser.extract_entities(text)

        city, state, country = None, None, None
        header_text = sections.get("header", "")
        header_lines = []
        if header_text:
            header_lines = [line.strip() for line in header_text.split("\n") if line.strip()]

        if header_lines:
            for line in header_lines[1:4]:
                parts = [p.strip() for p in line.split(",") if p.strip()]
                if len(parts) >= 2:
                    raw_city = parts[0].strip()
                    raw_state_or_country = parts[1].strip()

                    if any(re.search(rf'\b{re.escape(d)}\b', raw_city, re.IGNORECASE) for d in DEGREE_KEYWORDS):
                        continue
                    if any(re.search(rf'\b{re.escape(d)}\b', raw_state_or_country, re.IGNORECASE) for d in DEGREE_KEYWORDS):
                        continue

                    if re.match(r'^[A-Za-z\s]+$', raw_city):
                        city = raw_city.title()
                    else:
                        cleaned = _clean_location_string(raw_city)
                        if cleaned and len(cleaned) >= 2:
                            city = cleaned
                        else:
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

        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', normalized_text)
        email = email_match.group(0) if email_match else None

        phone_match = re.search(r'(\+?\d{1,4}[-.\s]?)?(\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4,6}', normalized_text)
        phone = phone_match.group(0) if phone_match else None

        profile_summary = self._parse_profile_summary(sections)
        linkedin = self._parse_linkedin(text, header_lines)

        personal_info = PersonalInfoSchema(
            prefix=prefix,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            city=city,
            state=state,
            country=country,
            linkedin=linkedin,
            profile_summary=profile_summary,
        )

        education_items = self._parse_education(sections, entities)

        experience_text = sections.get("experience", "")
        if experience_text:
            exp_years = ExperienceCalculatorService.calculate_experience(experience_text)
        else:
            exp_years = ExperienceCalculatorService.calculate_experience(text)

        experience_spec = None
        for spec_kw in SPECIALIZATION_KEYWORDS:
            if re.search(rf"\b{re.escape(spec_kw)}\b", normalized_text, re.IGNORECASE):
                experience_spec = spec_kw
                break

        current_designation = None
        current_hospital = None
        current_department = None

        if experience_text:
            exp_lines = [line.strip() for line in experience_text.split("\n") if line.strip()]
            if exp_lines:
                first_exp_line = exp_lines[0]
                EMPLOYER_KEYWORDS = ["hospital", "clinic", "medical", "centre", "center", "healthcare",
                                     "health", "nursing", "institute", "foundation", "pvt", "ltd", "college"]

                dr_match = _DATE_RANGE_PATTERN.search(first_exp_line)
                if dr_match:
                    title_part = first_exp_line[:dr_match.start()].strip()
                else:
                    title_part = first_exp_line

                # Handle case where first line is just a date range (title on next line)
                if not title_part and len(exp_lines) > 1:
                    designation_line = exp_lines[1]
                    current_designation = designation_line.rstrip(',').strip()
                    # Use work history to find most recent employer
                    wh = self._parse_work_history(experience_text)
                    if wh and wh[0].employer:
                        current_hospital = wh[0].employer.split(',')[0].strip()
                    else:
                        for exp_line in exp_lines[2:]:
                            if any(kw in exp_line.lower() for kw in EMPLOYER_KEYWORDS):
                                if exp_line.startswith('-') or exp_line.startswith('•') or exp_line.startswith('▪') or exp_line.startswith('–'):
                                    continue
                                parts2 = [p.strip() for p in exp_line.split(",")]
                                current_hospital = parts2[0]
                                break
                else:
                    parts = []
                    if "|" in title_part:
                        parts = [p.strip() for p in title_part.split("|")]
                    elif " at " in title_part.lower():
                        parts = [p.strip() for p in re.split(r'\s+at\s+', title_part, flags=re.IGNORECASE)]
                    elif " - " in title_part:
                        parts = [p.strip() for p in title_part.split(" - ")]
                    elif " – " in title_part:
                        parts = [p.strip() for p in title_part.split(" – ")]
                    elif "," in title_part:
                        parts = [p.strip() for p in title_part.split(",")]

                    if len(parts) >= 2:
                        current_designation = parts[0]
                        candidate_hospital = parts[1]
                        if "," in candidate_hospital:
                            candidate_hospital = candidate_hospital.split(",")[0].strip()
                        # Check if the "hospital" is actually a department name
                        if candidate_hospital.lower().startswith("department of"):
                            current_department = candidate_hospital
                            current_designation = title_part.rstrip(',').strip()
                            current_hospital = None
                        elif any(spec.lower() == candidate_hospital.lower().strip() for spec in SPECIALIZATION_KEYWORDS):
                            current_hospital = None
                        else:
                            current_hospital = candidate_hospital
                    else:
                        current_designation = title_part

                if not current_hospital:
                    wh = self._parse_work_history(experience_text)
                    if wh and wh[0].employer:
                        current_hospital = wh[0].employer.split(',')[0].strip()
                    else:
                        for exp_line in exp_lines[1:]:
                            if exp_line.startswith('-') or exp_line.startswith('•') or exp_line.startswith('▪') or exp_line.startswith('–'):
                                continue
                            if any(kw in exp_line.lower() for kw in EMPLOYER_KEYWORDS):
                                parts2 = [p.strip() for p in exp_line.split(",")]
                                current_hospital = parts2[0]
                                break

        if not current_designation:
            designation_keywords = ["resident", "medical officer", "consultant", "attending", "surgeon", "physician", "fellow", "practitioner", "specialist", "intern"]
            for line in lines:
                if any(re.search(rf"\b{re.escape(ds)}\b", line, re.IGNORECASE) for ds in designation_keywords):
                    if len(line) < 80 and not any(kw in line.lower() for kw in ["college", "university", "school"]):
                        dr_m = _DATE_RANGE_PATTERN.search(line)
                        current_designation = line[:dr_m.start()].strip() if dr_m else line
                        break

        if not current_hospital:
            hospital_keywords = ["hospital", "clinic", "medical center", "healthcare", "nursing home", "health system", "pvt", "ltd"]
            for line in lines:
                if any(re.search(rf"\b{re.escape(hp)}\b", line, re.IGNORECASE) for hp in hospital_keywords):
                    if len(line) < 80:
                        current_hospital = line
                        break

        reg_number = None
        reg_match = re.search(
            r'\b(?:registration|reg|license|lic|council)\.?\s*(?:no|number)?[:.\s\-#]+([A-Z0-9\-/]{4,15})\b',
            normalized_text, re.IGNORECASE
        )
        if reg_match:
            reg_number = reg_match.group(1)

        reg_council = None
        reg_year = None
        council_match = re.search(
            r'(?:registered|registration)\s+(?:medical|dental)\s+(?:practitioner|doctor)\s*[-–]\s*([A-Za-z\s]+?)\s*(?:council|board|authority)',
            normalized_text, re.IGNORECASE
        )
        if council_match:
            reg_council = council_match.group(1).strip() + " Council"

        council_year_match = re.search(
            r'(?:registered|registration)\s+(?:medical|dental)\s+(?:practitioner|doctor).*?((?:19|20)\d{2})',
            normalized_text, re.IGNORECASE
        )
        if council_year_match:
            reg_year = int(council_year_match.group(1))

        experience = ExperienceSchema(
            specialization=experience_spec,
            experience_years=exp_years,
            current_designation=current_designation,
            current_hospital=current_hospital,
            current_department=current_department,
            registration_number=reg_number,
            registration_council=reg_council,
            registration_year=reg_year,
            work_history=self._parse_work_history(experience_text),
        )

        skills, languages = self._parse_categorized_skills_and_languages(sections)
        certifications = self._parse_structured_certifications(sections)

        metadata = MetadataSchema(
            parsed_at=datetime.utcnow().isoformat(),
            parser_version="2.0",
            file_type=ext.lstrip('.') if ext else None,
            last_updated=None,
        )

        lu_match = re.search(r'(?:last\s+updated|updated|last\s+modified)\s*[:]?\s*(.+?)$', normalized_text, re.IGNORECASE | re.MULTILINE)
        if lu_match:
            metadata.last_updated = lu_match.group(1).strip()

        return ResumeParserResponseSchema(
            personal_info=personal_info,
            education=education_items,
            experience=experience,
            skills=skills,
            certifications=certifications,
            languages=languages,
            metadata=metadata,
        )
