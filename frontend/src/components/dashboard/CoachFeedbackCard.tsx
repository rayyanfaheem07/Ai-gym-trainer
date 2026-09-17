import React from "react";
import { Brain, CheckCircle, AlertTriangle, Sparkles } from "lucide-react";
import { CoachingFeedback } from "@/types";

interface CoachFeedbackCardProps {
  feedback: CoachingFeedback;
}

export const CoachFeedbackCard: React.FC<CoachFeedbackCardProps> = ({ feedback }) => {
  return (
    <div className="bg-gray-900/50 border border-gray-800 rounded-2xl p-6 relative overflow-hidden">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-10 h-10 rounded-xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400">
          <Brain className="w-5 h-5" />
        </div>
        <div>
          <h3 className="font-semibold text-lg text-white">AI Coach Analysis</h3>
          <span className="text-xs text-purple-400 font-medium">Model: {feedback.llm_model}</span>
        </div>
      </div>

      <p className="text-sm text-gray-300 leading-relaxed bg-gray-950/60 p-4 rounded-xl border border-gray-800/80 mb-6">
        &ldquo;{feedback.summary}&rdquo;
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="p-4 rounded-xl bg-emerald-950/20 border border-emerald-900/40">
          <div className="flex items-center gap-2 text-emerald-400 text-sm font-semibold mb-2">
            <CheckCircle className="w-4 h-4" />
            Key Strengths
          </div>
          <ul className="text-xs text-gray-300 space-y-1 list-disc list-inside">
            {feedback.strengths.map((s, idx) => (
              <li key={idx}>{s}</li>
            ))}
          </ul>
        </div>

        <div className="p-4 rounded-xl bg-amber-950/20 border border-amber-900/40">
          <div className="flex items-center gap-2 text-amber-400 text-sm font-semibold mb-2">
            <AlertTriangle className="w-4 h-4" />
            Form Improvements
          </div>
          <ul className="text-xs text-gray-300 space-y-1 list-disc list-inside">
            {feedback.areas_to_improve.map((item, idx) => (
              <li key={idx}>{item}</li>
            ))}
          </ul>
        </div>
      </div>

      {feedback.recovery_advice && (
        <div className="mt-4 p-3 rounded-xl bg-cyan-950/20 border border-cyan-900/30 text-xs text-cyan-300 flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-cyan-400 shrink-0" />
          <span><strong>Recovery Advice:</strong> {feedback.recovery_advice}</span>
        </div>
      )}
    </div>
  );
};
