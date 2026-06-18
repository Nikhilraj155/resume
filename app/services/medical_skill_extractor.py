import re
from typing import List, Dict
from app.constants.medical_constants import MEDICAL_SKILLS, SKILL_SECTION_HEADERS


class MedicalSkillExtractorService:
    @staticmethod
    def extract_skills(text: str) -> List[str]:
        normalized_text = " ".join(text.split())
        extracted_skills = []
        for skill in MEDICAL_SKILLS:
            if not skill[0].isalnum():
                pattern = rf"{re.escape(skill)}\b"
            elif not skill[-1].isalnum():
                pattern = rf"\b{re.escape(skill)}"
            else:
                pattern = rf"\b{re.escape(skill)}\b"
            if re.search(pattern, normalized_text, re.IGNORECASE):
                extracted_skills.append(skill)
        return extracted_skills

    @staticmethod
    def extract_categorized_skills(skills_text: str) -> Dict[str, List[str]]:
        categories = {
            "clinical": [],
            "technical": [],
            "soft_skills": [],
        }
        if not skills_text.strip():
            return categories

        current_category = "clinical"
        lines = skills_text.split("\n")

        for line in lines:
            line_lower = line.lower().strip()
            if not line_lower:
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
                continue

        return categories
