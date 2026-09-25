export type ExerciseType = "squat" | "pushup" | "bicep_curl" | "lunge" | "shoulder_press";

export interface ExerciseItem {
  id: string;
  name: string;
  primary_target: string;
  difficulty: string;
  instructions: string[];
}

export interface FormIssue {
  id?: string;
  issue_code: string;
  severity: "low" | "moderate" | "high" | "critical" | string;
  feedback_text: string;
  timestamp_ms?: number;
}

export interface ExerciseResult {
  id?: string;
  rep_number: number;
  is_valid: boolean;
  form_score: number;
  duration_sec: number;
  eccentric_duration_sec?: number;
  concentric_duration_sec?: number;
  min_joint_angle?: number;
  max_joint_angle?: number;
  faults_detected?: string[];
  form_issues?: FormIssue[];
  created_at?: string;
}

export interface ExerciseSession {
  id: string;
  workout_id: string;
  exercise_name: string;
  session_order?: number;
  set_number?: number;
  target_reps?: number | null;
  completed_reps: number;
  valid_reps: number;
  invalid_reps: number;
  average_form_score: number;
  average_tempo_sec?: number;
  started_at?: string;
  ended_at?: string | null;
  results?: ExerciseResult[];
  reps?: ExerciseResult[];
}


export interface CoachingFeedback {
  id?: string;
  session_id: string;
  llm_model: string;
  summary: string;
  strengths: string[];
  areas_to_improve: string[];
  recovery_advice?: string;
  next_session_focus?: string;
  safety_note?: string;
  is_fallback?: boolean;
  created_at?: string;
}

export interface Workout {
  id: string;
  user_id: string;
  status: "in_progress" | "completed" | "cancelled";
  started_at: string;
  ended_at?: string | null;
  total_duration_sec?: number | null;
  total_calories?: number | null;
  overall_form_score?: number | null;
  notes?: string | null;
  created_at: string;
  updated_at: string;
  exercise_sessions?: ExerciseSession[];
  feedback?: CoachingFeedback;
}
