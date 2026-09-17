"use client";

import React, { Suspense } from "react";
import { RegisterForm } from "@/components/auth/RegisterForm";
import { Loader2 } from "lucide-react";

export default function RegisterPage() {
  return (
    <div className="min-h-[75vh] flex items-center justify-center py-6 px-4">
      <Suspense
        fallback={
          <div className="flex items-center gap-2 text-gray-400">
            <Loader2 className="w-5 h-5 animate-spin text-cyan-400" />
            <span>Loading...</span>
          </div>
        }
      >
        <RegisterForm />
      </Suspense>
    </div>
  );
}
