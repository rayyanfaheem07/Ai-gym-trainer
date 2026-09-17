"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuthStore } from "@/store/authStore";
import { Activity, Dumbbell, User as UserIcon, LogOut, LogIn, UserPlus } from "lucide-react";

export const Navbar: React.FC = () => {
  const pathname = usePathname();
  const { user, isAuthenticated, logout } = useAuthStore();

  const navLinks = [
    { href: "/workout", label: "Live Workout", icon: Dumbbell },
    { href: "/dashboard", label: "Dashboard", icon: Activity, authOnly: true },
    { href: "/history", label: "History & AI Coach", icon: Activity, authOnly: true },
  ];

  return (
    <header className="border-b border-gray-800/80 bg-gray-900/70 backdrop-blur-md sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2.5 group">
          <div className="h-9 w-9 rounded-xl bg-gradient-to-tr from-emerald-500 to-cyan-500 flex items-center justify-center font-black text-black text-sm shadow-md shadow-emerald-500/20 group-hover:scale-105 transition-transform">
            AI
          </div>
          <span className="font-bold text-lg tracking-tight bg-gradient-to-r from-white via-gray-100 to-gray-300 bg-clip-text text-transparent">
            AI Gym Trainer
          </span>
        </Link>

        {/* Navigation Links */}
        <nav className="hidden md:flex items-center gap-6 text-sm font-medium">
          {navLinks.map((link) => {
            if (link.authOnly && !isAuthenticated) return null;
            const isActive = pathname === link.href;
            const Icon = link.icon;
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all ${
                  isActive
                    ? "bg-emerald-500/10 text-emerald-400 font-semibold border border-emerald-500/20"
                    : "text-gray-300 hover:text-white hover:bg-gray-800/50"
                }`}
              >
                <Icon className="w-4 h-4" />
                {link.label}
              </Link>
            );
          })}
        </nav>

        {/* Auth / Profile Actions */}
        <div className="flex items-center gap-3">
          {isAuthenticated && user ? (
            <div className="flex items-center gap-3">
              <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-800/60 border border-gray-700/60 text-xs text-gray-300">
                <div className="w-2 h-2 rounded-full bg-emerald-400"></div>
                <UserIcon className="w-3.5 h-3.5 text-gray-400" />
                <span className="max-w-[140px] truncate">{user.full_name || user.email}</span>
              </div>
              <button
                onClick={logout}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-gray-800/80 hover:bg-rose-950/40 text-gray-300 hover:text-rose-400 border border-gray-700/80 hover:border-rose-900/60 transition-all"
                title="Log Out"
              >
                <LogOut className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Logout</span>
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <Link
                href="/login"
                className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold text-gray-300 hover:text-white hover:bg-gray-800/60 border border-transparent hover:border-gray-700 transition-all"
              >
                <LogIn className="w-3.5 h-3.5" />
                Login
              </Link>
              <Link
                href="/register"
                className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-emerald-500 hover:bg-emerald-400 text-black shadow-sm shadow-emerald-500/20 transition-all"
              >
                <UserPlus className="w-3.5 h-3.5" />
                Register
              </Link>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
