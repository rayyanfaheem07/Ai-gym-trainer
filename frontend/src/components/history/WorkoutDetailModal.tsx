"use client";

import React, { useState, useEffect } from "react";
import { Workout, CoachingFeedback } from "@/types";
import { workoutApi, coachApi } from "@/lib/api";
import { CoachFeedbackCard } from "@/components/dashboard/CoachFeedbackCard";
import {
  X,
  Calendar,
  Clock,
  Activity,
  Award,
  Dumbbell,
  CheckCircle2,
  AlertTriangle,
  Brain,
  Loader2,
  ChevronDown,
  ChevronUp,
} from "lucide-react";

interface WorkoutDetailModalProps {
  workoutId: string;
  onClose: () => void;
}

export const WorkoutDetailModal: React.FC<WorkoutDetailModalProps> = ({
  workoutId,
  onClose,
}) => {
  const [workout, setWorkout] = useState<Workout | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [coachFeedback, setCoachFeedback] = useState<CoachingFeedback | null>(null);
  const [evaluatingCoach, setEvaluatingCoach] = useState(false);
  const [coachError, setCoachError] = useState<string | null>(null);
  const [expandedSessions, setExpandedSessions] = useState<Record<string, boolean>>({});

  useEffect(() => {
    async function loadDetail() {
      try {
        setLoading(true);
        const data = await workoutApi.get(workoutId);
        setWorkout(data);
        if (data.feedback) {
          setCoachFeedback(data.feedback);
        }
        // Expand first session by default
        if (data.exercise_sessions && data.exercise_sessions.length > 0) {
          setExpandedSessions({ [data.exercise_sessions[0].id]: true });
        }
      } catch (err: any) {
        setError(err.message || "Failed to load workout details.");
      } finally {
        setLoading(false);
      }
    }
    loadDetail();
  }, [workoutId]);

  const handleConsultCoach = async () => {
    try {
      setEvaluatingCoach(true);
      setCoachError(null);
      const res = await coachApi.evaluate(workoutId);
      setCoachFeedback(res);
    } catch (err: any) {
      setCoachError(err.message || "Failed to connect to AI Coach service.");
    } finally {
      setEvaluatingCoach(false);
    }
  };

  const toggleSession = (id: string) => {
    setExpandedSessions((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-200">
      <div className="w-full max-w-3xl max-h-[90vh] overflow-y-auto p-6 sm:p-8 rounded-3xl bg-gray-900 border border-gray-800 shadow-2xl relative space-y-6">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-5 right-5 p-2 rounded-xl bg-gray-800/80 hover:bg-gray-800 text-gray-400 hover:text-white transition-all cursor-pointer"
        >
          <X className="w-5 h-5" />
        </button>

        {loading ? (
          <div className="py-16 flex flex-col items-center justify-center gap-3 text-gray-400">
            <Loader2 className="w-8 h-8 animate-spin text-emerald-400" />
            <p className="text-sm">Loading detailed workout telemetry from database...</p>
          </div>
        ) : error || !workout ? (
          <div className="py-12 text-center text-rose-400 text-sm space-y-3">
            <AlertTriangle className="w-8 h-8 text-rose-400 mx-auto" />
            <p>{error || "Workout not found."}</p>
          </div>
        ) : (
          <>
            {/* Header */}
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <span className="px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 capitalize">
                  {workout.status.replace("_", " ")}
                </span>
                <span className="text-xs text-gray-400">
                  {new Date(workout.started_at).toLocaleDateString(undefined, {
                    weekday: "short",
                    month: "short",
                    day: "numeric",
                    year: "numeric",
                  })}{" "}
                  at{" "}
                  {new Date(workout.started_at).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </span>
              </div>
              <h2 className="text-2xl font-extrabold text-white tracking-tight">
                {workout.notes || "Workout Session Breakdown"}
              </h2>
            </div>

            {/* Quick Metrics Bar */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="p-3.5 rounded-2xl bg-gray-950/60 border border-gray-800 text-center">
                <div className="text-[11px] text-gray-400 font-medium">Duration</div>
                <div className="text-lg font-black text-purple-400 mt-0.5">
                  {(workout.total_duration_sec ?? 0) >= 60
                    ? `${Math.round((workout.total_duration_sec ?? 0) / 60)}m ${Math.round((workout.total_duration_sec ?? 0) % 60)}s`
                    : `${Math.round(workout.total_duration_sec ?? 0)}s`}
                </div>
              </div>

              <div className="p-3.5 rounded-2xl bg-gray-950/60 border border-gray-800 text-center">
                <div className="text-[11px] text-gray-400 font-medium">Form Integrity</div>
                <div className="text-lg font-black text-emerald-400 mt-0.5">
                  {(workout.overall_form_score ?? 0) > 0 ? `${Math.round(workout.overall_form_score!)}%` : "100%"}
                </div>
              </div>

              <div className="p-3.5 rounded-2xl bg-gray-950/60 border border-gray-800 text-center">
                <div className="text-[11px] text-gray-400 font-medium">Exercise Sets</div>
                <div className="text-lg font-black text-cyan-400 mt-0.5">
                  {workout.exercise_sessions?.length || 0}
                </div>
              </div>

              <div className="p-3.5 rounded-2xl bg-gray-950/60 border border-gray-800 text-center">
                <div className="text-[11px] text-gray-400 font-medium">Calories Burned</div>
                <div className="text-lg font-black text-amber-400 mt-0.5">
                  {Math.round(workout.total_calories || 0)} kcal
                </div>
              </div>
            </div>

            {/* Exercise Sessions & Reps List */}
            <div className="space-y-4">
              <h3 className="text-sm font-bold text-gray-200 uppercase tracking-wider flex items-center gap-2">
                <Dumbbell className="w-4 h-4 text-emerald-400" />
                Exercise Sets & Biomechanical Telemetry
              </h3>

              {(!workout.exercise_sessions || workout.exercise_sessions.length === 0) ? (
                <div className="p-6 rounded-2xl bg-gray-950/50 border border-gray-800 text-center text-xs text-gray-400">
                  No individual exercise sets recorded for this session.
                </div>
              ) : (
                workout.exercise_sessions.map((sess, sIdx) => {
                  const isExpanded = expandedSessions[sess.id] ?? false;
                  const reps = sess.results || sess.reps || [];

                  return (
                    <div
                      key={sess.id}
                      className="rounded-2xl bg-gray-950/60 border border-gray-800/80 overflow-hidden"
                    >
                      {/* Session Header Toggle */}
                      <button
                        onClick={() => toggleSession(sess.id)}
                        className="w-full p-4 flex items-center justify-between text-left hover:bg-gray-900/50 transition-colors cursor-pointer"
                      >
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 font-bold text-xs">
                            #{sess.session_order || sIdx + 1}
                          </div>
                          <div>
                            <div className="font-bold text-sm text-white capitalize">
                              {sess.exercise_name.replace("_", " ")}
                            </div>
                            <div className="text-xs text-gray-400">
                              {sess.valid_reps} valid / {sess.completed_reps} completed reps • Form: {Math.round(sess.average_form_score)}%
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center gap-3">
                          {(sess.average_tempo_sec ?? 0) > 0 && (
                            <span className="text-xs font-mono text-cyan-400 hidden sm:inline">
                              {sess.average_tempo_sec!.toFixed(1)}s tempo
                            </span>
                          )}
                          {isExpanded ? (
                            <ChevronUp className="w-4 h-4 text-gray-400" />
                          ) : (
                            <ChevronDown className="w-4 h-4 text-gray-400" />
                          )}
                        </div>
                      </button>

                      {/* Rep-by-rep Details */}
                      {isExpanded && (
                        <div className="p-4 border-t border-gray-800/80 space-y-2.5 bg-gray-950/30">
                          {reps.length === 0 ? (
                            <div className="text-xs text-gray-500 py-2">
                              No rep-by-rep angle telemetry recorded.
                            </div>
                          ) : (
                            <div className="space-y-2">
                              {reps.map((rep, rIdx) => (
                                <div
                                  key={rep.id || rIdx}
                                  className="p-3 rounded-xl bg-gray-900/60 border border-gray-800/80 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-2"
                                >
                                  <div className="flex items-center gap-2.5">
                                    <span
                                      className={`px-2 py-0.5 rounded-md font-bold text-[10px] ${
                                        rep.is_valid
                                          ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                                          : "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                                      }`}
                                    >
                                      Rep #{rep.rep_number} {rep.is_valid ? "VALID" : "INVALID"}
                                    </span>
                                    <span className="text-gray-300">
                                      Score:{" "}
                                      <strong className="text-white">
                                        {Math.round(rep.form_score)}%
                                      </strong>
                                    </span>
                                  </div>


                                  <div className="flex items-center gap-4 text-gray-400 font-mono text-[11px]">
                                    {rep.min_joint_angle !== null && rep.min_joint_angle !== undefined && (
                                      <span>
                                        Angle: {Math.round(rep.min_joint_angle)}° –{" "}
                                        {Math.round(rep.max_joint_angle || 0)}°
                                      </span>
                                    )}
                                    {rep.duration_sec > 0 && (
                                      <span>{rep.duration_sec.toFixed(1)}s</span>
                                    )}
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>

            {/* AI Coach Insights Section */}
            <div className="space-y-3 pt-2">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-gray-200 uppercase tracking-wider flex items-center gap-2">
                  <Brain className="w-4 h-4 text-purple-400" />
                  AI Coach Feedback
                </h3>

                <button
                  onClick={handleConsultCoach}
                  disabled={evaluatingCoach}
                  className="px-3 py-1.5 rounded-xl bg-purple-500/10 hover:bg-purple-500/20 text-purple-300 border border-purple-500/30 text-xs font-semibold flex items-center gap-1.5 transition-all cursor-pointer disabled:opacity-50"
                >
                  {evaluatingCoach ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Consulting AI Coach...</span>
                    </>
                  ) : (
                    <>
                      <Brain className="w-3.5 h-3.5" />
                      <span>{coachFeedback ? "Re-evaluate" : "Consult AI Coach"}</span>
                    </>
                  )}
                </button>
              </div>

              {coachError && (
                <div className="p-3.5 rounded-2xl bg-rose-950/20 border border-rose-900/30 text-xs text-rose-400 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
                  <span>{coachError}</span>
                </div>
              )}

              {coachFeedback ? (
                <CoachFeedbackCard feedback={coachFeedback} />
              ) : (
                <div className="p-5 rounded-2xl bg-purple-950/10 border border-purple-900/30 text-xs text-purple-300/80">
                  Click &ldquo;Consult AI Coach&rdquo; above to generate personalized post-workout recommendations powered by local Ollama AI.
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
};
