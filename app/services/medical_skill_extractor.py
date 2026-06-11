import re
from typing import List
from app.constants.medical_constants import MEDICAL_SKILLS

class MedicalSkillExtractorService:
    @staticmethod
    def extract_skills(text: str) -> List[str]:
        """
        Extracts medical and clinical skills from the text based on a predefined list.
        Uses boundary checking to prevent partial matches.
        """
        extracted_skills = []
        # Normalize text spacing to ensure clean regex matching
        normalized_text = " ".join(text.split())
        
        for skill in MEDICAL_SKILLS:
            # Handle special characters (e.g. C++, ICU, CT Scan)
            # Use raw word boundary regex for letters/numbers
            pattern = rf"\b{re.escape(skill)}\b"
            
            # If the skill starts or ends with non-word character (like C++), handle it
            if not skill[0].isalnum():
                pattern = rf"{re.escape(skill)}\b"
            if not skill[-1].isalnum():
                pattern = rf"\b{re.escape(skill)}"
                
            if re.search(pattern, normalized_text, re.IGNORECASE):
                extracted_skills.append(skill)
                
        return extracted_skills
