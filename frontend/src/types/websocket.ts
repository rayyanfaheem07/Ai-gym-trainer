export type WSClientMessageType =
  | "pose_frame"
  | "start_session"
  | "stop_session"
  | "ping"
  | "set_exercise"
  | "reset";

export type WSServerMessageType =
  | "connected"
  | "analysis_result"
  | "session_started"
  | "session_stopped"
  | "pong"
  | "error";

export interface LandmarkPoint {
  x: number;
  y: number;
  z?: number;
  visibility?: number;
}

export interface PoseFramePayload {
  type?: "pose_frame";
  timestamp?: number;
  timestamp_ms?: number;
  exercise?: string;
  exercise_override?: string;
  landmarks: LandmarkPoint[];
}

export interface StartSessionPayload {
  type: "start_session";
  exercise?: string;
  workout_id?: string;
  notes?: string;
}

export interface StopSessionPayload {
  type: "stop_session";
  session_id?: string;
  save_to_db?: boolean;
}

export interface PingPayload {
  type: "ping";
  timestamp?: number;
}

export interface SetExercisePayload {
  type: "set_exercise";
  exercise: string;
}

export interface ResetPayload {
  type: "reset";
}

// Server Response Interfaces
export interface ConnectedResponse {
  type: "connected";
  status: string;
  user_id: string;
  session_id: string;
  message: string;
}

export interface AnalysisResultResponse {
  type: "analysis_result";
  timestamp: number;
  timestamp_ms: number;
  exercise: string;
  detected_exercise: string;
  stage: string;
  rep_count: number;
  valid_reps: number;
  invalid_reps: number;
  is_valid_rep: boolean;
  confidence: number;
  current_angles: Record<string, number>;
  primary_angle: number;
  form_score: number;
  warnings: string[];
  feedback: string[];
  issues: Array<{ name?: string; details?: string; severity?: string; [key: string]: any }>;
  audio_cue?: string | null;
  rep_duration_sec: number;
  metrics: Record<string, any>;
}

export interface SessionStartedResponse {
  type: "session_started";
  session_id: string;
  exercise: string;
  workout_id?: string | null;
  started_at: string;
}

export interface SessionSummary {
  session_id: string;
  exercise: string;
  user_id: string;
  workout_id?: string | null;
  total_reps: number;
  valid_reps: number;
  invalid_reps: number;
  average_form_score: number;
  duration_sec: number;
  frames_processed: number;
  persisted_to_db: boolean;
  persistence_error?: string;
}

export interface SessionStoppedResponse {
  type: "session_stopped";
  session_id: string;
  summary: SessionSummary;
}

export interface PongResponse {
  type: "pong";
  timestamp: number;
}

export interface ErrorResponse {
  type: "error";
  code: string;
  message: string;
}

export type WSServerMessage =
  | ConnectedResponse
  | AnalysisResultResponse
  | SessionStartedResponse
  | SessionStoppedResponse
  | PongResponse
  | ErrorResponse;
