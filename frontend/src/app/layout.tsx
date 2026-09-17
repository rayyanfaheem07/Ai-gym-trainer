import type { Metadata } from "next";
import { Navbar } from "@/components/layout/Navbar";
import "./globals.css";

export const metadata: Metadata = {
  title: "Real-Time AI Gym Trainer & Biomechanics Coach",
  description:
    "AI-powered real-time computer vision fitness trainer with form correction, rep tracking FSM, and local LLM coaching.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased bg-[#090d16] text-gray-100 min-h-screen flex flex-col selection:bg-emerald-500 selection:text-black font-sans">
        <Navbar />
        <main className="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-8">
          {children}
        </main>
      </body>
    </html>
  );
}
