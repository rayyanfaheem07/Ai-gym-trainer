"use client";

import React from "react";
import Link from "next/link";
import { SessionSummary } from "@/types";
import { Award, CheckCircle2, Clock, Dumbbell, Sparkles, X, RotateCcw, ArrowRight } from "lucide-react";

interface SessionSummaryModalProps {
  summary: SessionSummary | null;
  onClose: () => void;
  onRestart: () => void;
}

export const SessionSummaryModal: React.FC<SessionSummaryModalProps> = ({
  summary,
  onClose,
  onRestart,
}) => {
  if (!summary) return null;

  const validPercentage =
    summary.total_reps > 0
      ? Math.round((summary.valid_reps / summary.total_reps) * 100)
      : 100;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-200">
      <div className="w-full max-w-lg p-6 sm:p-8 rounded-3xl bg-gray-900 border border-gray-800 shadow-2xl shadow-emerald-500/5 relative space-y-6">
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-5 right-5 p-2 rounded-xl bg-gray-800/80 hover:bg-gray-800 text-gray-400 hover:text-white transition-all"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Modal Header */}
        <div className="text-center space-y-2">
          <div className="w-14 h-14 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 mx-auto">
            <Award className="w-7 h-7" />
          </div>
          <h2 className="text-2xl font-bold text-white tracking-tight">Workout Session Complete</h2>
          <p className="text-xs text-gray-400">
            Exercise: <span className="text-emerald-400 font-bold capitalize">{summary.exercise.replace("_", " ")}</span>
          </p>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="p-3 rounded-2xl bg-gray-950/60 border border-gray-800 text-center">
            <div className="text-xs text-gray-400">Total Reps</div>
            <div className="text-2xl font-black text-white mt-1">{summary.total_reps}</div>
          </div>

          <div className="p-3 rounded-2xl bg-gray-950/60 border border-gray-800 text-center">
            <div className="text-xs text-gray-400">Valid Reps</div>
            <div className="text-2xl font-black text-emerald-400 mt-1">{summary.valid_reps}</div>
          </div>

          <div className="p-3 rounded-2xl bg-gray-950/60 border border-gray-800 text-center">
            <div className="text-xs text-gray-400">Avg Form</div>
            <div className="text-2xl font-black text-cyan-400 mt-1">
              {summary.average_form_score > 0 ? `${Math.round(summary.average_form_score)}%` : "100%"}
            </div>
          </div>

          <div className="p-3 rounded-2xl bg-gray-950/60 border border-gray-800 text-center">
            <div className="text-xs text-gray-400">Duration</div>
            <div className="text-2xl font-black text-purple-400 mt-1">
              {summary.duration_sec >= 60
                ? `${Math.round(summary.duration_sec / 60)}m`
                : `${Math.round(summary.duration_sec)}s`}
            </div>
          </div>
        </div>

        {/* Quality Assessment */}
        <div className="p-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-between text-xs">
          <div className="flex items-center gap-2 text-emerald-300 font-semibold">
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            <span>Repetition Accuracy Rate:</span>
          </div>
          <span className="font-bold text-white text-sm">{validPercentage}%</span>
        </div>

        {/* Action Buttons */}
        <div className="space-y-2.5 pt-2">
          <Link
            href="/history"
            className="w-full py-3 px-4 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-black font-bold text-sm shadow-lg shadow-emerald-500/20 transition-all flex items-center justify-center gap-2"
          >
            <Sparkles className="w-4 h-4" />
            <span>View AI Coach Feedback & History</span>
            <ArrowRight className="w-4 h-4" />
          </Link>

          <button
            onClick={onRestart}
            className="w-full py-2.5 px-4 rounded-xl bg-gray-800 hover:bg-gray-700 text-white font-semibold text-xs transition-all flex items-center justify-center gap-2 cursor-pointer"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Start Another Set</span>
          </button>
        </div>
      </div>
    </div>
  );
};
