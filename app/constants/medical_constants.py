# Medical Resume Parser Constants

MEDICAL_SKILLS = [
    # Specializations & Core Fields
    "Cardiology", "Neurology", "ICU", "ECG", "Echocardiography", "Radiology",
    "Surgery", "Emergency Medicine", "Anesthesiology", "Pediatrics", "Orthopedics",
    "Oncology", "Dermatology", "Pathology", "Gynecology", "Obstetrics", "Ophthalmology",
    "Urology", "Psychiatry", "Gastroenterology", "Nephrology", "Pulmonology", "Endocrinology",
    "Rheumatology", "Hematology", "Immunology", "Internal Medicine", "General Medicine",
    "General Surgery", "Plastic Surgery", "Neurosurgery", "Cardiothoracic Surgery",
    "Orthopedic Surgery", "Pediatric Surgery", "ENT", "Otolaryngology",

    # Clinical Skills & Procedures
    "Suturing", "Patient Care", "Diagnosis", "Critical Care", "EMR", "EHR",
    "Prescribing", "Patient Evaluation", "Clinical Research", "Treatment Planning",
    "Intubation", "Ventilator Management", "Central Line Insertion", "Arterial Line",
    "Lumbar Puncture", "Cardiopulmonary Resuscitation", "CPR", "Patient Monitoring",
    "Triage", "Wound Care", "IV Cannulation", "Phlebotomy", "Diagnostic Imaging",
    "Ultrasound", "CT Scan", "MRI", "Medical Coding", "Pharmacology", "Telemedicine",
    "Dental implant placement", "Guided bone regeneration", "Sinus lift",
    "Complex extractions", "Bone grafting", "Surgical planning", "CAD-CAM restoration",
    "Aesthetic dentistry", "CBCT interpretation", "Crown and bridge preparation",
    "Removable prosthodontics", "Implant prosthetics", "Full-mouth rehabilitation",
    "Denture fabrication", "Shade matching", "Tooth preparation techniques",
    "Digital scanning", "CAD-CAM restorations", "Laser therapy", "Chemical peels",
    "Microdermabrasion", "Dermatosurgery", "Skin biopsy", "Cryotherapy",
    "Phototherapy", "Dermoscopy", "Histopathological diagnosis",
    "Immunohistochemistry", "Hematology analysis", "Bone marrow examination",
    "Psychiatric assessment", "Psychopharmacology", "Psychotherapy",
    "Cognitive behavioral therapy", "CBT", "Crisis intervention",
    "Electroconvulsive therapy", "ECT",

    # Technical & Data Science Skills
    "Python", "SQL", "NumPy", "Pandas", "Machine Learning", "Deep Learning",
    "Computer Vision", "NLP", "Data Science", "Data Visualization", "Streamlit",
    "Power BI", "Docker", "Git", "GitHub", "DICOM", "PACS", "LIS",
    "Electronic Health Records", "Hospital Information Systems",
    "Dental Practice Management Software", "Intraoral Scanners",
    "Digital Smile Design", "Telemedicine Platforms",
    "Laboratory Information System", "Digital Pathology Imaging",
]

CERTIFICATION_KEYWORDS = [
    "ACLS", "BLS", "ATLS", "DNB", "NALS", "PALS", "NRP", "FCCM", "FCCS",
    "FNB", "MRCP", "FRCS", "MRCS", "USMLE", "PLAB",
    "Advanced Cardiovascular Life Support", "Basic Life Support",
    "Advanced Trauma Life Support", "Neonatal Advanced Life Support",
    "Pediatric Advanced Life Support", "Neonatal Resuscitation Program",
    "Fellow", "FAAD", "ICOI", "Diplomate",
    "Board Certified", "Fellowship", "Registration",
]

LANGUAGES = [
    "English", "Hindi", "Marathi", "Tamil", "Telugu", "Kannada", "Malayalam",
    "Gujarati", "Bengali", "Punjabi", "Odia", "Urdu", "Spanish", "French",
    "German", "Arabic", "Mandarin", "Russian",
]

LANGUAGE_PROFICIENCY_KEYWORDS = {
    "fluent": "Fluent",
    "native": "Native",
    "intermediate": "Intermediate",
    "basic": "Basic",
    "conversational": "Intermediate",
    "proficient": "Fluent",
    "bilingual": "Fluent",
}

DEGREE_KEYWORDS = [
    "MBBS", "MD", "MS", "DM", "MCh", "DNB", "BDS", "MDS", "PhD",
    "B.Tech", "M.Tech", "B.E.", "M.E.", "BSc", "MSc", "B.Sc", "M.Sc", "Ph.D.",
    "Class XII", "Class X", "Class 12th", "Class 10th", "Class 12", "Class 10", "High School",
    "Bachelor of Medicine", "Bachelor of Surgery", "Doctor of Medicine",
    "Master of Surgery", "Diplomate of National Board", "Bachelor of Dental Surgery",
    "Master of Dental Surgery", "Bachelor of Science", "Master of Science",
    "Bachelor of Technology", "Master of Technology", "Bachelor of Engineering",
    "Master of Engineering", "Doctor of Philosophy", "BAMS", "BHMS", "BPT", "MPT",
    "Diploma", "Fellowship",
]

SPECIALIZATION_KEYWORDS = [
    "Cardiology", "Cardiologist", "Neurology", "Neurologist", "Pediatrics", "Pediatrician",
    "Orthopedics", "Orthopedic Surgeon", "Dermatology", "Dermatologist", "Radiology", "Radiologist",
    "Oncology", "Oncologist", "Anesthesiology", "Anesthesiologist", "Pathology", "Pathologist",
    "Surgery", "Surgeon", "General Surgeon", "Gynecology", "Gynecologist", "Obstetrics", "Obstetrician",
    "Internal Medicine", "General Medicine", "General Practitioner", "Physician", "Urology", "Urologist",
    "Psychiatry", "Psychiatrist", "Gastroenterology", "Gastroenterologist", "Nephrology", "Nephrologist",
    "Pulmonology", "Pulmonologist", "Endocrinology", "Endocrinologist", "ENT Specialist", "Ophthalmology",
    "Ophthalmologist", "Oral Surgery", "Oral and Maxillofacial Surgery", "Maxillofacial Surgery",
    "Prosthodontics", "Prosthodontist", "Oral Surgeon", "Oral Pathologist",
    "Computer Science", "Data Science", "Machine Learning", "Software Engineering",
]

SKILL_SECTION_HEADERS = {
    "clinical": [
        "clinical skills", "clinical", "clinical procedures", "medical skills",
        "surgical skills", "procedural skills", "core competencies",
    ],
    "technical": [
        "technical skills", "technical", "technical & software", "software",
        "technical & software skills", "it skills", "tools", "equipment",
    ],
    "soft_skills": [
        "soft skills", "soft", "interpersonal skills", "personal skills",
        "leadership skills", "communication", "personal attributes",
    ],
}

POSTGRADUATE_DEGREES = {"MD", "MS", "DM", "MCh", "MDS", "DNB", "Fellowship", "PhD"}
GRADUATE_DEGREES = {"MBBS", "BDS", "BAMS", "BHMS", "BPT", "B.Sc", "BSc", "B.Tech", "BE"}
SCHOOL_DEGREES = {"Class XII", "Class X", "Class 12th", "Class 10th", "Class 12", "Class 10", "High School"}
