# Doctor Resume Parser AI Microservice

A production-ready AI-powered resume parsing microservice built with **FastAPI** and **Google Gemini 2.5 Flash** to extract structured profile information from doctor resumes (PDF/DOCX). The parsed output directly maps to a 4-step frontend profile completion form without requiring additional conversion.

---

## Tech Stack
* **Language**: Python 3.10+
* **Framework**: FastAPI (Pydantic v2 validation)
* **Model**: Google Gemini 2.5 Flash
* **Text Extractors**: 
  * PyMuPDF (for PDFs)
  * python-docx (for Word documents)
* **Server**: Uvicorn
* **Database**: PostgreSQL (via Neon) with SQLAlchemy

---

## Folder Structure
```
ai-service/
├── app/
│   ├── main.py              # Application bootstrap & handlers
│   ├── database.py          # SQLAlchemy engine, session & table initialization
│   ├── models.py            # ORM models for PostgreSQL (Neon)
│   ├── routes/              # Route controllers
│   │   └── parser.py        # /ai/parse-resume endpoint
│   ├── services/            # Business logic / AI integration
│   │   ├── pdf_extractor.py          # PyMuPDF & python-docx text extractor
│   │   ├── resume_parser.py          # Core parsing with spaCy & regex
│   │   ├── resume_storage.py         # Persists parsed resumes to PostgreSQL
│   │   ├── spacy_parser.py           # spaCy NER & name extraction
│   │   ├── medical_skill_extractor.py
│   │   └── experience_calculator.py
│   ├── schemas/             # Pydantic schemas for data integrity
│   │   └── resume.py
│   ├── prompts/             # System instructions & templates
│   │   └── resume_prompt.py
│   ├── templates/
│   │   └── index.html       # Testing frontend
│   └── utils/
│       └── logger.py        # Custom formatted console logger
├── tests/                   # Unit tests
├── uploads/                 # Temporary directory for uploaded resumes (UUID named)
├── requirements.txt         # Package dependencies
├── .env                     # Environment variables (incl. DATABASE_URL)
└── postman_collection.json  # Importable Postman workspace
```

---

## Setup & Running Locally

### 1. Clone & Navigate
```bash
cd ai-service
```

### 2. Create Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Setup Environment Variables
Copy `.env.example` to `.env` and configure the required variables:
```bash
copy .env.example .env
```
Open `.env` and edit:
```env
PORT=8000
LOG_LEVEL=INFO
GEMINI_API_KEY=AIzaSyYourActualAPIKeyHere
DATABASE_URL=postgresql://user:password@host:port/dbname?sslmode=require
```

> **Database**: Parsed resumes are stored in PostgreSQL (Neon). Use a pooled connection URL (with `-pooler` in the hostname) for runtime queries. Table creation is handled automatically on startup via a direct connection.

### 5. Launch the Service
```bash
python -m app.main
```
The application will be live at `http://localhost:8000`. 
* **Swagger Interactive Docs**: `http://localhost:8000/docs`
* **Alternative ReDoc**: `http://localhost:8000/redoc`

---

## API Documentation

### 1. Health Check
* **Endpoint**: `GET /health`
* **Response**:
```json
{
  "status": "healthy",
  "gemini_api_configured": true,
  "version": "1.0.0"
}
```

### 2. Parse Resume
* **Endpoint**: `POST /ai/parse-resume`
* **Content-Type**: `multipart/form-data`
* **Request Params**:
  * `file`: (Binary PDF/DOCX)

---

## Sample Request & Response

### Sample Request (cURL)
```bash
curl -X 'POST' \
  'http://localhost:8000/ai/parse-resume' \
  -H 'accept: application/json' \
  -H 'Content-Type: multipart/form-data' \
  -F 'file=@dr_sarah_resume.pdf;type=application/pdf'
```

### Sample Response
```json
{
  "personal_info": {
    "prefix": "Dr",
    "first_name": "Sarah",
    "last_name": "Jenkins",
    "email": "sarah.jenkins@gmail.com",
    "phone": "+1-555-0199",
    "gender": "Female",
    "date_of_birth": "1988-04-12",
    "city": "Boston",
    "state": "Massachusetts",
    "country": "United States",
    "professional_headline": "Consultant Cardiologist with 8+ years of clinical practice in interventional cardiology."
  },
  "education": [
    {
      "degree": "MBBS",
      "specialization": "Medicine and Surgery",
      "college": "Harvard Medical School",
      "start_year": "2006",
      "end_year": "2012"
    },
    {
      "degree": "MD",
      "specialization": "Cardiology",
      "college": "Johns Hopkins University School of Medicine",
      "start_year": "2012",
      "end_year": "2015"
    }
  ],
  "experience": {
    "specialization": "Cardiologist",
    "experience_years": 8.5,
    "current_designation": "Senior Interventional Cardiologist",
    "current_hospital": "Massachusetts General Hospital",
    "medical_registration_number": "MC-987654-A"
  },
  "skills": [
    "Angioplasty",
    "Echocardiography",
    "Patient Care",
    "Electrocardiogram (ECG) Analysis",
    "Clinical Research"
  ],
  "certifications": [
    "Board Certified in Cardiovascular Disease",
    "Advanced Cardiovascular Life Support (ACLS)"
  ],
  "languages": [
    "English",
    "Spanish"
  ]
}
```

---

## Error Handling

The application maps specific error codes for seamless client error resolution:
* **`400 Bad Request`**: File is corrupted, empty, or uses an unsupported file extension.
* **`422 Unprocessable Entity`**: Request format/multipart parameters are wrong.
* **`500 Internal Server Error`**: Gemini API failure, network down, or unhandled exceptions.

## Database

Parsed resume data is automatically persisted to a **PostgreSQL** database (Neon) using SQLAlchemy ORM. Storage runs as a background task so it does not affect response time.

### Tables

| Table | Description |
|-------|-------------|
| `parsed_resumes` | Root record per uploaded file |
| `personal_info` | Doctor's name, contact, location |
| `education` | Degrees, colleges, years |
| `experience` | Specialization, years, current role |
| `work_history` | Individual job entries (FK → experience) |
| `resume_skills` | Extracted medical skills |
| `resume_certifications` | Certifications found in resume |
| `resume_languages` | Languages spoken |

> Database tables are created automatically on first startup. No manual migration steps needed.
