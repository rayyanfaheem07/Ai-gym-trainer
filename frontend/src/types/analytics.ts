import { Workout } from "./workout";

export interface ExerciseBreakdownItem {
  exercise_name: string;
  total_sessions: number;
  total_reps: number;
  valid_reps: number;
  invalid_reps: number;
  accuracy_percentage: number;
  average_form_score: number;
  best_form_score: number;
  total_duration_sec: number;
}

export interface AnalyticsSummary {
  total_workouts: number;
  total_reps: number;
  total_valid_reps: number;
  total_invalid_reps: number;
  valid_rep_percentage: number;
  average_form_score: number;
  total_duration_sec: number;
  most_practiced_exercise: string | null;
  recent_workout_count: number;
  exercise_breakdown: ExerciseBreakdownItem[];
}

export interface ExerciseAnalytics {
  exercise_name: string;
  total_sessions: number;
  total_reps: number;
  valid_reps: number;
  invalid_reps: number;
  valid_rep_percentage: number;
  average_form_score: number;
  best_form_score: number;
  average_duration_sec: number;
  common_faults: Array<{ issue_code: string; feedback_text: string; occurrences: number }>;
  recent_sessions: Workout[];
}

export interface TrendPoint {
  date: string;
  timestamp: number;
  workout_id: string;
  exercise_name?: string | null;
  form_score: number;
  total_reps: number;
  valid_reps: number;
  valid_rep_percentage: number;
  duration_sec: number;
}

export interface AnalyticsTrends {
  period: string;
  exercise?: string | null;
  total_points: number;
  points: TrendPoint[];
}

export interface PaginatedWorkouts {
  items: Workout[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface WorkoutHistoryFilter {
  exercise?: string;
  start_date?: string;
  end_date?: string;
  status?: string;
  page?: number;
  page_size?: number;
}
