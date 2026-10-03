import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from backend.app.schemas.coach import (
    CoachContext,
    CoachStructuredOutput,
    ExerciseSessionContext,
    FormIssueSummary,
)
from backend.app.services.coach_provider import (
    CoachProviderError,
    CoachProviderTimeoutError,
    CoachProviderUnavailableError,
    CoachProviderValidationError,
    DeterministicFallbackCoachProvider,
    OllamaCoachProvider,
)


@pytest.fixture
def sample_coach_context() -> CoachContext:
    return CoachContext(
        workout_id="wk-test-123",
        session_date="2026-09-18T10:00:00Z",
        total_duration_sec=240.0,
        overall_form_score=85.0,
        total_reps=12,
        valid_reps=10,
        invalid_reps=2,
        exercises=[
            ExerciseSessionContext(
                exercise_name="squat",
                session_order=1,
                total_reps=12,
                valid_reps=10,
                invalid_reps=2,
                average_form_score=85.0,
                average_tempo_sec=2.5,
                form_issues=[
                    FormIssueSummary(
                        issue_type="shallow_depth",
                        count=2,
                        severity="moderate",
                        feedback_samples=["Squat depth above parallel"],
                    )
                ],
            )
        ],
        top_form_issues=[
            FormIssueSummary(
                issue_type="shallow_depth",
                count=2,
                severity="moderate",
                feedback_samples=["Squat depth above parallel"],
            )
        ],
        target_focus="form_improvement",
    )


@pytest.mark.asyncio
async def test_ollama_provider_successful_response(sample_coach_context: CoachContext):
    provider = OllamaCoachProvider(base_url="http://localhost:11434", model="llama3.2")

    mock_llm_json = {
        "summary": "Great workout overall with 10 valid squats out of 12 completed.",
        "strengths": ["Maintained good cadence", "Strong core stabilization"],
        "areas_to_improve": ["Ensure hip crease descends below parallel on depth"],
        "next_session_focus": "Practice full depth pause squats",
        "safety_note": "Keep knees tracking over toes without valgus collapse",
    }

    mock_response = httpx.Response(
        status_code=200,
        json={"response": json.dumps(mock_llm_json)},
        request=httpx.Request("POST", "http://localhost:11434/api/generate"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        result = await provider.generate_coaching(sample_coach_context)

        assert isinstance(result, CoachStructuredOutput)
        assert result.summary == mock_llm_json["summary"]
        assert result.strengths == mock_llm_json["strengths"]
        assert result.areas_to_improve == mock_llm_json["areas_to_improve"]
        assert result.next_session_focus == mock_llm_json["next_session_focus"]
        assert result.safety_note == mock_llm_json["safety_note"]


@pytest.mark.asyncio
async def test_ollama_provider_connection_refused(sample_coach_context: CoachContext):
    provider = OllamaCoachProvider(base_url="http://localhost:11434", model="llama3.2")

    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")):
        with pytest.raises(CoachProviderUnavailableError) as exc_info:
            await provider.generate_coaching(sample_coach_context)
        assert "unreachable" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_ollama_provider_timeout(sample_coach_context: CoachContext):
    provider = OllamaCoachProvider(base_url="http://localhost:11434", timeout_seconds=5.0)

    with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Read timed out")):
        with pytest.raises(CoachProviderTimeoutError) as exc_info:
            await provider.generate_coaching(sample_coach_context)
        assert "timed out" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_ollama_provider_http_500(sample_coach_context: CoachContext):
    provider = OllamaCoachProvider(base_url="http://localhost:11434")

    mock_response = httpx.Response(
        status_code=500,
        text="Internal Model Error",
        request=httpx.Request("POST", "http://localhost:11434/api/generate"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        with pytest.raises(CoachProviderError) as exc_info:
            await provider.generate_coaching(sample_coach_context)
        assert "500" in str(exc_info.value)


@pytest.mark.asyncio
async def test_ollama_provider_malformed_json_response(sample_coach_context: CoachContext):
    provider = OllamaCoachProvider(base_url="http://localhost:11434")

    mock_response = httpx.Response(
        status_code=200,
        json={"response": "This is plain text not valid json"},
        request=httpx.Request("POST", "http://localhost:11434/api/generate"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        with pytest.raises(CoachProviderValidationError) as exc_info:
            await provider.generate_coaching(sample_coach_context)
        assert "invalid structured json" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_deterministic_fallback_provider(sample_coach_context: CoachContext):
    fallback_provider = DeterministicFallbackCoachProvider()
    result = await fallback_provider.generate_coaching(sample_coach_context)

    assert isinstance(result, CoachStructuredOutput)
    assert "12 total repetitions" in result.summary
    assert "85% form score" in result.summary
    assert len(result.strengths) > 0
    assert any("depth" in item.lower() for item in result.areas_to_improve)
    assert result.next_session_focus is not None
    assert "shallow depth" in result.next_session_focus.lower()
    assert result.safety_note is not None
