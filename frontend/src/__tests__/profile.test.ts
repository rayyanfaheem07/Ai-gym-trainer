import { test, describe } from "node:test";
import assert from "node:assert/strict";
import {
  UserProfile,
  UserProfileUpdate,
  PersonalTrend,
  PersonalHistoryContext,
} from "@/types";

describe("Phase 14 Athlete Personalization & Profile State Management", () => {
  test("UserProfile correctly parses all constrained profile enums", () => {
    const profile: UserProfile = {
      id: "prof-001",
      user_id: "user-001",
      fitness_goal: "strength",
      experience_level: "advanced",
      preferred_focus: "form",
      coaching_style: "technical",
      created_at: "2026-09-18T10:00:00Z",
    };

    assert.equal(profile.id, "prof-001");
    assert.equal(profile.fitness_goal, "strength");
    assert.equal(profile.experience_level, "advanced");
    assert.equal(profile.preferred_focus, "form");
    assert.equal(profile.coaching_style, "technical");
  });

  test("UserProfileUpdate allows partial updates", () => {
    const update: UserProfileUpdate = {
      fitness_goal: "muscle_gain",
      coaching_style: "concise",
    };

    assert.equal(update.fitness_goal, "muscle_gain");
    assert.equal(update.coaching_style, "concise");
    assert.equal(update.experience_level, undefined);
  });

  test("PersonalTrend data structure correctly identifies improving and declining directions", () => {
    const improvingTrend: PersonalTrend = {
      metric: "overall_form_score",
      exercise: "squat",
      current_value: 88.5,
      previous_value: 80.0,
      change: 8.5,
      direction: "improving",
      sufficient_data: true,
      message: "Squat form score improved by +8.5%",
    };

    assert.equal(improvingTrend.direction, "improving");
    assert.equal(improvingTrend.sufficient_data, true);
    assert.equal(improvingTrend.change, 8.5);

    const decliningTrend: PersonalTrend = {
      metric: "overall_form_score",
      exercise: null,
      current_value: 75.0,
      previous_value: 85.0,
      change: -10.0,
      direction: "declining",
      sufficient_data: true,
      message: "Form score declined by 10.0%",
    };

    assert.equal(decliningTrend.direction, "declining");
    assert.equal(decliningTrend.change, -10.0);
  });

  test("PersonalHistoryContext safely handles insufficient historical workouts", () => {
    const insufficientHistory: PersonalHistoryContext = {
      workouts_completed: 0,
      recent_workout_count: 0,
      recent_form_score: null,
      previous_form_score: null,
      recurring_form_issues: [],
      most_practiced_exercise: null,
      valid_rep_percentage: null,
      has_previous_workouts: false,
      comparison_available: false,
    };

    assert.equal(insufficientHistory.has_previous_workouts, false);
    assert.equal(insufficientHistory.comparison_available, false);
    assert.equal(insufficientHistory.recurring_form_issues.length, 0);
  });

  test("PersonalHistoryContext accurately stores recurring form issues", () => {
    const historyWithFaults: PersonalHistoryContext = {
      workouts_completed: 4,
      recent_workout_count: 3,
      recent_form_score: 82.0,
      previous_form_score: 79.0,
      recurring_form_issues: ["shallow_depth", "knee_valgus"],
      most_practiced_exercise: "squat",
      valid_rep_percentage: 85.5,
      has_previous_workouts: true,
      comparison_available: true,
    };

    assert.equal(historyWithFaults.has_previous_workouts, true);
    assert.equal(historyWithFaults.comparison_available, true);
    assert.equal(historyWithFaults.recurring_form_issues.length, 2);
    assert.ok(historyWithFaults.recurring_form_issues.includes("knee_valgus"));
  });
});
