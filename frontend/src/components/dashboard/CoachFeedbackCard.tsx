import React from "react";
import { Brain, CheckCircle, AlertTriangle, Sparkles, Target, ShieldAlert, Cpu } from "lucide-react";
import { CoachingFeedback } from "@/types";

interface CoachFeedbackCardProps {
  feedback: CoachingFeedback;
}

export const CoachFeedbackCard: React.FC<CoachFeedbackCardProps> = ({ feedback }) => {
  const isFallback =
    feedback.is_fallback ||
    (feedback.llm_model && feedback.llm_model.toLowerCase().includes("fallback"));

  return (
    <div className="bg-gray-900/60 border border-gray-800 rounded-3xl p-6 sm:p-7 relative overflow-hidden shadow-xl space-y-5">
      {/* Header with Provider / Fallback Badge */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2 border-b border-gray-800/80">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-2xl flex items-center justify-center ${
            isFallback
              ? "bg-amber-500/10 border border-amber-500/20 text-amber-400"
              : "bg-purple-500/10 border border-purple-500/20 text-purple-400"
          }`}>
            {isFallback ? <Cpu className="w-5 h-5" /> : <Brain className="w-5 h-5" />}
          </div>
          <div>
            <h3 className="font-bold text-lg text-white tracking-tight">AI Movement Coach</h3>
            <span className="text-xs text-gray-400 font-mono">
              Engine: <strong className={isFallback ? "text-amber-400" : "text-purple-300"}>{feedback.llm_model}</strong>
            </span>
          </div>
        </div>

        <div>
          {isFallback ? (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-500/10 border border-amber-500/20 text-amber-400">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400"></span>
              Deterministic Rule Engine
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-purple-500/10 border border-purple-500/20 text-purple-300">
              <span className="w-1.5 h-1.5 rounded-full bg-purple-400 animate-pulse"></span>
              Ollama LLM Grounded
            </span>
          )}
        </div>
      </div>

      {/* Fallback info banner if applicable */}
      {isFallback && (
        <div className="p-3.5 rounded-2xl bg-amber-950/20 border border-amber-900/30 text-xs text-amber-300/90 flex items-start gap-2.5">
          <Cpu className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
          <span>
            Local Ollama LLM is currently offline or unreachable. Coaching feedback was generated using verified deterministic telemetry rules.
          </span>
        </div>
      )}

      {/* Executive Performance Summary */}
      <div className="space-y-1.5">
        <div className="text-[11px] font-bold text-gray-400 uppercase tracking-wider">
          Performance Summary
        </div>
        <p className="text-sm text-gray-200 leading-relaxed bg-gray-950/70 p-4 rounded-2xl border border-gray-800/80">
          &ldquo;{feedback.summary}&rdquo;
        </p>
      </div>

      {/* Grid: Strengths & Form Corrections */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Strengths */}
        <div className="p-4 rounded-2xl bg-emerald-950/20 border border-emerald-900/40 space-y-2.5">
          <div className="flex items-center gap-2 text-emerald-400 text-xs font-bold uppercase tracking-wider">
            <CheckCircle className="w-4 h-4 text-emerald-400" />
            Key Movement Strengths
          </div>
          {feedback.strengths && feedback.strengths.length > 0 ? (
            <ul className="text-xs text-gray-300 space-y-1.5 list-disc list-inside">
              {feedback.strengths.map((s, idx) => (
                <li key={idx} className="leading-snug">{s}</li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-gray-400">Consistent movement engagement recorded.</p>
          )}
        </div>

        {/* Areas to Improve */}
        <div className="p-4 rounded-2xl bg-amber-950/20 border border-amber-900/40 space-y-2.5">
          <div className="flex items-center gap-2 text-amber-400 text-xs font-bold uppercase tracking-wider">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            Form Improvements & Corrections
          </div>
          {feedback.areas_to_improve && feedback.areas_to_improve.length > 0 ? (
            <ul className="text-xs text-gray-300 space-y-1.5 list-disc list-inside">
              {feedback.areas_to_improve.map((item, idx) => (
                <li key={idx} className="leading-snug">{item}</li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-gray-400">No major biomechanical faults detected.</p>
          )}
        </div>
      </div>

      {/* Next Session Focus */}
      {feedback.next_session_focus && (
        <div className="p-3.5 rounded-2xl bg-purple-950/20 border border-purple-900/30 text-xs text-purple-200 flex items-start gap-2.5">
          <Target className="w-4 h-4 text-purple-400 shrink-0 mt-0.5" />
          <div>
            <strong className="text-purple-300">Next Session Focus:</strong> {feedback.next_session_focus}
          </div>
        </div>
      )}

      {/* Safety Note */}
      {feedback.safety_note && (
        <div className="p-3.5 rounded-2xl bg-blue-950/20 border border-blue-900/30 text-xs text-blue-200 flex items-start gap-2.5">
          <ShieldAlert className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
          <div>
            <strong className="text-blue-300">Safety Cue:</strong> {feedback.safety_note}
          </div>
        </div>
      )}

      {/* Recovery Advice (if separate or general) */}
      {feedback.recovery_advice && !feedback.next_session_focus && (
        <div className="p-3.5 rounded-2xl bg-cyan-950/20 border border-cyan-900/30 text-xs text-cyan-300 flex items-start gap-2.5">
          <Sparkles className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
          <div>
            <strong className="text-white">Recovery Advice:</strong> {feedback.recovery_advice}
          </div>
        </div>
      )}
    </div>
  );
};
