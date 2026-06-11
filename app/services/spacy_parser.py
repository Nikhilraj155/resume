import spacy
import re
from typing import Dict, List, Tuple, Optional
from app.utils.logger import get_logger

logger = get_logger(__name__)

DR_PREFIX_PATTERN = re.compile(r"^(dr|doctor)\.?\s+", re.IGNORECASE)
NAME_PREFIX_CLEANUP_PATTERN = re.compile(r"^(?:dr|doctor|mr|mrs|ms|prof)\.?\s+", re.IGNORECASE)
NON_NAME_WORDS = {
    "certified",
    "doctor",
    "physician",
    "resident",
    "consultant",
    "surgeon",
    "specialist",
    "intern",
    "fellow",
    "medical",
    "senior",
    "junior",
}

class SpacyParserService:
    _nlp = None

    def __init__(self):
        if SpacyParserService._nlp is None:
            logger.info("Loading spaCy model 'en_core_web_sm'...")
            try:
                SpacyParserService._nlp = spacy.load("en_core_web_sm")
                logger.info("spaCy model loaded successfully.")
            except Exception as e:
                logger.error(f"Failed to load spaCy model 'en_core_web_sm': {str(e)}")
                raise RuntimeError("spaCy model 'en_core_web_sm' is not installed or available.")

    def parse_text(self, text: str) -> spacy.tokens.Doc:
        """Processes raw text through the spaCy pipeline."""
        return SpacyParserService._nlp(text)

    @staticmethod
    def _extract_dr_prefix(value: str) -> Optional[str]:
        return "Dr" if DR_PREFIX_PATTERN.match(value.strip()) else None

    @staticmethod
    def _is_likely_name_words(words: List[str]) -> bool:
        if not 2 <= len(words) <= 3:
            return False
        if not all(word.isalpha() and word[0].isupper() for word in words):
            return False
        lowered_words = {word.lower() for word in words}
        return not lowered_words.intersection(NON_NAME_WORDS)

    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """
        Extracts PERSON, ORG, and GPE (locations) entities from the text.
        """
        doc = self.parse_text(text)
        entities = {
            "PERSON": [],
            "ORG": [],
            "GPE": []
        }
        for ent in doc.ents:
            if ent.label_ in entities:
                cleaned_text = ent.text.strip().replace("\n", " ")
                if cleaned_text and cleaned_text not in entities[ent.label_]:
                    entities[ent.label_].append(cleaned_text)
        return entities

    def extract_name_details(self, text: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Extracts prefix, first name, and last name.
        Prioritizes the line-based heuristic on the top of the resume,
        falling back to spaCy PERSON entities if unsuccessful.
        """
        # 1. Line-based heuristic (most reliable for resumes)
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        # 1a. Handle resumes where the first and last name are stacked on separate lines.
        for idx in range(min(len(lines) - 1, 4)):
            combined_words = [lines[idx], lines[idx + 1]]
            if self._is_likely_name_words(combined_words):
                first_name = combined_words[0].title()
                last_name = combined_words[1].title()
                logger.info(f"Name extracted via stacked-line heuristic: prefix=None, first_name={first_name}, last_name={last_name}")
                return None, first_name, last_name

        for line in lines[:5]:
            prefix = self._extract_dr_prefix(line)
            # Clean prefix titles from the name line while only persisting Dr
            cleaned_line = NAME_PREFIX_CLEANUP_PATTERN.sub("", line).strip()
            # Clean formatting characters
            cleaned_line = re.sub(r'[^\w\s]', ' ', cleaned_line).strip()
            
            # Skip lines containing email, website, or digits (phone/address)
            if "@" in line or "http" in line or "www." in line or any(char.isdigit() for char in line):
                continue
                
            # Skip common resume headers
            if any(h in line.lower() for h in ["resume", "cv", "curriculum", "portfolio", "profile", "objective"]):
                continue
                
            words = cleaned_line.split()
            # Candidate names are typically 2 to 3 capitalized words
            if self._is_likely_name_words(words):
                first_name = words[0].title()
                last_name = " ".join(words[1:]).title()
                logger.info(f"Name extracted via line heuristic: prefix={prefix}, first_name={first_name}, last_name={last_name}")
                return prefix, first_name, last_name

        # 2. spaCy PERSON entity fallback
        doc = self.parse_text(text)
        person_entities = [ent.text.strip() for ent in doc.ents if ent.label_ == "PERSON"]
        
        valid_names = []
        for name in person_entities:
            prefix = self._extract_dr_prefix(name)
            # Clean prefix titles from entity text while only persisting Dr
            name_clean = NAME_PREFIX_CLEANUP_PATTERN.sub("", name).strip()
            cleaned_name = " ".join([w for w in name_clean.split() if w.isalpha()])
            if cleaned_name and len(cleaned_name.split()) >= 2 and len(cleaned_name) < 40:
                # Exclude common technical terms spaCy might misclassify
                if any(tech in cleaned_name.lower() for tech in ["streamlit", "pandas", "matplotlib", "numpy", "tensorflow", "python"]):
                    continue
                valid_names.append((prefix, cleaned_name))
                break
        
        if valid_names:
            prefix, cleaned_name = valid_names[0]
            name_parts = cleaned_name.split()
            first_name = name_parts[0].title()
            last_name = " ".join(name_parts[1:]).title()
            logger.info(f"Name extracted via spaCy PERSON entity: prefix={prefix}, first_name={first_name}, last_name={last_name}")
            return prefix, first_name, last_name

        # Fallback default
        return None, "Doctor", "Candidate"

    def extract_name(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Backward-compatible helper that returns only first and last name.
        """
        _, first_name, last_name = self.extract_name_details(text)
        return first_name, last_name
