"use client";

import React, { useState, useEffect, useRef, useCallback, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { useCamera } from "@/hooks/useCamera";
import { useWebSocket } from "@/hooks/useWebSocket";
import { CameraFeed } from "@/components/camera/CameraFeed";
import { SkeletonCanvas } from "@/components/camera/SkeletonCanvas";
import { LiveTelemetryOverlay } from "@/components/workout/LiveTelemetryOverlay";
import { SessionSummaryModal } from "@/components/workout/SessionSummaryModal";
import { BrowserPoseDetector } from "@/lib/poseDetector";
import { workoutApi } from "@/lib/api";
import { ExerciseType, LandmarkPoint, SessionSummary } from "@/types";
import {
  Play,
  Square,
  RotateCcw,
  AlertCircle,
  Dumbbell,
  Video,
  VideoOff,
  Sparkles,
  Loader2,
} from "lucide-react";

const EXERCISES: { id: ExerciseType; name: string; target: string }[] = [
  { id: "squat", name: "Squats", target: "Quadriceps, Glutes & Core" },
  { id: "pushup", name: "Push-ups", target: "Chest, Shoulders & Triceps" },
  { id: "bicep_curl", name: "Bicep Curls", target: "Biceps & Forearms" },
  { id: "lunge", name: "Lunges", target: "Hamstrings, Quads & Balance" },
  { id: "shoulder_press", name: "Shoulder Press", target: "Deltoids & Upper Traps" },
];

function WorkoutArena() {
  const searchParams = useSearchParams();
  const initialExercise = (searchParams?.get("exercise") as ExerciseType) || "squat";

  const { token, isAuthenticated } = useAuth();
  const { videoRef, cameraState, startCamera, stopCamera } = useCamera();

  const [selectedExercise, setSelectedExercise] = useState<ExerciseType>(
    EXERCISES.some((e) => e.id === initialExercise) ? initialExercise : "squat"
  );
  const [isTrainingActive, setIsTrainingActive] = useState<boolean>(false);
  const [activeWorkoutId, setActiveWorkoutId] = useState<string | null>(null);
  const [currentLandmarks, setCurrentLandmarks] = useState<LandmarkPoint[]>([]);
  const [completedSummary, setCompletedSummary] = useState<SessionSummary | null>(null);
  const [showSummaryModal, setShowSummaryModal] = useState<boolean>(false);
  const [generalError, setGeneralError] = useState<string | null>(null);

  const poseDetectorRef = useRef<BrowserPoseDetector | null>(null);
  const frameAnimationRef = useRef<number | null>(null);
  const isTrainingRef = useRef<boolean>(false);
  isTrainingRef.current = isTrainingActive;

  // Real-time WebSocket hook
  const {
    status: wsStatus,
    latestAnalysis,
    lastSummary,
    lastError,
    connect,
    disconnect,
    startSession,
    stopSession,
    sendPoseFrame,
    setExercise: wsSetExercise,
    reset: wsReset,
  } = useWebSocket({
    onSessionStopped: (stopped) => {
      setCompletedSummary(stopped.summary);
      setShowSummaryModal(true);
    },
    onError: (code, message) => {
      setGeneralError(`[${code}] ${message}`);
    },
  });

  // Handle Exercise Selection Change
  const handleExerciseChange = (newExercise: ExerciseType) => {
    setSelectedExercise(newExercise);
    if (isTrainingActive && wsStatus === "connected") {
      wsSetExercise(newExercise);
    }
  };

  // Start Training Routine
  const handleStartWorkout = async () => {
    setGeneralError(null);
    setCompletedSummary(null);

    // 1. Verify token
    if (!token) {
      setGeneralError("Please log in to start a live tracked workout.");
      return;
    }

    // 2. Start Camera
    const cameraOk = await startCamera();
    if (!cameraOk) {
      return;
    }

    // 3. Create active workout record in backend REST API
    let workoutId: string | undefined = undefined;
    try {
      const workout = await workoutApi.create(`Live ${selectedExercise.replace("_", " ")} workout`);
      workoutId = workout.id;
      setActiveWorkoutId(workout.id);
    } catch (err: any) {
      console.warn("Could not create workout session in REST API, continuing in-memory:", err);
    }

    // 4. Connect WebSocket & Initialize Session
    connect(token);
    setIsTrainingActive(true);

    // 5. Initialize Pose Detector
    if (!poseDetectorRef.current) {
      poseDetectorRef.current = new BrowserPoseDetector();
      await poseDetectorRef.current.initialize();
    }
  };

  // Send Start Session once WebSocket connects
  useEffect(() => {
    if (isTrainingActive && wsStatus === "connected") {
      startSession(selectedExercise, activeWorkoutId || undefined);
    }
  }, [isTrainingActive, wsStatus, selectedExercise, activeWorkoutId, startSession]);

  // Frame Capture & Pose Landmark Streaming Loop
  const runFrameLoop = useCallback(async () => {
    if (!isTrainingRef.current) return;

    if (videoRef.current && videoRef.current.readyState >= 2 && poseDetectorRef.current) {
      const landmarks = await poseDetectorRef.current.detect(videoRef.current);
      if (landmarks && landmarks.length >= 33) {
        setCurrentLandmarks(landmarks);
        sendPoseFrame(landmarks, selectedExercise);
      }
    }

    if (isTrainingRef.current) {
      frameAnimationRef.current = requestAnimationFrame(runFrameLoop);
    }
  }, [videoRef, sendPoseFrame, selectedExercise]);

  useEffect(() => {
    if (isTrainingActive && wsStatus === "connected") {
      frameAnimationRef.current = requestAnimationFrame(runFrameLoop);
    }
    return () => {
      if (frameAnimationRef.current) {
        cancelAnimationFrame(frameAnimationRef.current);
        frameAnimationRef.current = null;
      }
    };
  }, [isTrainingActive, wsStatus, runFrameLoop]);

  // Stop Training Routine
  const handleStopWorkout = async () => {
    setIsTrainingActive(false);

    if (frameAnimationRef.current) {
      cancelAnimationFrame(frameAnimationRef.current);
      frameAnimationRef.current = null;
    }

    // Send Stop Session to WebSocket
    if (wsStatus === "connected") {
      stopSession(true);
    }

    // Finish REST workout if active
    if (activeWorkoutId) {
      try {
        await workoutApi.finish(activeWorkoutId);
      } catch (err) {
        console.warn("Could not mark workout as finished in REST API:", err);
      }
    }

    // Stop Camera & Clean Landmarking
    stopCamera();
    setCurrentLandmarks([]);

    // Brief timeout to allow summary packet to arrive before disconnect
    setTimeout(() => {
      disconnect();
    }, 500);
  };

  const handleRestart = () => {
    setShowSummaryModal(false);
    setCompletedSummary(null);
    handleStartWorkout();
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight flex items-center gap-2.5">
            <Dumbbell className="w-7 h-7 text-emerald-400" />
            Live AI Workout Arena
          </h1>
          <p className="text-xs sm:text-sm text-gray-400 mt-1">
            Real-time computer vision pose estimation & deterministic biomechanics evaluation.
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-3">
          {!isTrainingActive ? (
            <button
              onClick={handleStartWorkout}
              className="px-6 py-3 rounded-2xl bg-emerald-500 hover:bg-emerald-400 text-black font-bold text-sm shadow-xl shadow-emerald-500/25 transition-all flex items-center gap-2 cursor-pointer"
            >
              <Play className="w-4 h-4 fill-black" />
              <span>Start Workout</span>
            </button>
          ) : (
            <button
              onClick={handleStopWorkout}
              className="px-6 py-3 rounded-2xl bg-rose-600 hover:bg-rose-500 text-white font-bold text-sm shadow-xl shadow-rose-600/25 transition-all flex items-center gap-2 cursor-pointer"
            >
              <Square className="w-4 h-4 fill-white" />
              <span>Stop & Save Session</span>
            </button>
          )}
        </div>
      </div>

      {/* Error Alert */}
      {(generalError || lastError) && (
        <div className="p-4 rounded-2xl bg-rose-950/40 border border-rose-900/60 text-rose-300 text-xs sm:text-sm flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-rose-400 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <span className="font-semibold">Connection or Hardware Notice:</span>{" "}
            {generalError || lastError?.message}
          </div>
        </div>
      )}

      {/* Exercise Selector Tabs */}
      <div className="p-2 rounded-2xl bg-gray-900/60 border border-gray-800 flex flex-wrap gap-2">
        {EXERCISES.map((ex) => (
          <button
            key={ex.id}
            onClick={() => handleExerciseChange(ex.id)}
            disabled={isTrainingActive}
            className={`px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-2 cursor-pointer disabled:opacity-75 disabled:cursor-not-allowed ${
              selectedExercise === ex.id
                ? "bg-emerald-500 text-black shadow-md shadow-emerald-500/20"
                : "text-gray-300 hover:text-white hover:bg-gray-800/60"
            }`}
          >
            <span>{ex.name}</span>
          </button>
        ))}
      </div>

      {/* Main Grid: Camera Video (Left 3 cols on 5-grid) + Live Telemetry HUD (Right 2 cols) */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Camera Feed & Skeleton (3 cols) */}
        <div className="lg:col-span-3 space-y-3">
          <div className="relative rounded-3xl overflow-hidden border border-gray-800/80 bg-gray-950 shadow-2xl">
            <CameraFeed
              ref={videoRef}
              cameraState={cameraState}
              onRetry={startCamera}
            />
            {isTrainingActive && currentLandmarks.length >= 33 && (
              <SkeletonCanvas landmarks={currentLandmarks} />
            )}
          </div>

          <div className="px-4 py-2.5 rounded-2xl bg-gray-900/40 border border-gray-800 text-xs text-gray-400 flex items-center justify-between">
            <span>
              Target:{" "}
              <strong className="text-white">
                {EXERCISES.find((e) => e.id === selectedExercise)?.target}
              </strong>
            </span>
            <span className="font-mono text-emerald-400">
              {isTrainingActive ? "● STREAMING POSE" : "STANDBY"}
            </span>
          </div>
        </div>

        {/* Live Telemetry Overlay HUD (2 cols) */}
        <div className="lg:col-span-2">
          <LiveTelemetryOverlay
            analysis={latestAnalysis}
            wsStatus={wsStatus}
            isStreaming={isTrainingActive}
            exerciseName={selectedExercise}
          />
        </div>
      </div>

      {/* Session Summary Modal */}
      {showSummaryModal && (
        <SessionSummaryModal
          summary={completedSummary || lastSummary}
          onClose={() => setShowSummaryModal(false)}
          onRestart={handleRestart}
        />
      )}
    </div>
  );
}

export default function WorkoutPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-[60vh] flex flex-col items-center justify-center gap-3 text-gray-400">
          <Loader2 className="w-8 h-8 animate-spin text-emerald-400" />
          <p className="text-sm">Initializing Workout Arena...</p>
        </div>
      }
    >
      <WorkoutArena />
    </Suspense>
  );
}
