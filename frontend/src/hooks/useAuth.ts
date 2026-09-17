"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuthStore } from "@/store/authStore";

interface UseAuthOptions {
  requireAuth?: boolean;
  redirectTo?: string;
}

export function useAuth(options: UseAuthOptions = {}) {
  const { requireAuth = false, redirectTo = "/login" } = options;
  const router = useRouter();
  const pathname = usePathname();
  const {
    user,
    token,
    isAuthenticated,
    isLoading,
    error,
    initialize,
    login,
    register,
    logout,
    clearError,
  } = useAuthStore();

  useEffect(() => {
    initialize();
  }, [initialize]);

  useEffect(() => {
    if (!isLoading && requireAuth && !isAuthenticated) {
      router.push(`${redirectTo}?redirect=${encodeURIComponent(pathname)}`);
    }
  }, [isLoading, requireAuth, isAuthenticated, redirectTo, router, pathname]);

  return {
    user,
    token,
    isAuthenticated,
    isLoading,
    error,
    login,
    register,
    logout,
    clearError,
  };
}
