"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { ExerciseItem } from "@/types";
import { exerciseApi } from "@/lib/api";
import { Dumbbell, Target, ChevronRight, Loader2, Sparkles } from "lucide-react";

export const ExerciseCatalog: React.FC = () => {
  const [exercises, setExercises] = useState<ExerciseItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadCatalog() {
      try {
        setLoading(true);
        const data = await exerciseApi.list();
        setExercises(data.exercises || []);
      } catch (err: any) {
        setError(err.message || "Failed to load exercise catalog.");
      } finally {
        setLoading(false);
      }
    }
    loadCatalog();
  }, []);

  if (loading) {
    return (
      <div className="p-8 rounded-2xl bg-gray-900/40 border border-gray-800 flex items-center justify-center gap-3 text-gray-400">
        <Loader2 className="w-5 h-5 animate-spin text-emerald-400" />
        <span>Loading exercises from AI server...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 rounded-2xl bg-rose-950/20 border border-rose-900/40 text-rose-300 text-sm">
        {error}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold text-white flex items-center gap-2">
          <Dumbbell className="w-5 h-5 text-emerald-400" />
          Supported Exercises ({exercises.length})
        </h2>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {exercises.map((ex) => (
          <div
            key={ex.id}
            className="p-5 rounded-2xl bg-gray-900/50 border border-gray-800 hover:border-emerald-500/40 transition-all flex flex-col justify-between group"
          >
            <div>
              <div className="flex items-start justify-between gap-2 mb-2">
                <h3 className="font-bold text-base text-white group-hover:text-emerald-400 transition-colors">
                  {ex.name}
                </h3>
                <span className="px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-gray-800 text-gray-300 capitalize border border-gray-700">
                  {ex.difficulty || "All Levels"}
                </span>
              </div>

              <div className="flex items-center gap-1.5 text-xs text-cyan-400 font-medium mb-3">
                <Target className="w-3.5 h-3.5" />
                <span>Target: {ex.primary_target}</span>
              </div>

              {ex.instructions && ex.instructions.length > 0 && (
                <ul className="text-xs text-gray-400 space-y-1 mb-4 list-disc list-inside line-clamp-2">
                  {ex.instructions.map((inst, idx) => (
                    <li key={idx}>{inst}</li>
                  ))}
                </ul>
              )}
            </div>

            <Link
              href={`/workout?exercise=${encodeURIComponent(ex.id)}`}
              className="mt-2 w-full py-2 px-3 rounded-xl bg-gray-800 hover:bg-emerald-500 text-gray-200 hover:text-black text-xs font-semibold transition-all flex items-center justify-center gap-1.5"
            >
              <span>Train {ex.name}</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        ))}
      </div>
    </div>
  );
};
