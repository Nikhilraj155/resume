import os
from dotenv import load_dotenv
load_dotenv()

import pytest
from uuid import uuid4
from app.services.matching_engine import (
    _cosine_similarity,
    _jaccard_similarity,
    _experience_fit,
    _location_match,
    _build_candidate_name,
    _generate_semantic_reason,
    _generate_skill_reason,
    _generate_experience_reason,
    _generate_certification_reason,
    _generate_specialization_reason,
    _generate_location_reason,
)
from app.models import PersonalInfo


class TestCosineSimilarity:
    def test_identical_vectors(self):
        assert _cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0

    def test_orthogonal_vectors(self):
        assert _cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0

    def test_similar_vectors(self):
        result = _cosine_similarity([1.0, 0.5, 0.0], [0.9, 0.4, 0.1])
        assert 0.9 < result <= 1.0

    def test_empty_vectors(self):
        assert _cosine_similarity([], [1.0, 0.0]) == 0.0
        assert _cosine_similarity([1.0, 0.0], []) == 0.0

    def test_clamps_to_zero_one(self):
        result = _cosine_similarity([-10.0], [10.0])
        assert 0.0 <= result <= 1.0


class TestJaccardSimilarity:
    def test_identical_sets(self):
        assert _jaccard_similarity({"a", "b"}, {"a", "b"}) == 1.0

    def test_disjoint_sets(self):
        assert _jaccard_similarity({"a", "b"}, {"c", "d"}) == 0.0

    def test_partial_overlap(self):
        result = _jaccard_similarity({"a", "b", "c"}, {"b", "c", "d"})
        assert result == pytest.approx(0.5)

    def test_one_empty_set(self):
        assert _jaccard_similarity(set(), {"a", "b"}) == 0.0
        assert _jaccard_similarity({"a", "b"}, set()) == 0.0


class TestExperienceFit:
    def test_exact_match(self):
        assert _experience_fit(5.0, 3.0, 7.0) == 1.0

    def test_below_minimum(self):
        score = _experience_fit(1.0, 3.0, 7.0)
        assert 0.0 <= score < 1.0

    def test_above_maximum(self):
        score = _experience_fit(10.0, 3.0, 7.0)
        assert 0.0 <= score < 1.0

    def test_no_resume_years(self):
        assert _experience_fit(None, 3.0, 7.0) == 0.0

    def test_no_jd_bounds(self):
        assert _experience_fit(5.0, None, None) == 0.5


class TestLocationMatch:
    def test_exact_city_match(self):
        assert _location_match("Mumbai", "Maharashtra", "Mumbai, India") == 1.0

    def test_state_match(self):
        assert _location_match("Pune", "Maharashtra", "Mumbai, Maharashtra") == 0.75

    def test_no_match(self):
        assert _location_match("New York", "NY", "Mumbai, India") == 0.0

    def test_no_resume_location(self):
        assert _location_match(None, None, "Mumbai, India") == 0.0

    def test_no_jd_location(self):
        assert _location_match("Mumbai", "Maharashtra", None) == 0.5


class TestBuildCandidateName:
    def test_full_name(self):
        pi = PersonalInfo(prefix="Dr.", first_name="John", last_name="Doe")
        assert _build_candidate_name(pi) == "Dr. John Doe"

    def test_no_prefix(self):
        pi = PersonalInfo(first_name="John", last_name="Doe")
        assert _build_candidate_name(pi) == "John Doe"

    def test_only_first_name(self):
        pi = PersonalInfo(first_name="John")
        assert _build_candidate_name(pi) == "John"

    def test_none_personal_info(self):
        assert _build_candidate_name(None) is None

    def test_no_name_parts(self):
        pi = PersonalInfo()
        assert _build_candidate_name(pi) is None


class TestMatchReasons:
    def test_semantic_reason_high(self):
        assert "Excellent" in _generate_semantic_reason(0.85)

    def test_semantic_reason_low(self):
        assert "Poor" in _generate_semantic_reason(0.1)

    def test_skill_reason_strong(self):
        reason = _generate_skill_reason(0.8, 8, 10, 20)
        assert "Strong" in reason
        assert "8" in reason

    def test_skill_reason_no_requirements(self):
        reason = _generate_skill_reason(0.0, 0, 0, 5)
        assert "No specific skills" in reason

    def test_skill_reason_no_match(self):
        reason = _generate_skill_reason(0.0, 0, 5, 5)
        assert "No overlapping" in reason

    def test_experience_reason_within_range(self):
        reason = _generate_experience_reason(1.0, 5.0, 3.0, 7.0)
        assert "fits within" in reason

    def test_experience_reason_no_years(self):
        reason = _generate_experience_reason(0.0, None, 3.0, 7.0)
        assert "not available" in reason

    def test_experience_reason_no_bounds(self):
        reason = _generate_experience_reason(0.5, 5.0, None, None)
        assert "years of relevant experience" in reason

    def test_certification_reason_all_present(self):
        reason = _generate_certification_reason(0.9, 3, 3)
        assert "All required certifications" in reason

    def test_certification_reason_no_requirements(self):
        reason = _generate_certification_reason(0.0, 0, 0)
        assert "No certifications required" in reason

    def test_certification_reason_no_match(self):
        reason = _generate_certification_reason(0.0, 0, 3)
        assert "No matching certifications" in reason

    def test_specialization_reason_direct_match(self):
        reason = _generate_specialization_reason(1.0, "Cardiology", "Healthcare")
        assert "directly matches" in reason

    def test_specialization_reason_no_spec(self):
        reason = _generate_specialization_reason(0.0, None, "Healthcare")
        assert "not available" in reason

    def test_location_reason_exact(self):
        reason = _generate_location_reason(1.0, "Mumbai", "Maharashtra", "Mumbai, India")
        assert "matches the job location" in reason

    def test_location_reason_no_jd_location(self):
        reason = _generate_location_reason(0.5, "Mumbai", "Maharashtra", None)
        assert "No location preference" in reason

    def test_location_reason_no_match(self):
        reason = _generate_location_reason(0.0, "New York", "NY", "Mumbai, India")
        assert "differs from" in reason


class TestMatchJobsIntegration:
    @pytest.fixture(autouse=True)
    def check_db(self):
        if not os.getenv("DATABASE_URL"):
            pytest.skip("DATABASE_URL not set, skipping integration test")

    def test_match_jobs_returns_empty_for_nonexistent_resume(self):
        from app.services.matching_engine import match_jobs
        results, candidate_name, total = match_jobs(uuid4(), top_k=5)
        assert results == []
        assert candidate_name is None
        assert total == 0


class TestMatchingEndpoint:
    @pytest.fixture(autouse=True)
    def check_db(self):
        if not os.getenv("DATABASE_URL"):
            pytest.skip("DATABASE_URL not set, skipping integration test")

    def test_health_endpoint(self):
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_match_endpoint_returns_422_for_missing_resume_id(self):
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        resp = client.post("/ai/match-jobs", json={})
        assert resp.status_code == 422

    def test_match_endpoint_returns_404_for_nonexistent_resume(self):
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        resp = client.post("/ai/match-jobs", json={"resume_id": str(uuid4()), "top_k": 5})
        assert resp.status_code == 404
