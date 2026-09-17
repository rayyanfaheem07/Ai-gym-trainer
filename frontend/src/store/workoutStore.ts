import { create } from "zustand";
import { AnalysisResultResponse, ExerciseType } from "@/types";

interface WorkoutStore {
  activeSessionId: string | null;
  selectedExercise: ExerciseType;
  isStreaming: boolean;
  liveFeedback: AnalysisResultResponse | null;
  setActiveSessionId: (id: string | null) => void;
  setSelectedExercise: (exercise: ExerciseType) => void;
  setIsStreaming: (isStreaming: boolean) => void;
  setLiveFeedback: (feedback: AnalysisResultResponse | null) => void;
  reset: () => void;
}

export const useWorkoutStore = create<WorkoutStore>((set) => ({
  activeSessionId: null,
  selectedExercise: "squat",
  isStreaming: false,
  liveFeedback: null,
  setActiveSessionId: (id) => set({ activeSessionId: id }),
  setSelectedExercise: (exercise) => set({ selectedExercise: exercise }),
  setIsStreaming: (isStreaming) => set({ isStreaming }),
  setLiveFeedback: (feedback) => set({ liveFeedback: feedback }),
  reset: () =>
    set({
      activeSessionId: null,
      isStreaming: false,
      liveFeedback: null,
    }),
}));
