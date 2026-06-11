import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.resume_parser import ResumeParserService


class _FakeSpacyParser:
    def extract_name_details(self, text):
        return "Dr", "Rahul", "Sharma"

    def extract_entities(self, text):
        return {"GPE": [], "ORG": ["City Hospital", "State Medical University"]}


class ResumeParserServiceTests(unittest.TestCase):
    def test_parse_resume_returns_replacement_json_structure(self):
        service = object.__new__(ResumeParserService)
        service.spacy_parser = _FakeSpacyParser()

        resume_text = "\n".join(
            [
                "Dr Rahul Sharma",
                "MBBS, MD",
                "123 Medical Road, Mumbai, Maharashtra, India",
                "rahul.sharma@example.com",
                "+91 9876543210",
                "LinkedIn: linkedin.com/in/rahulsharma",
                "Professional Summary",
                "Experienced cardiologist with leadership in inpatient and outpatient care.",
                "Experience",
                "Senior Consultant | City Hospital | Mumbai | Jan 2020 - Present",
                "Lead cardiology department operations",
                "Reduced patient wait times by 20%",
                "Registrar | Metro Clinic | Pune | Jun 2016 - Dec 2019",
                "Managed OPD and emergency consultations",
                "Education",
                "Doctor of Medicine in Cardiology - State Medical University, Mumbai, 2013 - 2016, GPA 3.8",
                "MBBS - State Medical University, Mumbai, 2007 - 2013",
                "Class XII - Central Board of Secondary Education, 2005 - 2007, 91%",
                "Certifications",
                "ACLS - American Heart Association - 2021",
                "Medical License Number: REG12345",
                "Skills",
                "Cardiology, ECG, EHR, Python, Communication",
                "Languages",
                "English - Fluent",
                "Hindi - Native",
                "Projects",
                "Tele-cardiology outreach program",
                "Awards",
                "Best Resident Award",
                "Publications",
                "Cardiac Risk Study 2022",
                "Senior Consultant",
                "City Hospital",
            ]
        )

        with patch("app.services.resume_parser.PDFExtractorService.extract_text", return_value=resume_text), \
             patch("app.services.resume_parser.ExperienceCalculatorService.calculate_experience", return_value=0.0), \
             patch("app.services.resume_parser.MedicalSkillExtractorService.extract_skills", return_value=[]):
            result = service.parse_resume("dummy.pdf")

        self.assertEqual(result.personal_info.prefix, "Dr")
        self.assertEqual(result.personal_info.full_name, "Rahul Sharma")
        self.assertEqual(result.personal_info.linkedin, "linkedin.com/in/rahulsharma")
        self.assertEqual(result.professional_summary, "Experienced cardiologist with leadership in inpatient and outpatient care.")
        self.assertEqual(len(result.education), 3)
        self.assertEqual(len(result.work_experience), 2)
        self.assertEqual(result.work_experience[0].designation, "Senior Consultant")
        self.assertIn("City Hospital", result.medical_profile.hospital_affiliations)
        self.assertIn("REG12345", result.medical_profile.registration_license_numbers)
        self.assertIn("ACLS", [item.certification_name for item in result.certifications])
        self.assertIn("English", [item.language for item in result.languages])
        self.assertIn("Tele-cardiology outreach program", result.projects)
        self.assertIn("Best Resident Award", result.awards)
        self.assertIn("Cardiac Risk Study 2022", result.publications)
        self.assertIn("Cardiology", result.skills.clinical_skills)
        self.assertIn("Python", result.skills.technical_skills)
        self.assertIn("EHR", result.skills.software_skills)
        self.assertIn("Communication", result.skills.soft_skills)


if __name__ == "__main__":
    unittest.main()
