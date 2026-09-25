"use client";

import React, { useState, useEffect } from "react";
import { useAuth } from "@/hooks/useAuth";
import { profileApi } from "@/lib/api";
import {
  CoachingStyle,
  ExperienceLevel,
  FitnessGoal,
  PreferredFocus,
  UserProfile,
} from "@/types";
import {
  Target,
  Award,
  Compass,
  MessageSquare,
  Save,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Dumbbell,
  Flame,
  Activity,
  HeartPulse,
  Shield,
  Zap,
} from "lucide-react";

export default function ProfilePage() {
  const { user, isAuthenticated, isLoading: authLoading } = useAuth({ requireAuth: true });

  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Form selections
  const [fitnessGoal, setFitnessGoal] = useState<FitnessGoal>("general_fitness");
  const [experienceLevel, setExperienceLevel] = useState<ExperienceLevel>("beginner");
  const [preferredFocus, setPreferredFocus] = useState<PreferredFocus>("form");
  const [coachingStyle, setCoachingStyle] = useState<CoachingStyle>("supportive");

  useEffect(() => {
    if (!isAuthenticated) return;

    async function loadProfile() {
      try {
        setLoading(true);
        setErrorMsg(null);
        const res = await profileApi.get();
        setProfile(res);
        setFitnessGoal(res.fitness_goal);
        setExperienceLevel(res.experience_level);
        setPreferredFocus(res.preferred_focus);
        setCoachingStyle(res.coaching_style);
      } catch (err: any) {
        setErrorMsg(err.message || "Failed to load athlete profile.");
      } finally {
        setLoading(false);
      }
    }

    loadProfile();
  }, [isAuthenticated]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSaving(true);
      setErrorMsg(null);
      setSuccessMsg(null);

      const updated = await profileApi.update({
        fitness_goal: fitnessGoal,
        experience_level: experienceLevel,
        preferred_focus: preferredFocus,
        coaching_style: coachingStyle,
      });

      setProfile(updated);
      setSuccessMsg("Personalization preferences updated successfully!");
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to update profile.");
    } finally {
      setSaving(false);
    }
  };

  if (authLoading || (loading && !profile)) {
    return (
      <div className="min-h-[60vh] flex flex-col items-center justify-center gap-3 text-gray-400">
        <Loader2 className="w-8 h-8 animate-spin text-emerald-400" />
        <p className="text-sm">Loading athlete profile & personalization...</p>
      </div>
    );
  }

  const fitnessGoals = [
    { id: "general_fitness", label: "General Fitness", desc: "Overall health, mobility, and functional movement", icon: Activity },
    { id: "strength", label: "Max Strength", desc: "Heavy mechanical load and joint stability", icon: Dumbbell },
    { id: "muscle_gain", label: "Hypertrophy / Muscle Gain", desc: "Time under tension and eccentric control", icon: Zap },
    { id: "fat_loss", label: "Fat Loss / Conditioning", desc: "High density work and consistent cadence", icon: Flame },
    { id: "endurance", label: "Muscular Endurance", desc: "Repetition stamina and fatigue resistance", icon: HeartPulse },
  ];

  const experienceLevels = [
    { id: "beginner", label: "Beginner", desc: "New to structured lifting; emphasizes fundamentals & simple cues" },
    { id: "intermediate", label: "Intermediate", desc: "Consistent training background; focuses on nuance and progression" },
    { id: "advanced", label: "Advanced", desc: "Deep biomechanical familiarity; demands technical cues and fine tolerance" },
  ];

  const preferredFocusOptions = [
    { id: "form", label: "Form Precision", desc: "Strict joint angle execution and fault elimination" },
    { id: "strength", label: "Progressive Overload", desc: "Weight and mechanical effort progression" },
    { id: "consistency", label: "Movement Consistency", desc: "Cadence, repetition tempo, and stamina regularity" },
    { id: "endurance", label: "Volume & Stamina", desc: "Extended set duration and repetition count" },
    { id: "balanced", label: "Balanced Development", desc: "Harmonious combination of technique and output" },
  ];

  const coachingStyles = [
    { id: "supportive", label: "Supportive & Encouraging", desc: "Positive reinforcement with clear, constructive pointers" },
    { id: "concise", label: "Concise & Direct", desc: "Brief, punchy bullet points and immediate actionable cues" },
    { id: "detailed", label: "Detailed & Instructive", desc: "Comprehensive step-by-step biomechanical breakdowns" },
    { id: "technical", label: "Technical & Analytical", desc: "Rigorous kinematic terminology and anatomical angles" },
  ];

  return (
    <div className="max-w-4xl mx-auto space-y-8 animate-in fade-in duration-300">
      {/* Header Banner */}
      <div className="p-6 sm:p-8 rounded-3xl bg-gradient-to-r from-emerald-950/40 via-gray-900/60 to-cyan-950/40 border border-gray-800/80 backdrop-blur-md shadow-xl flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-semibold mb-2">
            <Shield className="w-3.5 h-3.5" />
            Athlete Personalization
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
            Coaching & Fitness Profile
          </h1>
          <p className="text-sm text-gray-400 mt-1">
            Tailor the AI Coach&apos;s feedback depth, pedagogical style, and workout emphasis to your specific training goals.
          </p>
        </div>
      </div>

      {/* Notifications */}
      {successMsg && (
        <div className="p-4 rounded-2xl bg-emerald-950/40 border border-emerald-500/40 text-emerald-300 flex items-center gap-3 text-sm animate-in fade-in">
          <CheckCircle2 className="w-5 h-5 flex-shrink-0 text-emerald-400" />
          <span>{successMsg}</span>
        </div>
      )}

      {errorMsg && (
        <div className="p-4 rounded-2xl bg-rose-950/40 border border-rose-500/40 text-rose-300 flex items-center gap-3 text-sm animate-in fade-in">
          <AlertCircle className="w-5 h-5 flex-shrink-0 text-rose-400" />
          <span>{errorMsg}</span>
        </div>
      )}

      <form onSubmit={handleSave} className="space-y-8">
        {/* Section 1: Fitness Goal */}
        <div className="p-6 rounded-3xl bg-gray-900/60 border border-gray-800 backdrop-blur-md space-y-4 shadow-lg">
          <div className="flex items-center gap-2.5 text-white font-bold text-lg border-b border-gray-800 pb-3">
            <Target className="w-5 h-5 text-emerald-400" />
            <span>Primary Fitness Goal</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {fitnessGoals.map((g) => {
              const isSelected = fitnessGoal === g.id;
              const Icon = g.icon;
              return (
                <button
                  type="button"
                  key={g.id}
                  onClick={() => setFitnessGoal(g.id as FitnessGoal)}
                  className={`p-4 rounded-2xl border text-left transition-all flex flex-col justify-between gap-3 ${
                    isSelected
                      ? "bg-emerald-500/15 border-emerald-500/50 shadow-md shadow-emerald-500/10 ring-1 ring-emerald-400/30"
                      : "bg-gray-800/40 border-gray-800 hover:bg-gray-800/80 hover:border-gray-700"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <Icon className={`w-5 h-5 ${isSelected ? "text-emerald-400" : "text-gray-400"}`} />
                    {isSelected && <span className="w-2 h-2 rounded-full bg-emerald-400"></span>}
                  </div>
                  <div>
                    <h3 className={`font-semibold text-sm ${isSelected ? "text-white" : "text-gray-200"}`}>
                      {g.label}
                    </h3>
                    <p className="text-xs text-gray-400 mt-1 leading-relaxed">{g.desc}</p>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Section 2: Experience Level */}
        <div className="p-6 rounded-3xl bg-gray-900/60 border border-gray-800 backdrop-blur-md space-y-4 shadow-lg">
          <div className="flex items-center gap-2.5 text-white font-bold text-lg border-b border-gray-800 pb-3">
            <Award className="w-5 h-5 text-cyan-400" />
            <span>Experience Level</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {experienceLevels.map((lvl) => {
              const isSelected = experienceLevel === lvl.id;
              return (
                <button
                  type="button"
                  key={lvl.id}
                  onClick={() => setExperienceLevel(lvl.id as ExperienceLevel)}
                  className={`p-4 rounded-2xl border text-left transition-all flex flex-col justify-between gap-2 ${
                    isSelected
                      ? "bg-cyan-500/15 border-cyan-500/50 shadow-md shadow-cyan-500/10 ring-1 ring-cyan-400/30"
                      : "bg-gray-800/40 border-gray-800 hover:bg-gray-800/80 hover:border-gray-700"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <h3 className={`font-semibold text-sm ${isSelected ? "text-white" : "text-gray-200"}`}>
                      {lvl.label}
                    </h3>
                    {isSelected && <span className="w-2 h-2 rounded-full bg-cyan-400"></span>}
                  </div>
                  <p className="text-xs text-gray-400 leading-relaxed">{lvl.desc}</p>
                </button>
              );
            })}
          </div>
        </div>

        {/* Section 3: Preferred Focus */}
        <div className="p-6 rounded-3xl bg-gray-900/60 border border-gray-800 backdrop-blur-md space-y-4 shadow-lg">
          <div className="flex items-center gap-2.5 text-white font-bold text-lg border-b border-gray-800 pb-3">
            <Compass className="w-5 h-5 text-indigo-400" />
            <span>Preferred Session Focus</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {preferredFocusOptions.map((f) => {
              const isSelected = preferredFocus === f.id;
              return (
                <button
                  type="button"
                  key={f.id}
                  onClick={() => setPreferredFocus(f.id as PreferredFocus)}
                  className={`p-4 rounded-2xl border text-left transition-all flex flex-col justify-between gap-2 ${
                    isSelected
                      ? "bg-indigo-500/15 border-indigo-500/50 shadow-md shadow-indigo-500/10 ring-1 ring-indigo-400/30"
                      : "bg-gray-800/40 border-gray-800 hover:bg-gray-800/80 hover:border-gray-700"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <h3 className={`font-semibold text-sm ${isSelected ? "text-white" : "text-gray-200"}`}>
                      {f.label}
                    </h3>
                    {isSelected && <span className="w-2 h-2 rounded-full bg-indigo-400"></span>}
                  </div>
                  <p className="text-xs text-gray-400 leading-relaxed">{f.desc}</p>
                </button>
              );
            })}
          </div>
        </div>

        {/* Section 4: Coaching Style */}
        <div className="p-6 rounded-3xl bg-gray-900/60 border border-gray-800 backdrop-blur-md space-y-4 shadow-lg">
          <div className="flex items-center gap-2.5 text-white font-bold text-lg border-b border-gray-800 pb-3">
            <MessageSquare className="w-5 h-5 text-amber-400" />
            <span>AI Coach Feedback Style</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {coachingStyles.map((s) => {
              const isSelected = coachingStyle === s.id;
              return (
                <button
                  type="button"
                  key={s.id}
                  onClick={() => setCoachingStyle(s.id as CoachingStyle)}
                  className={`p-4 rounded-2xl border text-left transition-all flex flex-col justify-between gap-2 ${
                    isSelected
                      ? "bg-amber-500/15 border-amber-500/50 shadow-md shadow-amber-500/10 ring-1 ring-amber-400/30"
                      : "bg-gray-800/40 border-gray-800 hover:bg-gray-800/80 hover:border-gray-700"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <h3 className={`font-semibold text-sm ${isSelected ? "text-white" : "text-gray-200"}`}>
                      {s.label}
                    </h3>
                    {isSelected && <span className="w-2 h-2 rounded-full bg-amber-400"></span>}
                  </div>
                  <p className="text-xs text-gray-400 leading-relaxed">{s.desc}</p>
                </button>
              );
            })}
          </div>
        </div>

        {/* Save Button */}
        <div className="flex justify-end pt-2">
          <button
            type="submit"
            disabled={saving}
            className="px-8 py-3.5 rounded-2xl bg-emerald-500 hover:bg-emerald-400 disabled:bg-emerald-800/50 text-black font-bold text-sm shadow-xl shadow-emerald-500/20 transition-all flex items-center gap-2.5 cursor-pointer"
          >
            {saving ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin text-black" />
                <span>Saving Preferences...</span>
              </>
            ) : (
              <>
                <Save className="w-4 h-4 text-black" />
                <span>Save Profile Preferences</span>
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
