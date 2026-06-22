import sys, os, json
sys.path.insert(0, '.')
from app.services.resume_parser import ResumeParserService

parser = ResumeParserService()
files = sorted(os.listdir('resumess'))
for f in files:
    if not f.endswith('.pdf'):
        continue
    path = os.path.join('resumess', f)
    print(f"\n{'='*60}")
    print(f"FILE: {f}")
    print('='*60)
    result = parser.parse_resume(path)
    data = json.loads(result.model_dump_json(exclude_none=True))
    print(json.dumps(data, indent=2))
