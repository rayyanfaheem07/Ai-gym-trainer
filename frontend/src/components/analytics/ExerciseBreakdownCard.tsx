"use client";

import React from "react";
import Link from "next/link";
import { ExerciseBreakdownItem } from "@/types";
import { Dumbbell, Target, ChevronRight, Award, Activity } from "lucide-react";

interface ExerciseBreakdownCardProps {
  items: ExerciseBreakdownItem[];
  isLoading?: boolean;
}

export const ExerciseBreakdownCard: React.FC<ExerciseBreakdownCardProps> = ({
  items = [],
  isLoading = false,
}) => {
  if (isLoading) {
    return (
      <div className="p-6 rounded-3xl bg-gray-900/50 border border-gray-800 space-y-4 animate-pulse">
        <div className="h-6 w-48 bg-gray-800 rounded-lg"></div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[...Array(2)].map((_, i) => (
            <div key={i} className="h-32 bg-gray-800/60 rounded-2xl"></div>
          ))}
        </div>
      </div>
    );
  }

  if (!items || items.length === 0) {
    return (
      <div className="p-8 rounded-3xl bg-gray-900/50 border border-gray-800 text-center space-y-3">
        <div className="w-10 h-10 rounded-2xl bg-gray-800 flex items-center justify-center text-gray-500 mx-auto">
          <Target className="w-5 h-5" />
        </div>
        <div className="text-sm font-semibold text-white">No Exercise Volume Yet</div>
        <p className="text-xs text-gray-400 max-w-sm mx-auto">
          Train any of the 5 supported exercises in the Live Workout Arena to see per-movement statistics and form ratings.
        </p>
      </div>
    );
  }

  return (
    <div className="p-6 rounded-3xl bg-gray-900/50 border border-gray-800 space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-400">
            <Target className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-base font-bold text-white tracking-tight">
              Exercise Performance Breakdown
            </h3>
            <p className="text-[11px] text-gray-400">
              Biomechanical accuracy and repetition stats per exercise
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {items.map((ex) => (
          <div
            key={ex.exercise_name}
            className="p-4 rounded-2xl bg-gray-950/60 border border-gray-800/80 hover:border-cyan-500/30 transition-all space-y-3 flex flex-col justify-between"
          >
            <div>
              <div className="flex items-center justify-between mb-1">
                <h4 className="font-bold text-sm text-white capitalize flex items-center gap-2">
                  <Dumbbell className="w-4 h-4 text-cyan-400" />
                  {ex.exercise_name.replace("_", " ")}
                </h4>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-gray-800 text-gray-300">
                  {ex.total_sessions} session{ex.total_sessions !== 1 ? "s" : ""}
                </span>
              </div>

              <div className="grid grid-cols-3 gap-2 mt-3 text-center">
                <div className="p-2 rounded-xl bg-gray-900/80 border border-gray-800">
                  <div className="text-base font-black text-white">{ex.total_reps}</div>
                  <div className="text-[10px] text-gray-400">Total Reps</div>
                </div>

                <div className="p-2 rounded-xl bg-gray-900/80 border border-gray-800">
                  <div className="text-base font-black text-emerald-400">
                    {ex.accuracy_percentage}%
                  </div>
                  <div className="text-[10px] text-gray-400">Accuracy</div>
                </div>

                <div className="p-2 rounded-xl bg-gray-900/80 border border-gray-800">
                  <div className="text-base font-black text-cyan-400">
                    {ex.average_form_score > 0 ? `${Math.round(ex.average_form_score)}%` : "100%"}
                  </div>
                  <div className="text-[10px] text-gray-400">Avg Form</div>
                </div>
              </div>
            </div>

            <Link
              href={`/workout?exercise=${encodeURIComponent(ex.exercise_name)}`}
              className="w-full py-1.5 px-3 rounded-xl bg-gray-900 hover:bg-cyan-500/20 text-cyan-300 border border-cyan-500/20 text-[11px] font-semibold flex items-center justify-center gap-1 transition-all"
            >
              <span>Train {ex.exercise_name.replace("_", " ")}</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        ))}
      </div>
    </div>
  );
};
