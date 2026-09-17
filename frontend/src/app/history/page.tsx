"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useAuth } from "@/hooks/useAuth";
import { AnalyticsOverviewCards } from "@/components/analytics/AnalyticsOverviewCards";
import { WorkoutDetailModal } from "@/components/history/WorkoutDetailModal";
import { AnalyticsSummary, PaginatedWorkouts, Workout } from "@/types";
import { analyticsApi, workoutApi } from "@/lib/api";
import {
  Activity,
  Calendar,
  ChevronLeft,
  ChevronRight,
  Dumbbell,
  Filter,
  Loader2,
  Sparkles,
  ArrowRight,
  Eye,
} from "lucide-react";

const EXERCISE_OPTIONS = [
  { value: "", label: "All Exercises" },
  { value: "squat", label: "Squat" },
  { value: "pushup", label: "Push-up" },
  { value: "bicep_curl", label: "Bicep Curl" },
  { value: "lunge", label: "Lunge" },
  { value: "shoulder_press", label: "Shoulder Press" },
];

export default function HistoryPage() {
  const { isAuthenticated, isLoading: authLoading } = useAuth({ requireAuth: true });

  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [paginatedData, setPaginatedData] = useState<PaginatedWorkouts>({
    items: [],
    total: 0,
    page: 1,
    page_size: 10,
    total_pages: 1,
  });

  const [selectedExercise, setSelectedExercise] = useState<string>("");
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedWorkoutId, setSelectedWorkoutId] = useState<string | null>(null);

  const loadData = useCallback(async (page: number, exercise: string) => {
    try {
      setLoading(true);
      setError(null);

      const [summaryRes, historyRes] = await Promise.all([
        analyticsApi.getSummary(),
        workoutApi.getHistory({
          page,
          page_size: 10,
          exercise: exercise || undefined,
        }),
      ]);

      setSummary(summaryRes);
      setPaginatedData(historyRes);
    } catch (err: any) {
      setError(err.message || "Failed to load workout history from server.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isAuthenticated) {
      loadData(currentPage, selectedExercise);
    }
  }, [isAuthenticated, currentPage, selectedExercise, loadData]);

  const handleFilterChange = (newExercise: string) => {
    setSelectedExercise(newExercise);
    setCurrentPage(1);
  };

  if (authLoading || (!isAuthenticated && loading)) {
    return (
      <div className="min-h-[60vh] flex flex-col items-center justify-center gap-3 text-gray-400">
        <Loader2 className="w-8 h-8 animate-spin text-emerald-400" />
        <p className="text-sm">Loading history...</p>
      </div>
    );
  }

  const { items, total, page, total_pages } = paginatedData;

  return (
    <div className="space-y-8 animate-in fade-in duration-300">
      {/* Top Header */}
      <div>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight flex items-center gap-2.5">
          <Activity className="w-7 h-7 text-emerald-400" />
          Workout History & Performance Analytics
        </h1>
        <p className="text-xs sm:text-sm text-gray-400 mt-1">
          Historical record of all workouts, biomechanical accuracy ratings, and rep progression.
        </p>
      </div>

      {/* Aggregate Lifetime Summary Cards */}
      <AnalyticsOverviewCards summary={summary} isLoading={loading && !summary} />

      {/* Filter and Table Container */}
      <div className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-2xl bg-gray-900/60 border border-gray-800">
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-emerald-400" />
            <span className="text-xs font-bold text-white uppercase tracking-wider">
              Filter Workouts
            </span>
            <span className="text-xs text-gray-400">
              ({total} recorded workout{total !== 1 ? "s" : ""})
            </span>
          </div>

          <div className="flex items-center gap-3">
            <select
              value={selectedExercise}
              onChange={(e) => handleFilterChange(e.target.value)}
              aria-label="Filter by exercise"
              className="px-3 py-1.5 rounded-xl bg-gray-950 border border-gray-800 text-xs text-gray-200 focus:outline-none focus:border-emerald-500 font-medium"
            >
              {EXERCISE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Workouts List / Table */}
        {loading ? (
          <div className="p-12 text-center text-gray-400 bg-gray-900/30 rounded-3xl border border-gray-800 flex items-center justify-center gap-3">
            <Loader2 className="w-6 h-6 animate-spin text-emerald-400" />
            <span>Fetching workout logs from database...</span>
          </div>
        ) : error ? (
          <div className="p-6 text-center text-rose-400 bg-rose-950/20 rounded-3xl border border-rose-900/40 text-sm">
            {error}
          </div>
        ) : items.length === 0 ? (
          <div className="p-12 text-center bg-gray-900/40 rounded-3xl border border-gray-800 space-y-4">
            <div className="w-14 h-14 rounded-2xl bg-gray-800 flex items-center justify-center text-gray-400 mx-auto">
              <Dumbbell className="w-7 h-7" />
            </div>
            <div>
              <h3 className="text-white font-bold text-base">No Recorded Workouts Found</h3>
              <p className="text-gray-400 text-xs mt-1 max-w-sm mx-auto">
                {selectedExercise
                  ? `No workouts found for ${selectedExercise.replace("_", " ")}. Try selecting another filter or start a live workout.`
                  : "Completed sets in the Live Workout Arena will automatically appear here."}
              </p>
            </div>
            <Link
              href="/workout"
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-black text-xs font-bold transition-all"
            >
              <span>Start Workout Now</span>
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        ) : (
          <div className="space-y-3">
            {items.map((w) => {
              const sessions = w.exercise_sessions || [];
              const primarySession = sessions[0];
              const totalCompleted = sessions.reduce((sum, s) => sum + (s.completed_reps || 0), 0);
              const totalValid = sessions.reduce((sum, s) => sum + (s.valid_reps || 0), 0);

              const dateStr = new Date(w.started_at).toLocaleDateString(undefined, {
                month: "short",
                day: "numeric",
                year: "numeric",
              });
              const timeStr = new Date(w.started_at).toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
              });

              return (
                <div
                  key={w.id}
                  className="p-5 rounded-3xl bg-gray-900/50 border border-gray-800 hover:border-gray-700 transition-all flex flex-col md:flex-row md:items-center justify-between gap-4"
                >
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 shrink-0">
                      <Dumbbell className="w-6 h-6" />
                    </div>
                    <div>
                      <h4 className="font-bold text-base text-white capitalize">
                        {primarySession
                          ? primarySession.exercise_name.replace("_", " ")
                          : w.notes || "Live Training"}
                      </h4>
                      <div className="flex items-center gap-2 text-xs text-gray-400 mt-0.5">
                        <Calendar className="w-3.5 h-3.5" />
                        <span>
                          {dateStr} at {timeStr}
                        </span>
                        <span>•</span>
                        <span className="capitalize text-emerald-400 font-medium">
                          {w.status.replace("_", " ")}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center justify-between md:justify-end gap-6 text-xs">
                    <div>
                      <div className="font-bold text-white text-sm">
                        {totalValid} <span className="text-gray-400 font-normal">/ {totalCompleted}</span>
                      </div>
                      <div className="text-gray-400 font-medium">Valid Reps</div>
                    </div>

                    <div>
                      <div className="font-bold text-emerald-400 text-sm">
                        {(w.overall_form_score ?? 0) > 0 ? `${Math.round(w.overall_form_score!)}%` : "100%"}
                      </div>
                      <div className="text-gray-400 font-medium">Form Integrity</div>
                    </div>

                    <div>
                      <div className="font-bold text-purple-400 text-sm">
                        {(w.total_duration_sec ?? 0) >= 60
                          ? `${Math.round((w.total_duration_sec ?? 0) / 60)}m`
                          : `${Math.round(w.total_duration_sec ?? 0)}s`}
                      </div>
                      <div className="text-gray-400 font-medium">Duration</div>
                    </div>


                    <button
                      onClick={() => setSelectedWorkoutId(w.id)}
                      className="px-3.5 py-2 rounded-xl bg-gray-800 hover:bg-emerald-500 hover:text-black text-gray-200 text-xs font-semibold flex items-center gap-1.5 transition-all cursor-pointer"
                    >
                      <Eye className="w-3.5 h-3.5" />
                      <span>Inspect Details</span>
                    </button>
                  </div>
                </div>
              );
            })}

            {/* Pagination Bar */}
            {total_pages > 1 && (
              <div className="flex items-center justify-between pt-4 px-2">
                <div className="text-xs text-gray-400">
                  Page <strong className="text-white">{page}</strong> of{" "}
                  <strong className="text-white">{total_pages}</strong>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                    disabled={page <= 1}
                    className="p-2 rounded-xl bg-gray-900 border border-gray-800 text-gray-300 hover:text-white disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
                    title="Previous Page"
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </button>

                  <button
                    onClick={() => setCurrentPage((p) => Math.min(total_pages, p + 1))}
                    disabled={page >= total_pages}
                    className="p-2 rounded-xl bg-gray-900 border border-gray-800 text-gray-300 hover:text-white disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
                    title="Next Page"
                  >
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Workout Detail Modal */}
      {selectedWorkoutId && (
        <WorkoutDetailModal
          workoutId={selectedWorkoutId}
          onClose={() => setSelectedWorkoutId(null)}
        />
      )}
    </div>
  );
}
