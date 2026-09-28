import {
  AnalyticsSummary,
  AnalyticsTrends,
  AuthTokens,
  CoachingFeedback,
  ExerciseAnalytics,
  ExerciseItem,
  LoginRequest,
  PaginatedWorkouts,
  RegisterRequest,
  User,
  UserProfile,
  UserProfileUpdate,
  Workout,
  WorkoutHistoryFilter,
} from "@/types";
import { getStoredToken, removeStoredToken } from "./auth";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  (process.env.NEXT_PUBLIC_API_URL
    ? `${process.env.NEXT_PUBLIC_API_URL}/api/v1`
    : "http://localhost:8000/api/v1");

export class ApiError extends Error {
  status: number;
  code?: string;
  details?: any;

  constructor(message: string, status: number, code?: string, details?: any) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;
  const token = getStoredToken();

  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  if (token) {
    (headers as Record<string, string>)["Authorization"] = `Bearer ${token}`;
  }

  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
    });
  } catch (err: any) {
    throw new ApiError(
      "Unable to connect to the AI Gym Trainer server. Please ensure the backend is running.",
      0,
      "NETWORK_ERROR"
    );
  }

  if (response.status === 401) {
    // Unauthorized / Expired Token
    removeStoredToken();
    let errorMsg = "Authentication required or session expired. Please log in.";
    try {
      const errJson = await response.json();
      if (errJson.detail?.message) errorMsg = errJson.detail.message;
      else if (typeof errJson.detail === "string") errorMsg = errJson.detail;
    } catch {
      // fallback
    }
    throw new ApiError(errorMsg, 401, "UNAUTHORIZED");
  }

  if (!response.ok) {
    let errorMsg = `Server error (${response.status})`;
    let errorCode = "API_ERROR";
    let errorDetails = null;

    try {
      const errJson = await response.json();
      if (errJson.detail) {
        if (typeof errJson.detail === "string") {
          errorMsg = errJson.detail;
        } else if (errJson.detail.message) {
          errorMsg = errJson.detail.message;
          errorCode = errJson.detail.code || errorCode;
          errorDetails = errJson.detail.details;
        } else if (Array.isArray(errJson.detail)) {
          // FastAPI / Pydantic validation error array
          errorMsg = errJson.detail.map((e: any) => e.msg || JSON.stringify(e)).join(", ");
          errorCode = "VALIDATION_ERROR";
        }
      }
    } catch {
      errorMsg = response.statusText || errorMsg;
    }

    throw new ApiError(errorMsg, response.status, errorCode, errorDetails);
  }

  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}

// --- Auth APIs ---
export const authApi = {
  register: (data: RegisterRequest) =>
    request<User>("/auth/register", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  login: (data: LoginRequest) =>
    request<AuthTokens>("/auth/login", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getMe: () => request<User>("/auth/me", { method: "GET" }),
};

// --- Personalization / Profile APIs ---
export const profileApi = {
  get: () => request<UserProfile>("/profile", { method: "GET" }),

  update: (data: UserProfileUpdate) =>
    request<UserProfile>("/profile", {
      method: "PUT",
      body: JSON.stringify(data),
    }),
};

// --- Exercise Catalog APIs ---
export const exerciseApi = {
  list: () => request<{ exercises: ExerciseItem[]; total: number }>("/exercises", { method: "GET" }),
};

// --- Workout Session APIs ---
export const workoutApi = {
  create: (notes?: string) =>
    request<Workout>("/workouts/start", {
      method: "POST",
      body: JSON.stringify({ notes: notes || "Live Web Workout" }),
    }),

  list: (filters?: WorkoutHistoryFilter) => {
    const params = new URLSearchParams();
    if (filters?.exercise) params.append("exercise", filters.exercise);
    if (filters?.start_date) params.append("start_date", filters.start_date);
    if (filters?.end_date) params.append("end_date", filters.end_date);
    if (filters?.page_size) params.append("limit", filters.page_size.toString());
    const queryStr = params.toString() ? `?${params.toString()}` : "";
    return request<Workout[]>(`/workouts${queryStr}`, { method: "GET" });
  },

  getHistory: (filters?: WorkoutHistoryFilter) => {
    const params = new URLSearchParams();
    if (filters?.page) params.append("page", filters.page.toString());
    if (filters?.page_size) params.append("page_size", filters.page_size.toString());
    if (filters?.exercise) params.append("exercise", filters.exercise);
    if (filters?.start_date) params.append("start_date", filters.start_date);
    if (filters?.end_date) params.append("end_date", filters.end_date);
    if (filters?.status) params.append("status", filters.status);
    const queryStr = params.toString() ? `?${params.toString()}` : "";
    return request<PaginatedWorkouts>(`/workouts/history${queryStr}`, { method: "GET" });
  },

  get: (workoutId: string) => request<Workout>(`/workouts/${workoutId}`, { method: "GET" }),

  finish: (workoutId: string, notes?: string) =>
    request<Workout>(`/workouts/${workoutId}/finish`, {
      method: "POST",
      body: JSON.stringify({ notes }),
    }),
};

// --- Analytics APIs ---
export const analyticsApi = {
  getSummary: () => request<AnalyticsSummary>("/analytics/summary", { method: "GET" }),

  getExerciseAnalytics: (exercise: string) =>
    request<ExerciseAnalytics>(`/analytics/exercises/${encodeURIComponent(exercise)}`, {
      method: "GET",
    }),

  getTrends: (period: string = "all", exercise?: string) => {
    const params = new URLSearchParams({ period });
    if (exercise) params.append("exercise", exercise);
    return request<AnalyticsTrends>(`/analytics/trends?${params.toString()}`, {
      method: "GET",
    });
  },
};

// --- AI Coach Insights APIs ---
export const coachApi = {
  evaluate: (sessionId: string, targetFocus?: string) =>
    request<CoachingFeedback>("/coach/evaluate", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId, target_focus: targetFocus }),
    }),

  evaluateSession: (sessionId: string, targetFocus?: string) => {
    const params = targetFocus ? `?target_focus=${encodeURIComponent(targetFocus)}` : "";
    return request<CoachingFeedback>(`/coach/session/${sessionId}${params}`, {
      method: "POST",
    });
  },

  getSessionCoaching: (sessionId: string) =>
    request<CoachingFeedback>(`/coach/session/${sessionId}`, {
      method: "GET",
    }),
};

// Export convenience aliases for existing code
export const createWorkoutSession = (notes?: string) => workoutApi.create(notes);
export const getWorkoutSessions = () => workoutApi.list();
export const getWorkoutSession = (id: string) => workoutApi.get(id);
export const requestCoachFeedback = (sessionId: string) => coachApi.evaluate(sessionId);

