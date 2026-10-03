"use client";

import React from "react";
import Link from "next/link";
import { UserProfile } from "@/types";
import { Target, Award, Compass, MessageSquare, Settings2, Sparkles } from "lucide-react";

interface PersonalizationCardProps {
  profile: UserProfile | null;
  isLoading?: boolean;
}

export const PersonalizationCard: React.FC<PersonalizationCardProps> = ({
  profile,
  isLoading = false,
}) => {
  if (isLoading) {
    return (
      <div className="p-6 rounded-3xl bg-gray-900/40 border border-gray-800/80 animate-pulse h-36"></div>
    );
  }

  if (!profile) return null;

  const formatLabel = (str: string) =>
    str
      .replace(/_/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase());

  return (
    <div className="p-6 rounded-3xl bg-gradient-to-br from-gray-900/80 via-gray-900/50 to-emerald-950/20 border border-gray-800/80 backdrop-blur-md shadow-xl flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
      <div className="space-y-3">
        <div className="flex items-center gap-2 text-xs font-semibold text-emerald-400">
          <Sparkles className="w-4 h-4" />
          <span>Active Athlete Training Profile</span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 sm:gap-6">
          <div className="space-y-1">
            <div className="flex items-center gap-1.5 text-xs text-gray-400">
              <Target className="w-3.5 h-3.5 text-emerald-400" />
              <span>Goal</span>
            </div>
            <p className="text-sm font-bold text-white">{formatLabel(profile.fitness_goal)}</p>
          </div>

          <div className="space-y-1">
            <div className="flex items-center gap-1.5 text-xs text-gray-400">
              <Award className="w-3.5 h-3.5 text-cyan-400" />
              <span>Level</span>
            </div>
            <p className="text-sm font-bold text-white">{formatLabel(profile.experience_level)}</p>
          </div>

          <div className="space-y-1">
            <div className="flex items-center gap-1.5 text-xs text-gray-400">
              <Compass className="w-3.5 h-3.5 text-indigo-400" />
              <span>Focus</span>
            </div>
            <p className="text-sm font-bold text-white">{formatLabel(profile.preferred_focus)}</p>
          </div>

          <div className="space-y-1">
            <div className="flex items-center gap-1.5 text-xs text-gray-400">
              <MessageSquare className="w-3.5 h-3.5 text-amber-400" />
              <span>Style</span>
            </div>
            <p className="text-sm font-bold text-white">{formatLabel(profile.coaching_style)}</p>
          </div>
        </div>
      </div>

      <Link
        href="/profile"
        className="px-4 py-2 rounded-xl bg-gray-800/80 hover:bg-gray-700/80 text-gray-200 hover:text-white border border-gray-700/70 text-xs font-semibold flex items-center gap-2 transition-all flex-shrink-0"
      >
        <Settings2 className="w-3.5 h-3.5" />
        <span>Customize Coaching</span>
      </Link>
    </div>
  );
};
