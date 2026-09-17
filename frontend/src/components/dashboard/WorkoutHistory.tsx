"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { Workout } from "@/types";
import { workoutApi } from "@/lib/api";
import { Activity, Clock, Calendar, CheckCircle2, ChevronRight, Loader2, Dumbbell } from "lucide-react";

export const WorkoutHistory: React.FC = () => {
  const [workouts, setWorkouts] = useState<Workout[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchWorkouts() {
      try {
        setLoading(true);
        const data = await workoutApi.list();
        setWorkouts(data || []);
      } catch (err: any) {
        setError(err.message || "Failed to load workout history.");
      } finally {
        setLoading(false);
      }
    }
    fetchWorkouts();
  }, []);

  if (loading) {
    return (
      <div className="p-8 rounded-2xl bg-gray-900/40 border border-gray-800 flex items-center justify-center gap-3 text-gray-400">
        <Loader2 className="w-5 h-5 animate-spin text-cyan-400" />
        <span>Loading workout history...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 rounded-2xl bg-rose-950/20 border border-rose-900/40 text-rose-300 text-sm">
        {error}
      </div>
    );
  }

  if (workouts.length === 0) {
    return (
      <div className="p-10 rounded-2xl bg-gray-900/40 border border-gray-800 text-center space-y-3">
        <div className="w-12 h-12 rounded-2xl bg-gray-800 flex items-center justify-center text-gray-500 mx-auto">
          <Dumbbell className="w-6 h-6" />
        </div>
        <h3 className="font-semibold text-white text-sm">No Workouts Recorded Yet</h3>
        <p className="text-xs text-gray-400 max-w-sm mx-auto">
          Launch a live workout session with camera tracking to record form scores and repetition metrics.
        </p>
        <Link
          href="/workout"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-black text-xs font-semibold transition-all mt-2"
        >
          Start First Workout
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {workouts.slice(0, 5).map((workout) => {
        const sessionsCount = workout.exercise_sessions?.length || 0;
        const totalReps =
          workout.exercise_sessions?.reduce((sum, s) => sum + (s.completed_reps || 0), 0) || 0;
        const validReps =
          workout.exercise_sessions?.reduce((sum, s) => sum + (s.valid_reps || 0), 0) || 0;
        const formattedDate = new Date(workout.started_at).toLocaleDateString(undefined, {
          month: "short",
          day: "numeric",
          year: "numeric",
        });
        const formattedTime = new Date(workout.started_at).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        });

        return (
          <div
            key={workout.id}
            className="p-4 rounded-2xl bg-gray-900/50 border border-gray-800 hover:border-gray-700 transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-4"
          >
            <div className="flex items-center gap-3.5">
              <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
                <CheckCircle2 className="w-5 h-5" />
              </div>
              <div>
                <h4 className="font-semibold text-sm text-white">
                  {workout.notes || "Recorded Workout"}
                </h4>
                <div className="flex items-center gap-3 text-xs text-gray-400 mt-0.5">
                  <span className="flex items-center gap-1">
                    <Calendar className="w-3.5 h-3.5" />
                    {formattedDate} at {formattedTime}
                  </span>
                  <span>•</span>
                  <span>
                    {sessionsCount} exercise{sessionsCount !== 1 ? "s" : ""}
                  </span>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-6 text-xs">
              <div>
                <div className="font-bold text-white text-sm">{validReps} / {totalReps}</div>
                <div className="text-gray-400">Valid Reps</div>
              </div>

              {workout.overall_form_score !== null && workout.overall_form_score !== undefined && (
                <div>
                  <div className="font-bold text-emerald-400 text-sm">
                    {Math.round(workout.overall_form_score)}%
                  </div>
                  <div className="text-gray-400">Form Score</div>
                </div>
              )}

              <Link
                href="/history"
                className="p-2 rounded-xl bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-white transition-all"
                title="View Insights"
              >
                <ChevronRight className="w-4 h-4" />
              </Link>
            </div>
          </div>
        );
      })}
    </div>
  );
};
