import Link from "next/link";
import { Activity, Camera, Brain, Zap, ShieldCheck, Trophy } from "lucide-react";

export default function Home() {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-emerald-500/30 bg-emerald-500/10 text-emerald-400 text-xs font-medium mb-6">
        <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
        Computer Vision + Local LLM Engine Ready
      </div>

      <h1 className="text-4xl sm:text-6xl font-extrabold tracking-tight max-w-3xl bg-gradient-to-b from-white via-gray-100 to-gray-400 bg-clip-text text-transparent">
        Real-Time AI Gym Trainer & Biomechanics Coach
      </h1>

      <p className="mt-6 text-lg text-gray-400 max-w-2xl">
        High-precision 3D pose estimation, deterministic finite state rep counting, and instantaneous corrective feedback powered by local AI.
      </p>

      <div className="mt-8 flex flex-wrap items-center justify-center gap-4">
        <Link
          href="/workout"
          className="px-6 py-3 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-black font-semibold shadow-lg shadow-emerald-500/20 transition-all flex items-center gap-2"
        >
          <Camera className="w-5 h-5" />
          Start Live Training
        </Link>
        <Link
          href="/history"
          className="px-6 py-3 rounded-xl border border-gray-700 bg-gray-800/60 hover:bg-gray-800 text-white font-semibold transition-all flex items-center gap-2"
        >
          <Activity className="w-5 h-5 text-cyan-400" />
          View History & Insights
        </Link>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-16 max-w-5xl w-full text-left">
        <div className="p-6 rounded-2xl border border-gray-800 bg-gray-900/40 backdrop-blur-sm">
          <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 mb-4">
            <Zap className="w-5 h-5" />
          </div>
          <h3 className="font-semibold text-lg text-white">Sub-40ms Form Tracking</h3>
          <p className="mt-2 text-sm text-gray-400">
            One-Euro filtered MediaPipe pose processing computes 3D Euclidean joint angles and delivers instant visual & audio cues.
          </p>
        </div>

        <div className="p-6 rounded-2xl border border-gray-800 bg-gray-900/40 backdrop-blur-sm">
          <div className="w-10 h-10 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400 mb-4">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <h3 className="font-semibold text-lg text-white">Deterministic Rep FSM</h3>
          <p className="mt-2 text-sm text-gray-400">
            Robust state machine with hysteresis guarantees clean rep counts and distinguishes valid depth from bad repetitions.
          </p>
        </div>

        <div className="p-6 rounded-2xl border border-gray-800 bg-gray-900/40 backdrop-blur-sm">
          <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400 mb-4">
            <Brain className="w-5 h-5" />
          </div>
          <h3 className="font-semibold text-lg text-white">Local Ollama AI Coach</h3>
          <p className="mt-2 text-sm text-gray-400">
            Synthesizes session volume, fatigue breakdown, and range-of-motion metrics to provide private, local LLM coaching advice.
          </p>
        </div>
      </div>
    </div>
  );
}
