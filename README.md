# Doctor Resume Parser AI Microservice

An AI-powered resume parsing microservice built with **FastAPI** and open-source NLP (spaCy, SentenceTransformers) to extract structured profile information from doctor resumes (PDF/DOCX). The parsed output maps directly to a 4-step profile completion form.

## Tech Stack
* **Language**: Python 3.10+
* **Framework**: FastAPI (Pydantic v2 validation)
* **NLP**: spaCy (NER: `en_core_web_sm`)
* **Embeddings**: SentenceTransformers (`BAAI/bge-small-en-v1.5`, 384-dim)
* **Text Extractors**:
  * PyMuPDF (for PDFs, including TeX-generated PDFs)
  * python-docx (for Word documents)
* **Server**: Uvicorn
* **Database**: PostgreSQL (Neon) with SQLAlchemy + pgvector
* **Configuration**: pydantic-settings
* **Testing**: pytest + httpx

## Project Structure
```
ai-service/
├── app/
│   ├── main.py              # Application bootstrap & handlers
│   ├── config.py            # Centralized settings (pydantic-settings)
│   ├── database.py          # SQLAlchemy engine, session & table initialization
│   ├── models.py            # ORM models for PostgreSQL
│   ├── routes/              # Route controllers
│   │   ├── parser.py        # /ai/parse-resume endpoint
│   │   └── matching.py      # /ai/match-jobs endpoint
│   ├── services/            # Business logic
│   │   ├── pdf_extractor.py           # PyMuPDF & python-docx text extractor
│   │   ├── resume_parser.py           # Core parsing with spaCy & regex
│   │   ├── resume_storage.py          # Persists parsed resumes to PostgreSQL
│   │   ├── spacy_parser.py            # spaCy NER & name extraction
│   │   ├── medical_skill_extractor.py # Keyword-based medical skill detection
│   │   ├── experience_calculator.py   # Date range parsing & experience calc
│   │   ├── embedding_service.py       # SentenceTransformer wrapper
│   │   ├── embedding_utils.py         # Shared embedding text builder
│   │   └── matching_engine.py         # Multi-factor job matching
│   ├── schemas/             # Pydantic schemas
│   │   ├── resume.py
│   │   └── matching.py
│   ├── constants/
│   │   └── medical_constants.py  # Medical skills, certs, lists
│   ├── templates/
│   │   └── index.html       # Testing frontend (wizard UI)
│   └── utils/
│       └── logger.py        # Custom formatted console logger
├── tests/
│   ├── test_matching_engine.py
│   ├── test_resume_parser.py
│   ├── test_embedding_utils.py
│   └── test_api.py
├── uploads/                 # Temporary uploaded files (auto-cleaned)
├── requirements.txt
├── .env                     # Environment variables
└── postman_collection.json
```

## Setup & Running Locally

### 1. Create Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### 3. Configure Environment
Create a `.env` file:
```env
PORT=8000
LOG_LEVEL=INFO
DATABASE_URL=postgresql://user:password@host:port/dbname?sslmode=require
MAX_UPLOAD_SIZE_MB=10
```

### 4. Launch the Service
```bash
python -m app.main
```

The application will be live at `http://localhost:8000`.
* **Swagger Docs**: `http://localhost:8000/docs`
* **ReDoc**: `http://localhost:8000/redoc`

## API Endpoints

### 1. Health Check
`GET /health`

### 2. Parse Resume
`POST /ai/parse-resume` (multipart/form-data, accepts PDF/DOCX)

### 3. Match Jobs
`POST /ai/match-jobs` (JSON with `resume_id` and `top_k`)

## Database

Tables are created automatically on first startup. Uses pgvector for semantic search.

| Table | Description |
|-------|-------------|
| `parsed_resumes` | Root record per uploaded file |
| `personal_info` | Doctor's name, contact, location |
| `education` | Degrees, colleges, years |
| `experience` | Specialization, years, current role |
| `work_history` | Individual job entries |
| `resume_skills` | Extracted medical skills |
| `resume_certifications` | Certifications |
| `resume_languages` | Languages spoken |

## Running Tests
```bash
pytest tests/ -v
```
