export type FitnessGoal =
  | "strength"
  | "muscle_gain"
  | "fat_loss"
  | "general_fitness"
  | "endurance";

export type ExperienceLevel = "beginner" | "intermediate" | "advanced";

export type PreferredFocus =
  | "form"
  | "strength"
  | "consistency"
  | "endurance"
  | "balanced";

export type CoachingStyle =
  | "concise"
  | "supportive"
  | "detailed"
  | "technical";

export type PersonalTrendDirection =
  | "improving"
  | "declining"
  | "stable"
  | "insufficient_data";

export interface UserProfile {
  id: string;
  user_id: string;
  fitness_goal: FitnessGoal;
  experience_level: ExperienceLevel;
  preferred_focus: PreferredFocus;
  coaching_style: CoachingStyle;
  created_at?: string;
  updated_at?: string;
}

export interface UserProfileUpdate {
  fitness_goal?: FitnessGoal;
  experience_level?: ExperienceLevel;
  preferred_focus?: PreferredFocus;
  coaching_style?: CoachingStyle;
}

export interface PersonalTrend {
  metric: string;
  exercise?: string | null;
  current_value?: number | null;
  previous_value?: number | null;
  change?: number | null;
  direction: PersonalTrendDirection;
  sufficient_data: boolean;
  message?: string | null;
}

export interface PersonalHistoryContext {
  workouts_completed: number;
  recent_workout_count: number;
  recent_form_score?: number | null;
  previous_form_score?: number | null;
  recurring_form_issues: string[];
  most_practiced_exercise?: string | null;
  valid_rep_percentage?: number | null;
  has_previous_workouts: boolean;
  comparison_available: boolean;
}
