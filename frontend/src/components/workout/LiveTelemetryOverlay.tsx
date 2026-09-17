"use client";

import React from "react";
import { AnalysisResultResponse } from "@/types";
import { WSConnectionStatus } from "@/hooks/useWebSocket";
import { Activity, AlertTriangle, CheckCircle, Volume2, Wifi, WifiOff } from "lucide-react";

interface LiveTelemetryOverlayProps {
  analysis: AnalysisResultResponse | null;
  wsStatus: WSConnectionStatus;
  isStreaming: boolean;
  exerciseName: string;
}

export const LiveTelemetryOverlay: React.FC<LiveTelemetryOverlayProps> = ({
  analysis,
  wsStatus,
  isStreaming,
  exerciseName,
}) => {
  const formScore = analysis ? Math.round(analysis.form_score) : 100;
  const repCount = analysis ? analysis.rep_count : 0;
  const validReps = analysis ? analysis.valid_reps : 0;
  const stage = analysis?.stage ? analysis.stage.replace("_", " ").toUpperCase() : "READY";
  const warnings = analysis?.warnings || [];
  const audioCue = analysis?.audio_cue || (analysis?.feedback && analysis.feedback[0]);

  // Color coding based on form score
  const getScoreColor = (score: number) => {
    if (score >= 85) return "text-emerald-400 border-emerald-500/30 bg-emerald-500/10";
    if (score >= 70) return "text-amber-400 border-amber-500/30 bg-amber-500/10";
    return "text-rose-400 border-rose-500/30 bg-rose-500/10";
  };

  const getScoreGradient = (score: number) => {
    if (score >= 85) return "from-emerald-500 to-teal-400";
    if (score >= 70) return "from-amber-500 to-yellow-400";
    return "from-rose-500 to-red-400";
  };

  return (
    <div className="space-y-4">
      {/* Status Bar */}
      <div className="flex items-center justify-between px-4 py-2.5 rounded-2xl bg-gray-900/60 border border-gray-800 backdrop-blur-md">
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">Exercise:</span>
          <span className="text-xs font-bold text-white uppercase tracking-wide">
            {exerciseName.replace("_", " ")}
          </span>
        </div>

        <div className="flex items-center gap-2">
          <div
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold border ${
              wsStatus === "connected"
                ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/20"
                : wsStatus === "connecting"
                ? "text-amber-400 bg-amber-500/10 border-amber-500/20"
                : "text-rose-400 bg-rose-500/10 border-rose-500/20"
            }`}
          >
            {wsStatus === "connected" ? (
              <>
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                <span>Live AI Connected</span>
              </>
            ) : wsStatus === "connecting" ? (
              <>
                <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-ping"></span>
                <span>Connecting...</span>
              </>
            ) : (
              <>
                <WifiOff className="w-3 h-3" />
                <span>Disconnected</span>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Primary HUD Cards */}
      <div className="grid grid-cols-3 gap-3">
        {/* Rep Counter */}
        <div className="p-4 rounded-2xl bg-gray-900/60 border border-gray-800 backdrop-blur-md text-center flex flex-col justify-between">
          <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">
            Reps
          </span>
          <div className="my-1">
            <span className="text-4xl sm:text-5xl font-black text-white tracking-tight">
              {repCount}
            </span>
          </div>
          <span className="text-[10px] text-emerald-400 font-medium">
            {validReps} Valid
          </span>
        </div>

        {/* Form Score Gauge */}
        <div className="p-4 rounded-2xl bg-gray-900/60 border border-gray-800 backdrop-blur-md text-center flex flex-col justify-between">
          <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">
            Form Score
          </span>
          <div className="my-1">
            <span
              className={`text-4xl sm:text-5xl font-black tracking-tight ${
                formScore >= 85
                  ? "text-emerald-400"
                  : formScore >= 70
                  ? "text-amber-400"
                  : "text-rose-400"
              }`}
            >
              {analysis ? `${formScore}%` : "—"}
            </span>
          </div>
          <div className="w-full bg-gray-800 rounded-full h-1.5 overflow-hidden">
            <div
              className={`h-full bg-gradient-to-r ${getScoreGradient(formScore)} transition-all duration-300`}
              style={{ width: `${formScore}%` }}
            ></div>
          </div>
        </div>

        {/* Movement Stage FSM */}
        <div className="p-4 rounded-2xl bg-gray-900/60 border border-gray-800 backdrop-blur-md text-center flex flex-col justify-between">
          <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">
            Phase / Stage
          </span>
          <div className="my-1">
            <span className="inline-block px-2.5 py-1 rounded-xl bg-gray-800 border border-gray-700 text-cyan-300 font-bold text-xs sm:text-sm tracking-wide">
              {stage}
            </span>
          </div>
          <span className="text-[10px] text-gray-500 font-medium truncate">
            {analysis?.primary_angle ? `${Math.round(analysis.primary_angle)}° Joint Angle` : "Tracking pose..."}
          </span>
        </div>
      </div>

      {/* Audio/Visual Live Coaching Cue */}
      {audioCue && isStreaming && (
        <div className="p-3.5 rounded-2xl bg-gradient-to-r from-emerald-500/10 via-cyan-500/10 to-transparent border border-emerald-500/30 flex items-center gap-3">
          <div className="p-2 rounded-xl bg-emerald-500/20 text-emerald-400">
            <Volume2 className="w-4 h-4" />
          </div>
          <div className="flex-1">
            <div className="text-[10px] font-bold text-emerald-400 uppercase tracking-wider">
              Live Coach Cue
            </div>
            <div className="text-sm font-semibold text-white">{audioCue}</div>
          </div>
        </div>
      )}

      {/* Form Warnings / Issues */}
      {warnings.length > 0 && isStreaming && (
        <div className="p-3.5 rounded-2xl bg-amber-500/10 border border-amber-500/30 space-y-1">
          <div className="flex items-center gap-1.5 text-xs font-bold text-amber-400">
            <AlertTriangle className="w-4 h-4" />
            <span>Form Correction Needed</span>
          </div>
          <ul className="text-xs text-amber-200/90 pl-5 list-disc space-y-0.5">
            {warnings.map((warn, idx) => (
              <li key={idx}>{warn}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Joint Angles Telemetry */}
      {analysis?.current_angles && Object.keys(analysis.current_angles).length > 0 && (
        <div className="p-3.5 rounded-2xl bg-gray-900/40 border border-gray-800 text-xs">
          <div className="text-gray-400 font-semibold mb-2 flex items-center justify-between">
            <span>Biomechanical Joint Angles</span>
            <span className="text-cyan-400 font-mono text-[11px]">
              {analysis.rep_duration_sec > 0 ? `${analysis.rep_duration_sec.toFixed(1)}s rep tempo` : ""}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {Object.entries(analysis.current_angles).map(([joint, angle]) => (
              <div
                key={joint}
                className="px-2.5 py-1.5 rounded-xl bg-gray-950/60 border border-gray-800/80 flex items-center justify-between"
              >
                <span className="text-gray-400 capitalize">{joint.replace("_", " ")}:</span>
                <span className="text-white font-mono font-bold">{Math.round(angle)}°</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
