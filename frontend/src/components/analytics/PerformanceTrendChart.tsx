"use client";

import React, { useState } from "react";
import { TrendPoint } from "@/types";
import { TrendingUp, BarChart3, Calendar } from "lucide-react";

interface PerformanceTrendChartProps {
  points: TrendPoint[];
  isLoading?: boolean;
  onPeriodChange?: (period: string) => void;
  selectedPeriod?: string;
}

export const PerformanceTrendChart: React.FC<PerformanceTrendChartProps> = ({
  points = [],
  isLoading = false,
  onPeriodChange,
  selectedPeriod = "all",
}) => {
  const [metric, setMetric] = useState<"form_score" | "reps">("form_score");
  const [hoveredPoint, setHoveredPoint] = useState<TrendPoint | null>(null);

  if (isLoading) {
    return (
      <div className="p-6 rounded-3xl bg-gray-900/50 border border-gray-800 h-72 flex items-center justify-center animate-pulse">
        <div className="text-gray-500 text-xs">Loading performance trends...</div>
      </div>
    );
  }

  if (!points || points.length === 0) {
    return (
      <div className="p-8 rounded-3xl bg-gray-900/50 border border-gray-800 text-center flex flex-col items-center justify-center gap-3 h-72">
        <div className="w-10 h-10 rounded-2xl bg-gray-800 flex items-center justify-center text-gray-500">
          <BarChart3 className="w-5 h-5" />
        </div>
        <div className="text-sm font-semibold text-white">No Trend Telemetry Yet</div>
        <p className="text-xs text-gray-400 max-w-sm">
          Complete workout sessions with camera tracking to visualize longitudinal form integrity and volume trends.
        </p>
      </div>
    );
  }

  // SVG Chart Dimensions
  const svgWidth = 600;
  const svgHeight = 200;
  const paddingX = 40;
  const paddingY = 30;

  const dataValues = points.map((p) =>
    metric === "form_score" ? p.form_score : p.total_reps
  );

  const minVal = metric === "form_score" ? Math.max(0, Math.min(...dataValues, 60)) : 0;
  const maxVal = metric === "form_score" ? 100 : Math.max(...dataValues, 10);
  const range = maxVal - minVal || 1;

  // Compute SVG coordinate points
  const coords = points.map((p, index) => {
    const x =
      paddingX +
      (points.length > 1
        ? (index / (points.length - 1)) * (svgWidth - 2 * paddingX)
        : (svgWidth - 2 * paddingX) / 2);
    const val = metric === "form_score" ? p.form_score : p.total_reps;
    const y =
      svgHeight -
      paddingY -
      ((val - minVal) / range) * (svgHeight - 2 * paddingY);
    return { x, y, point: p, val };
  });

  // Construct SVG Path
  const pathD = coords.reduce(
    (acc, curr, idx) => `${acc} ${idx === 0 ? "M" : "L"} ${curr.x} ${curr.y}`,
    ""
  );

  // Area Fill Path
  const areaD =
    coords.length > 0
      ? `${pathD} L ${coords[coords.length - 1].x} ${svgHeight - paddingY} L ${coords[0].x} ${svgHeight - paddingY} Z`
      : "";

  return (
    <div className="p-6 rounded-3xl bg-gray-900/50 border border-gray-800 space-y-4">
      {/* Header with Metric & Period Toggles */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
            <TrendingUp className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-base font-bold text-white tracking-tight">
              Performance Trends
            </h3>
            <p className="text-[11px] text-gray-400">
              {points.length} recorded session{points.length !== 1 ? "s" : ""}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Metric Selector */}
          <div className="p-1 rounded-xl bg-gray-950/80 border border-gray-800 flex text-xs font-semibold">
            <button
              onClick={() => setMetric("form_score")}
              className={`px-3 py-1 rounded-lg transition-all cursor-pointer ${
                metric === "form_score"
                  ? "bg-emerald-500 text-black shadow-sm"
                  : "text-gray-400 hover:text-white"
              }`}
            >
              Form Score
            </button>
            <button
              onClick={() => setMetric("reps")}
              className={`px-3 py-1 rounded-lg transition-all cursor-pointer ${
                metric === "reps"
                  ? "bg-emerald-500 text-black shadow-sm"
                  : "text-gray-400 hover:text-white"
              }`}
            >
              Rep Volume
            </button>
          </div>

          {/* Period Selector */}
          {onPeriodChange && (
            <select
              value={selectedPeriod}
              onChange={(e) => onPeriodChange(e.target.value)}
              aria-label="Select time period"
              className="px-2.5 py-1.5 rounded-xl bg-gray-950/80 border border-gray-800 text-xs font-semibold text-gray-300 focus:outline-none focus:border-emerald-500"
            >
              <option value="7d">Last 7 Days</option>
              <option value="30d">Last 30 Days</option>
              <option value="all">All Time</option>
            </select>
          )}
        </div>
      </div>

      {/* SVG Line / Area Graph */}
      <div className="relative w-full overflow-hidden">
        <svg
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          className="w-full h-48 sm:h-56 overflow-visible"
        >
          <defs>
            <linearGradient id="trendGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#10B981" stopOpacity="0.35" />
              <stop offset="100%" stopColor="#10B981" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Grid lines */}
          <line
            x1={paddingX}
            y1={paddingY}
            x2={svgWidth - paddingX}
            y2={paddingY}
            stroke="#1f2937"
            strokeDasharray="4 4"
          />
          <line
            x1={paddingX}
            y1={(svgHeight - paddingY + paddingY) / 2}
            x2={svgWidth - paddingX}
            y2={(svgHeight - paddingY + paddingY) / 2}
            stroke="#1f2937"
            strokeDasharray="4 4"
          />
          <line
            x1={paddingX}
            y1={svgHeight - paddingY}
            x2={svgWidth - paddingX}
            y2={svgHeight - paddingY}
            stroke="#374151"
          />

          {/* Area Fill */}
          {areaD && <path d={areaD} fill="url(#trendGradient)" />}

          {/* Line Path */}
          {pathD && (
            <path
              d={pathD}
              fill="none"
              stroke="#10B981"
              strokeWidth="3"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )}

          {/* Interactive Data Keypoints */}
          {coords.map((c, i) => (
            <g key={i}>
              <circle
                cx={c.x}
                cy={c.y}
                r={hoveredPoint === c.point ? 6 : 4}
                fill="#10B981"
                stroke="#090d16"
                strokeWidth="2"
                className="cursor-pointer transition-all hover:scale-125"
                onMouseEnter={() => setHoveredPoint(c.point)}
                onMouseLeave={() => setHoveredPoint(null)}
              />
            </g>
          ))}
        </svg>

        {/* Hover Tooltip Overlay */}
        {hoveredPoint && (
          <div className="absolute top-2 right-2 p-2.5 rounded-xl bg-gray-950/90 border border-emerald-500/40 text-xs shadow-xl backdrop-blur-md animate-in fade-in duration-150">
            <div className="font-bold text-white capitalize">
              {hoveredPoint.exercise_name?.replace("_", " ") || "Workout"}
            </div>
            <div className="text-gray-400 text-[11px]">{hoveredPoint.date}</div>
            <div className="mt-1 flex items-center gap-2">
              <span className="text-emerald-400 font-bold font-mono">
                {metric === "form_score"
                  ? `${Math.round(hoveredPoint.form_score)}% Form`
                  : `${hoveredPoint.total_reps} Reps (${hoveredPoint.valid_reps} Valid)`}
              </span>
              <span className="text-gray-500">•</span>
              <span className="text-cyan-400 font-mono">
                {Math.round(hoveredPoint.duration_sec)}s
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
