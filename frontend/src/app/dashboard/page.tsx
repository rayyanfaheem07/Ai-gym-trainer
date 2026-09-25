"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useAuth } from "@/hooks/useAuth";
import { AnalyticsOverviewCards } from "@/components/analytics/AnalyticsOverviewCards";
import { PerformanceTrendChart } from "@/components/analytics/PerformanceTrendChart";
import { ExerciseBreakdownCard } from "@/components/analytics/ExerciseBreakdownCard";
import { PersonalizationCard } from "@/components/dashboard/PersonalizationCard";
import { ExerciseCatalog } from "@/components/dashboard/ExerciseCatalog";
import { WorkoutHistory } from "@/components/dashboard/WorkoutHistory";
import { AnalyticsSummary, AnalyticsTrends, UserProfile } from "@/types";
import { analyticsApi, profileApi } from "@/lib/api";
import { Dumbbell, Activity, Play, ArrowRight, Loader2, Sparkles } from "lucide-react";

export default function DashboardPage() {
  const { user, isAuthenticated, isLoading: authLoading } = useAuth({ requireAuth: true });

  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [trends, setTrends] = useState<AnalyticsTrends | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [selectedPeriod, setSelectedPeriod] = useState<string>("30d");
  const [loadingAnalytics, setLoadingAnalytics] = useState(true);

  useEffect(() => {
    if (!isAuthenticated) return;

    async function fetchDashboardData() {
      try {
        setLoadingAnalytics(true);
        const [sumRes, trendRes, profRes] = await Promise.allSettled([
          analyticsApi.getSummary(),
          analyticsApi.getTrends(selectedPeriod),
          profileApi.get(),
        ]);

        if (sumRes.status === "fulfilled") setSummary(sumRes.value);
        if (trendRes.status === "fulfilled") setTrends(trendRes.value);
        if (profRes.status === "fulfilled") setProfile(profRes.value);
      } catch (err) {
        console.warn("Could not fetch analytics or profile data:", err);
      } finally {
        setLoadingAnalytics(false);
      }
    }

    fetchDashboardData();
  }, [isAuthenticated, selectedPeriod]);

  if (authLoading) {
    return (
      <div className="min-h-[60vh] flex flex-col items-center justify-center gap-3 text-gray-400">
        <Loader2 className="w-8 h-8 animate-spin text-emerald-400" />
        <p className="text-sm">Authenticating dashboard session...</p>
      </div>
    );
  }

  if (!isAuthenticated || !user) {
    return null; // Will redirect via useAuth
  }

  return (
    <div className="space-y-8 animate-in fade-in duration-300">
      {/* Athlete Hero Banner */}
      <div className="p-6 sm:p-8 rounded-3xl bg-gradient-to-r from-emerald-950/40 via-gray-900/60 to-cyan-950/40 border border-gray-800/80 backdrop-blur-md flex flex-col md:flex-row items-start md:items-center justify-between gap-6 shadow-xl">
        <div className="space-y-2">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-semibold">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
            Authenticated Athlete
          </div>
          <h1 className="text-2xl sm:text-4xl font-extrabold text-white tracking-tight">
            Welcome, {user.full_name || user.email.split("@")[0]}
          </h1>
          <p className="text-sm text-gray-400 max-w-xl">
            Real-time computer vision pose estimation, deterministic rep tracking, and persistent biomechanical performance analytics.
          </p>
        </div>

        <Link
          href="/workout"
          className="px-6 py-3.5 rounded-2xl bg-emerald-500 hover:bg-emerald-400 text-black font-bold text-sm shadow-xl shadow-emerald-500/20 transition-all flex items-center gap-2.5 flex-shrink-0 group cursor-pointer"
        >
          <Play className="w-4 h-4 fill-black" />
          <span>Start Live Workout</span>
          <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
        </Link>
      </div>

      {/* Athlete Personalization Profile Card */}
      {profile && <PersonalizationCard profile={profile} isLoading={loadingAnalytics && !profile} />}

      {/* Analytics Summary Overview Cards */}
      <AnalyticsOverviewCards summary={summary} isLoading={loadingAnalytics && !summary} />

      {/* Longitudinal Performance Trends Chart */}
      <PerformanceTrendChart
        points={trends?.points || []}
        isLoading={loadingAnalytics && !trends}
        selectedPeriod={selectedPeriod}
        onPeriodChange={(p) => setSelectedPeriod(p)}
      />

      {/* Exercise Performance Breakdown */}
      {summary?.exercise_breakdown && summary.exercise_breakdown.length > 0 && (
        <ExerciseBreakdownCard items={summary.exercise_breakdown} isLoading={loadingAnalytics} />
      )}

      {/* Main Grid: Exercise Catalog & Recent Workouts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Supported Exercises Catalog (2 Cols) */}
        <div className="lg:col-span-2 space-y-6">
          <ExerciseCatalog />
        </div>

        {/* Recent Workouts (1 Col) */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              <Activity className="w-5 h-5 text-cyan-400" />
              Recent Activity
            </h2>
            <Link
              href="/history"
              className="text-xs text-cyan-400 hover:text-cyan-300 font-semibold"
            >
              View All History
            </Link>
          </div>

          <WorkoutHistory />
        </div>
      </div>
    </div>
  );
}
