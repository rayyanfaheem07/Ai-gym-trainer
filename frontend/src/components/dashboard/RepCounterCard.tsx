import React from "react";
import { CheckCircle2, XCircle, Gauge, Flame } from "lucide-react";

interface RepCounterCardProps {
  repCount: number;
  validReps: number;
  invalidReps: number;
  formScore: number;
  stage: string;
  primaryAngle: number;
}

export const RepCounterCard: React.FC<RepCounterCardProps> = ({
  repCount,
  validReps,
  invalidReps,
  formScore,
  stage,
  primaryAngle,
}) => {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 w-full">
      <div className="bg-gray-900/60 border border-gray-800 rounded-2xl p-4 flex flex-col justify-between">
        <span className="text-xs uppercase font-semibold text-gray-400">Total Reps</span>
        <div className="text-4xl font-extrabold text-white mt-2">{repCount}</div>
        <span className="text-xs text-emerald-400 mt-1 font-medium">{stage}</span>
      </div>

      <div className="bg-gray-900/60 border border-gray-800 rounded-2xl p-4 flex flex-col justify-between">
        <div className="flex items-center justify-between">
          <span className="text-xs uppercase font-semibold text-gray-400">Valid / Invalid</span>
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
        </div>
        <div className="text-2xl font-bold mt-2">
          <span className="text-emerald-400">{validReps}</span>
          <span className="text-gray-500 mx-1">/</span>
          <span className="text-rose-400">{invalidReps}</span>
        </div>
        <span className="text-xs text-gray-500 mt-1">Accuracy</span>
      </div>

      <div className="bg-gray-900/60 border border-gray-800 rounded-2xl p-4 flex flex-col justify-between">
        <div className="flex items-center justify-between">
          <span className="text-xs uppercase font-semibold text-gray-400">Form Score</span>
          <Gauge className="w-4 h-4 text-cyan-400" />
        </div>
        <div className="text-3xl font-extrabold text-cyan-400 mt-2">
          {formScore.toFixed(0)}%
        </div>
        <span className="text-xs text-gray-500 mt-1">Biomechanics</span>
      </div>

      <div className="bg-gray-900/60 border border-gray-800 rounded-2xl p-4 flex flex-col justify-between">
        <div className="flex items-center justify-between">
          <span className="text-xs uppercase font-semibold text-gray-400">Joint Angle</span>
          <Flame className="w-4 h-4 text-amber-400" />
        </div>
        <div className="text-3xl font-extrabold text-amber-400 mt-2">
          {primaryAngle.toFixed(0)}°
        </div>
        <span className="text-xs text-gray-500 mt-1">Live Primary Joint</span>
      </div>
    </div>
  );
};
