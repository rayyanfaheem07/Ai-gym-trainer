"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/authStore";
import { UserPlus, AlertCircle, Loader2, CheckCircle2 } from "lucide-react";

export const RegisterForm: React.FC = () => {
  const router = useRouter();
  const { register, isLoading, error, clearError } = useAuthStore();
  const initialize = useAuthStore((state) => state.initialize);

  useEffect(() => {
    initialize();
  }, [initialize]);

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);
    clearError();

    if (!email.trim()) {
      setValidationError("Email is required.");
      return;
    }
    if (!password) {
      setValidationError("Password is required.");
      return;
    }
    if (password.length < 8) {
      setValidationError("Password must be at least 8 characters long.");
      return;
    }
    if (password !== confirmPassword) {
      setValidationError("Passwords do not match.");
      return;
    }

    try {
      await register(email.trim(), password, fullName.trim() || undefined);
      router.push("/dashboard");
    } catch {
      // Handled by store error
    }
  };

  return (
    <div className="w-full max-w-md p-8 rounded-3xl bg-gray-900/60 border border-gray-800/80 backdrop-blur-xl shadow-2xl shadow-black/50">
      <div className="text-center mb-8">
        <div className="w-12 h-12 rounded-2xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400 mx-auto mb-4">
          <UserPlus className="w-6 h-6" />
        </div>
        <h2 className="text-2xl font-bold text-white tracking-tight">Create Account</h2>
        <p className="text-sm text-gray-400 mt-1">Start your AI-guided fitness journey</p>
      </div>

      {(error || validationError) && (
        <div className="mb-6 p-4 rounded-xl bg-rose-950/40 border border-rose-900/60 text-rose-300 text-sm flex items-start gap-3">
          <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5 text-rose-400" />
          <span>{validationError || error}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="reg-name" className="block text-xs font-semibold text-gray-300 mb-1.5">
            Full Name <span className="text-gray-500 font-normal">(Optional)</span>
          </label>
          <input
            id="reg-name"
            type="text"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            placeholder="Alex Athlete"
            disabled={isLoading}
            className="w-full px-4 py-2.5 rounded-xl bg-gray-950/70 border border-gray-800 text-white placeholder-gray-500 text-sm focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all"
          />
        </div>

        <div>
          <label htmlFor="reg-email" className="block text-xs font-semibold text-gray-300 mb-1.5">
            Email Address
          </label>
          <input
            id="reg-email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="athlete@gymtrainer.com"
            disabled={isLoading}
            required
            className="w-full px-4 py-2.5 rounded-xl bg-gray-950/70 border border-gray-800 text-white placeholder-gray-500 text-sm focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all"
          />
        </div>

        <div>
          <label htmlFor="reg-password" className="block text-xs font-semibold text-gray-300 mb-1.5">
            Password <span className="text-gray-500 font-normal">(min. 8 characters)</span>
          </label>
          <input
            id="reg-password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••••••"
            disabled={isLoading}
            required
            className="w-full px-4 py-2.5 rounded-xl bg-gray-950/70 border border-gray-800 text-white placeholder-gray-500 text-sm focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all"
          />
        </div>

        <div>
          <label htmlFor="reg-confirm" className="block text-xs font-semibold text-gray-300 mb-1.5">
            Confirm Password
          </label>
          <input
            id="reg-confirm"
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            placeholder="••••••••••••"
            disabled={isLoading}
            required
            className="w-full px-4 py-2.5 rounded-xl bg-gray-950/70 border border-gray-800 text-white placeholder-gray-500 text-sm focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all"
          />
        </div>

        <button
          type="submit"
          disabled={isLoading}
          className="w-full py-3 px-4 rounded-xl bg-cyan-500 hover:bg-cyan-400 disabled:bg-cyan-500/50 text-black font-semibold text-sm shadow-lg shadow-cyan-500/20 transition-all flex items-center justify-center gap-2 cursor-pointer disabled:cursor-not-allowed mt-4"
        >
          {isLoading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Creating Account...</span>
            </>
          ) : (
            <span>Create Account</span>
          )}
        </button>
      </form>

      <div className="mt-8 text-center text-xs text-gray-400">
        Already have an account?{" "}
        <Link href="/login" className="text-cyan-400 hover:text-cyan-300 font-semibold underline underline-offset-4">
          Sign In
        </Link>
      </div>
    </div>
  );
};
