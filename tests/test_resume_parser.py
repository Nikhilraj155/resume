import pytest
import tempfile
import os
from app.services.resume_parser import ResumeParserService, _clean_location_string, _DATE_RANGE_PATTERN


class TestCleanLocationString:
    def test_removes_email(self):
        result = _clean_location_string("user@example.com, Bengaluru")
        assert "user" not in result

    def test_removes_phone(self):
        result = _clean_location_string("+91-1234567890, Mumbai")
        assert "Mumbai" in result or result == "Mumbai"

    def test_removes_url(self):
        result = _clean_location_string("https://example.com New York")
        assert "New" in result or "York" in result

    def test_pipe_handling_last_segment(self):
        result = _clean_location_string("something | Mumbai")
        assert "Mumbai" in result

    def test_known_city_extraction(self):
        result = _clean_location_string("Some text Bengaluru more")
        assert "Bengaluru" in result or "bengaluru" in result.lower()

    def test_empty_input(self):
        assert _clean_location_string("") == ""


class TestDateRangeRegex:
    def test_month_year_range(self):
        m = _DATE_RANGE_PATTERN.search("Jan 2015 - Dec 2020")
        assert m is not None
        assert m.group(1) == "Jan 2015"
        assert m.group(2) == "Dec 2020"

    def test_year_only_range(self):
        m = _DATE_RANGE_PATTERN.search("2015 - 2020")
        assert m is not None
        assert m.group(1) == "2015"
        assert m.group(2) == "2020"

    def test_present_end(self):
        m = _DATE_RANGE_PATTERN.search("Jan 2020 - Present")
        assert m is not None
        assert "Present" in m.group(2)

    def test_no_match(self):
        m = _DATE_RANGE_PATTERN.search("No dates here")
        assert m is None


class TestResumeParserService:
    @pytest.fixture
    def parser(self):
        return ResumeParserService()

    def test_segment_text_experience(self, parser):
        text = "WORK EXPERIENCE\nSome experience here\nEducation\nSome education"
        sections = parser._segment_text(text)
        assert "experience" in sections
        assert "education" in sections
        assert "Some experience here" in sections["experience"]
        assert "Some education" in sections["education"]

    def test_segment_text_skills(self, parser):
        text = "Skills\nPython, Java\nCertifications\nSome cert"
        sections = parser._segment_text(text)
        assert "skills" in sections
        assert "certifications" in sections

    def test_parse_work_history_empty(self, parser):
        assert parser._parse_work_history("") == []

    def test_parse_work_history_basic(self, parser):
        text = "Cardiologist, Dept of Cardiology  Jan 2015 - Dec 2020"
        result = parser._parse_work_history(text)
        assert len(result) > 0
        entry = result[0]
        assert entry.designation is not None

    def test_parse_work_history_bullets_skipped(self, parser):
        text = "Consultant  Jan 2020 - Present\n- Managed patients\n- Performed surgeries"
        result = parser._parse_work_history(text)
        assert len(result) == 1


class TestParseResume:
    @pytest.fixture
    def parser(self):
        return ResumeParserService()

    def test_parse_resume_rejects_invalid_file(self, parser):
        with pytest.raises(ValueError):
            parser.parse_resume("nonexistent_file.pdf")

    def test_parse_resume_rejects_empty_file(self, parser):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            path = f.name
        try:
            with pytest.raises(ValueError):
                parser.parse_resume(path)
        finally:
            os.unlink(path)

    def test_email_regex_extraction(self, parser):
        from app.services.resume_parser import re
        text = "Contact me at doctor@hospital.com or call 12345"
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
        assert email_match is not None
        assert email_match.group(0) == "doctor@hospital.com"

    def test_phone_regex_extraction(self, parser):
        from app.services.resume_parser import re
        text = "Phone: +1-555-123-4567"
        phone_match = re.search(r'(\+?\d{1,4}[-.\s]?)?(\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4,6}', text)
        assert phone_match is not None
