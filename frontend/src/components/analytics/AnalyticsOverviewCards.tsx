"use client";

import React from "react";
import { AnalyticsSummary } from "@/types";
import { Award, Activity, Clock, Target, Dumbbell } from "lucide-react";

interface AnalyticsOverviewCardsProps {
  summary: AnalyticsSummary | null;
  isLoading?: boolean;
}

export const AnalyticsOverviewCards: React.FC<AnalyticsOverviewCardsProps> = ({
  summary,
  isLoading = false,
}) => {
  if (isLoading) {
    return (
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 animate-pulse">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-28 rounded-3xl bg-gray-900/40 border border-gray-800"></div>
        ))}
      </div>
    );
  }

  const totalWorkouts = summary?.total_workouts ?? 0;
  const totalReps = summary?.total_reps ?? 0;
  const validReps = summary?.total_valid_reps ?? 0;
  const avgFormScore = summary?.average_form_score ? Math.round(summary.average_form_score) : 0;
  const durationSec = summary?.total_duration_sec ?? 0;
  const accuracyPct = summary?.valid_rep_percentage ?? 100;

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

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {/* 1. Total Workouts */}
      <div className="p-5 rounded-3xl bg-gray-900/50 border border-gray-800 backdrop-blur-md flex items-center gap-4 hover:border-gray-700 transition-all">
        <div className="p-3.5 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 shrink-0">
          <Dumbbell className="w-6 h-6" />
        </div>
        <div>
          <div className="text-2xl sm:text-3xl font-black text-white tracking-tight">
            {totalWorkouts}
          </div>
          <div className="text-xs text-gray-400 font-medium mt-0.5">Total Workouts</div>
        </div>
      </div>

      {/* 2. Repetition Volume & Accuracy */}
      <div className="p-5 rounded-3xl bg-gray-900/50 border border-gray-800 backdrop-blur-md flex items-center gap-4 hover:border-gray-700 transition-all">
        <div className="p-3.5 rounded-2xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 shrink-0">
          <Activity className="w-6 h-6" />
        </div>
        <div>
          <div className="text-2xl sm:text-3xl font-black text-white tracking-tight">
            {validReps} <span className="text-xs font-normal text-gray-400">/ {totalReps}</span>
          </div>
          <div className="text-xs text-gray-400 font-medium mt-0.5">
            Valid Reps ({accuracyPct}%)
          </div>
        </div>
      </div>

      {/* 3. Average Form Score */}
      <div className="p-5 rounded-3xl bg-gray-900/50 border border-gray-800 backdrop-blur-md flex items-center gap-4 hover:border-gray-700 transition-all">
        <div className="p-3.5 rounded-2xl bg-amber-500/10 border border-amber-500/20 text-amber-400 shrink-0">
          <Award className="w-6 h-6" />
        </div>
        <div>
          <div className="text-2xl sm:text-3xl font-black text-white tracking-tight">
            {avgFormScore > 0 ? `${avgFormScore}%` : "—"}
          </div>
          <div className="text-xs text-gray-400 font-medium mt-0.5">Avg Form Integrity</div>
        </div>
      </div>

      {/* 4. Total Training Time */}
      <div className="p-5 rounded-3xl bg-gray-900/50 border border-gray-800 backdrop-blur-md flex items-center gap-4 hover:border-gray-700 transition-all">
        <div className="p-3.5 rounded-2xl bg-purple-500/10 border border-purple-500/20 text-purple-400 shrink-0">
          <Clock className="w-6 h-6" />
        </div>
        <div>
          <div className="text-2xl sm:text-3xl font-black text-white tracking-tight">
            {formatDuration(durationSec)}
          </div>
          <div className="text-xs text-gray-400 font-medium mt-0.5">Total Training Time</div>
        </div>
      </div>
    </div>
  );
};
