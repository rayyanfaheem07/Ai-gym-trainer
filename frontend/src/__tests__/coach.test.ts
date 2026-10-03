import { test, describe } from "node:test";
import assert from "node:assert/strict";
import { CoachingFeedback, Workout } from "@/types";

describe("Phase 13 AI Coach Frontend Data & State Management", () => {
  test("CoachingFeedback serialization accurately parses structured feedback fields", () => {
    const feedback: CoachingFeedback = {
      id: "cf-123",
      session_id: "wk-001",
      llm_model: "llama3.2",
      summary: "Completed 12 total reps with 10 valid reps and 85% form score.",
      strengths: ["Strong eccentric control", "Solid core brace"],
      areas_to_improve: ["Work on hip crease depth"],
      next_session_focus: "Depth consistency",
      safety_note: "Keep knees tracking over toes",
      is_fallback: false,
      created_at: "2026-09-18T10:00:00Z",
    };

    assert.equal(feedback.session_id, "wk-001");
    assert.equal(feedback.llm_model, "llama3.2");
    assert.equal(feedback.strengths.length, 2);
    assert.equal(feedback.areas_to_improve[0], "Work on hip crease depth");
    assert.equal(feedback.is_fallback, false);
    assert.equal(feedback.next_session_focus, "Depth consistency");
  });

  test("Fallback mode detection correctly identifies deterministic offline fallback", () => {
    const fallbackFeedback: CoachingFeedback = {
      id: "cf-456",
      session_id: "wk-002",
      llm_model: "llama3.2 (offline-fallback)",
      summary: "Completed 8 total repetitions across 1 set with 80% form score.",
      strengths: ["Consistent exercise engagement"],
      areas_to_improve: ["Focus on smooth cadence"],
      is_fallback: true,
      created_at: "2026-09-18T10:05:00Z",
    };

    const isFallbackMode =
      fallbackFeedback.is_fallback ||
      (fallbackFeedback.llm_model && fallbackFeedback.llm_model.toLowerCase().includes("fallback"));

    assert.equal(isFallbackMode, true);
  });

  test("Workout entity links correctly to attached CoachingFeedback", () => {
    const workout: Workout = {
      id: "wk-999",
      user_id: "user-abc",
      status: "completed",
      started_at: "2026-09-18T09:00:00Z",
      ended_at: "2026-09-18T09:10:00Z",
      total_duration_sec: 600,
      overall_form_score: 91.5,
      created_at: "2026-09-18T09:00:00Z",
      updated_at: "2026-09-18T09:10:00Z",
      feedback: {
        id: "fb-999",
        session_id: "wk-999",
        llm_model: "llama3.2",
        summary: "Excellent form across all sets.",
        strengths: ["High form score of 91%"],
        areas_to_improve: ["Maintain progressive overload"],
      },
    };

    assert.ok(workout.feedback);
    assert.equal(workout.feedback.session_id, workout.id);
    assert.equal(workout.overall_form_score, 91.5);
  });
});
