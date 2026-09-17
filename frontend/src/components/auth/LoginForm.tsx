"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuthStore } from "@/store/authStore";
import { LogIn, AlertCircle, Loader2 } from "lucide-react";

export const LoginForm: React.FC = () => {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectTo = searchParams?.get("redirect") || "/dashboard";

  const { login, isLoading, error, clearError } = useAuthStore();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
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

    try {
      await login(email.trim(), password);
      router.push(redirectTo);
    } catch {
      // Handled by store error
    }
  };

  return (
    <div className="w-full max-w-md p-8 rounded-3xl bg-gray-900/60 border border-gray-800/80 backdrop-blur-xl shadow-2xl shadow-black/50">
      <div className="text-center mb-8">
        <div className="w-12 h-12 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 mx-auto mb-4">
          <LogIn className="w-6 h-6" />
        </div>
        <h2 className="text-2xl font-bold text-white tracking-tight">Welcome Back</h2>
        <p className="text-sm text-gray-400 mt-1">Sign in to your AI Gym Trainer account</p>
      </div>

      {(error || validationError) && (
        <div className="mb-6 p-4 rounded-xl bg-rose-950/40 border border-rose-900/60 text-rose-300 text-sm flex items-start gap-3">
          <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5 text-rose-400" />
          <span>{validationError || error}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <label htmlFor="login-email" className="block text-xs font-semibold text-gray-300 mb-1.5">
            Email Address
          </label>
          <input
            id="login-email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="athlete@gymtrainer.com"
            disabled={isLoading}
            required
            className="w-full px-4 py-2.5 rounded-xl bg-gray-950/70 border border-gray-800 text-white placeholder-gray-500 text-sm focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition-all"
          />
        </div>

        <div>
          <label htmlFor="login-password" className="block text-xs font-semibold text-gray-300 mb-1.5">
            Password
          </label>
          <input
            id="login-password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••••••"
            disabled={isLoading}
            required
            className="w-full px-4 py-2.5 rounded-xl bg-gray-950/70 border border-gray-800 text-white placeholder-gray-500 text-sm focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition-all"
          />
        </div>

        <button
          type="submit"
          disabled={isLoading}
          className="w-full py-3 px-4 rounded-xl bg-emerald-500 hover:bg-emerald-400 disabled:bg-emerald-500/50 text-black font-semibold text-sm shadow-lg shadow-emerald-500/20 transition-all flex items-center justify-center gap-2 cursor-pointer disabled:cursor-not-allowed mt-2"
        >
          {isLoading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Authenticating...</span>
            </>
          ) : (
            <span>Sign In</span>
          )}
        </button>
      </form>

      <div className="mt-8 text-center text-xs text-gray-400">
        Don&apos;t have an account yet?{" "}
        <Link href="/register" className="text-emerald-400 hover:text-emerald-300 font-semibold underline underline-offset-4">
          Register now
        </Link>
      </div>
    </div>
  );
};
