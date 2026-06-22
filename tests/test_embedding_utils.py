import pytest
from uuid import uuid4
from app.services.embedding_utils import (
    build_embedding_text_from_schema,
)
from app.schemas.resume import (
    ResumeParserResponseSchema, PersonalInfoSchema,
    EducationItemSchema, ExperienceSchema, WorkHistoryItemSchema,
    SkillCategorySchema, CertificationSchema, LanguageSchema,
)


class TestBuildEmbeddingTextFromSchema:
    def test_empty_resume(self):
        data = ResumeParserResponseSchema(
            personal_info=PersonalInfoSchema(),
            experience=ExperienceSchema(),
        )
        text = build_embedding_text_from_schema(data)
        assert text == ""

    def test_with_personal_info(self):
        data = ResumeParserResponseSchema(
            personal_info=PersonalInfoSchema(
                prefix="Dr", first_name="John", last_name="Doe"
            ),
            experience=ExperienceSchema(),
        )
        text = build_embedding_text_from_schema(data)
        assert "Dr John Doe" in text

    def test_with_skills(self):
        data = ResumeParserResponseSchema(
            personal_info=PersonalInfoSchema(),
            experience=ExperienceSchema(),
            skills=SkillCategorySchema(
                clinical=["Cardiology", "Echocardiography"],
            ),
        )
        text = build_embedding_text_from_schema(data)
        assert "Cardiology" in text
        assert "Echocardiography" in text

    def test_with_education(self):
        data = ResumeParserResponseSchema(
            personal_info=PersonalInfoSchema(),
            experience=ExperienceSchema(),
            education=[
                EducationItemSchema(degree="MBBS", college="Harvard Medical School"),
            ],
        )
        text = build_embedding_text_from_schema(data)
        assert "MBBS" in text
        assert "Harvard Medical School" in text

    def test_with_experience(self):
        data = ResumeParserResponseSchema(
            personal_info=PersonalInfoSchema(),
            experience=ExperienceSchema(
                specialization="Cardiology",
                experience_years=8.5,
                work_history=[
                    WorkHistoryItemSchema(
                        designation="Consultant",
                        employer="City Hospital",
                        start_date="Jan 2015",
                        end_date="Dec 2020",
                    ),
                ],
            ),
        )
        text = build_embedding_text_from_schema(data)
        assert "Cardiology" in text
        assert "8.5" in text
        assert "Consultant" in text
        assert "City Hospital" in text

    def test_with_certifications(self):
        data = ResumeParserResponseSchema(
            personal_info=PersonalInfoSchema(),
            experience=ExperienceSchema(),
            certifications=[
                CertificationSchema(name="Board Certified"),
                CertificationSchema(name="ACLS"),
            ],
        )
        text = build_embedding_text_from_schema(data)
        assert "Board Certified" in text
        assert "ACLS" in text

    def test_with_languages(self):
        data = ResumeParserResponseSchema(
            personal_info=PersonalInfoSchema(),
            experience=ExperienceSchema(),
            languages=[
                LanguageSchema(language="English", proficiency="Fluent"),
                LanguageSchema(language="Spanish", proficiency="Native"),
            ],
        )
        text = build_embedding_text_from_schema(data)
        assert "English (Fluent)" in text
        assert "Spanish (Native)" in text

    def test_with_location(self):
        data = ResumeParserResponseSchema(
            personal_info=PersonalInfoSchema(city="Mumbai", state="Maharashtra"),
            experience=ExperienceSchema(),
        )
        text = build_embedding_text_from_schema(data)
        assert "Mumbai" in text
        assert "Maharashtra" in text


class TestBuildEmbeddingTextFromResume:
    def test_import_exists(self):
        from app.services.embedding_utils import build_embedding_text_from_resume
        assert callable(build_embedding_text_from_resume)
