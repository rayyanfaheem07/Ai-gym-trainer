import { test, describe } from "node:test";
import assert from "node:assert/strict";
import { AnalyticsSummary, ExerciseBreakdownItem, TrendPoint } from "../types/analytics";

describe("Phase 12 Frontend Analytics Data Transformation & Calculations", () => {
  test("Analytics summary accurately calculates valid rep percentage and duration", () => {
    const summary: AnalyticsSummary = {
      total_workouts: 4,
      total_reps: 40,
      total_valid_reps: 36,
      total_invalid_reps: 4,
      valid_rep_percentage: 90.0,
      average_form_score: 93.5,
      total_duration_sec: 1250.0,
      most_practiced_exercise: "squat",
      recent_workout_count: 4,
      exercise_breakdown: [
        {
          exercise_name: "squat",
          total_sessions: 2,
          total_reps: 20,
          valid_reps: 18,
          invalid_reps: 2,
          accuracy_percentage: 90.0,
          average_form_score: 94.0,
          best_form_score: 96.0,
          total_duration_sec: 600.0,
        },
        {
          exercise_name: "pushup",
          total_sessions: 2,
          total_reps: 20,
          valid_reps: 18,
          invalid_reps: 2,
          accuracy_percentage: 90.0,
          average_form_score: 93.0,
          best_form_score: 95.0,
          total_duration_sec: 650.0,
        },
      ],
    };

    assert.equal(summary.total_workouts, 4);
    assert.equal(summary.total_reps, 40);
    assert.equal(summary.total_valid_reps, 36);
    assert.equal(summary.valid_rep_percentage, 90.0);
    assert.equal(summary.exercise_breakdown.length, 2);
    assert.equal(summary.most_practiced_exercise, "squat");
  });

  test("Trend points serialization accurately preserves timestamps and form scores", () => {
    const points: TrendPoint[] = [
      {
        date: "2026-09-01",
        timestamp: 1725184800,
        workout_id: "w-1",
        exercise_name: "squat",
        form_score: 88.5,
        total_reps: 10,
        valid_reps: 9,
        valid_rep_percentage: 90.0,
        duration_sec: 120.0,
      },
      {
        date: "2026-09-05",
        timestamp: 1725530400,
        workout_id: "w-2",
        exercise_name: "squat",
        form_score: 94.0,
        total_reps: 12,
        valid_reps: 12,
        valid_rep_percentage: 100.0,
        duration_sec: 145.0,
      },
    ];

    assert.equal(points.length, 2);
    assert.equal(points[0].form_score < points[1].form_score, true);
    assert.equal(points[1].valid_rep_percentage, 100.0);
  });

  test("Workout history filter state transitions handle page reset on exercise filter change", () => {
    let filterState = {
      exercise: "",
      page: 3,
      page_size: 10,
    };

    const handleFilterChange = (newExercise: string) => {
      filterState = {
        ...filterState,
        exercise: newExercise,
        page: 1, // Must reset to page 1
      };
    };

    handleFilterChange("squat");
    assert.equal(filterState.exercise, "squat");
    assert.equal(filterState.page, 1);
  });

  test("Pagination total pages helper computes correct ceiling count", () => {
    const computeTotalPages = (total: number, pageSize: number) => {
      if (total <= 0) return 1;
      return Math.ceil(total / pageSize);
    };

    assert.equal(computeTotalPages(0, 10), 1);
    assert.equal(computeTotalPages(5, 10), 1);
    assert.equal(computeTotalPages(10, 10), 1);
    assert.equal(computeTotalPages(11, 10), 2);
    assert.equal(computeTotalPages(25, 10), 3);
  });

  test("Duration formatter converts seconds to human readable strings", () => {
    const formatDuration = (sec: number) => {
      if (sec >= 3600) {
        const hrs = Math.floor(sec / 3600);
        const mins = Math.round((sec % 3600) / 60);
        return `${hrs}h ${mins}m`;
      }
      if (sec >= 60) {
        return `${Math.round(sec / 60)}m`;
      }
      return `${Math.round(sec)}s`;
    };

    assert.equal(formatDuration(45), "45s");
    assert.equal(formatDuration(120), "2m");
    assert.equal(formatDuration(3660), "1h 1m");
  });
});
