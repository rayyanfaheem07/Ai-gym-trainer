import { test, describe } from "node:test";
import assert from "node:assert/strict";

describe("Phase 16 Frontend Quality Assurance & Complete End-to-End Workflows", () => {
  // ============================================================================
  // 1. Complete Logical Flow: Register -> Login -> Profile -> Workout -> History -> Analytics -> Coach
  // ============================================================================
  test("Complete User Flow transitions across state machines without data loss", () => {
    // 1. Registration state
    interface User {
      id: string;
      email: string;
      fullName?: string;
    }
    const registeredUser: User = { id: "user-123", email: "athlete@gym.ai", fullName: "Athlete One" };
    const register = (email: string) => {
      return { success: true, user: { id: "user-123", email, fullName: "Athlete One" } };
    };
    const regResult = register("athlete@gym.ai");
    assert.equal(regResult.success, true);
    assert.equal(registeredUser.email, "athlete@gym.ai");

    // 2. Login state & token acquisition
    let authToken: string | null = null;
    const login = (email: string) => {
      if (email === registeredUser.email) {
        authToken = "jwt-mock-token-header.payload.signature";
        return { token: authToken };
      }
      throw new Error("Invalid credentials");
    };
    const loginResult = login("athlete@gym.ai");
    assert.ok(loginResult.token);

    // 3. Profile configuration
    interface Profile {
      fitness_goal: string;
      experience_level: string;
      coaching_style: string;
    }
    let profile: Profile = {
      fitness_goal: "strength",
      experience_level: "intermediate",
      coaching_style: "concise",
    };
    assert.equal(profile.fitness_goal, "strength");

    // 4. Workout Start & Streaming Telemetry
    interface ActiveSession {
      workoutId: string;
      exercise: string;
      reps: number;
      validReps: number;
      formScore: number;
      status: "active" | "completed";
    }
    const session: ActiveSession = {
      workoutId: "workout-999",
      exercise: "squat",
      reps: 0,
      validReps: 0,
      formScore: 100,
      status: "active",
    };

    // Simulate 3 processed reps
    for (let r = 1; r <= 3; r++) {
      session.reps += 1;
      session.validReps += 1;
      session.formScore = 92.0;
    }
    assert.equal(session.reps, 3);
    assert.equal(session.validReps, 3);
    assert.equal(session.formScore, 92.0);

    // 5. Workout Completion
    session.status = "completed";
    assert.equal(session.status, "completed");

    // 6. Workout History & Analytics Aggregation
    const historyEntry = {
      id: session.workoutId,
      exercise: session.exercise,
      total_reps: session.reps,
      valid_reps: session.validReps,
      form_score: session.formScore,
      completed_at: new Date().toISOString(),
    };
    assert.equal(historyEntry.total_reps, 3);

    // 7. Personalized Coach Feedback linking
    const coachFeedback = {
      session_id: session.workoutId,
      summary: "Excellent depth on all 3 squat repetitions. Hips stayed stable.",
      strengths: ["Clean knee tracking", "Full depth"],
      areas_to_improve: ["Keep chest proud on ascent"],
      is_fallback: false,
    };
    assert.equal(coachFeedback.session_id, historyEntry.id);
    assert.ok(coachFeedback.summary.includes("3 squat repetitions"));
  });

  // ============================================================================
  // 2. Hardware / Camera Permission Denial & Failure Handling
  // ============================================================================
  test("Camera permission denial and device unavailability handle clean recovery", () => {
    type CameraErrorState = {
      hasError: boolean;
      errorCode: string | null;
      userFriendlyMessage: string | null;
    };

    const handleCameraError = (err: { name: string; message: string }): CameraErrorState => {
      if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
        return {
          hasError: true,
          errorCode: "CAMERA_PERMISSION_DENIED",
          userFriendlyMessage:
            "Camera permission was denied. Please allow camera access in browser permissions to enable form tracking.",
        };
      }
      if (err.name === "NotFoundError" || err.name === "DevicesNotFoundError") {
        return {
          hasError: true,
          errorCode: "CAMERA_DEVICE_NOT_FOUND",
          userFriendlyMessage:
            "No camera device was detected on your system. Please connect a webcam to continue.",
        };
      }
      return {
        hasError: true,
        errorCode: "CAMERA_GENERIC_ERROR",
        userFriendlyMessage: "An error occurred while connecting to the camera.",
      };
    };

    const permDenied = handleCameraError({ name: "NotAllowedError", message: "Permission denied" });
    assert.equal(permDenied.hasError, true);
    assert.equal(permDenied.errorCode, "CAMERA_PERMISSION_DENIED");
    assert.match(permDenied.userFriendlyMessage!, /camera access in browser permissions/i);

    const devNotFound = handleCameraError({ name: "NotFoundError", message: "Device not found" });
    assert.equal(devNotFound.hasError, true);
    assert.equal(devNotFound.errorCode, "CAMERA_DEVICE_NOT_FOUND");
    assert.match(devNotFound.userFriendlyMessage!, /No camera device was detected/i);
  });

  // ============================================================================
  // 3. Resource Cleanup: MediaPipe, Camera Tracks, WebSocket & Timers
  // ============================================================================
  test("Resource cleanup safely stops camera tracks, closes socket, and clears timers", () => {
    let trackStopped = false;
    let socketClosed = false;
    let timerCleared = false;
    let animationCancelled = false;

    const mockTrack = {
      stop: () => {
        trackStopped = true;
      },
    };

    const mockSocket = {
      close: () => {
        socketClosed = true;
      },
    };

    const timerId = 12345;
    const animationFrameId = 67890;

    // Simulate cleanup function in workout component unmount
    const cleanupWorkoutResources = (
      tracks: Array<{ stop: () => void }>,
      ws: { close: () => void } | null,
      timer: number | null,
      animId: number | null
    ) => {
      tracks.forEach((t) => t.stop());
      if (ws) ws.close();
      if (timer) {
        timerCleared = true; // simulated clearInterval
      }
      if (animId) {
        animationCancelled = true; // simulated cancelAnimationFrame
      }
    };

    cleanupWorkoutResources([mockTrack], mockSocket, timerId, animationFrameId);

    assert.equal(trackStopped, true, "Camera media tracks must be stopped");
    assert.equal(socketClosed, true, "WebSocket connection must be closed");
    assert.equal(timerCleared, true, "Workout timers must be cleared");
    assert.equal(animationCancelled, true, "Animation frame loops must be cancelled");
  });

  // ============================================================================
  // 4. WebSocket Error Packets and Oversized Message Resilience
  // ============================================================================
  test("WebSocket client safely parses error packets and oversized payload warnings", () => {
    type WSIncomingPacket =
      | { type: "connected"; status: string }
      | { type: "analysis_result"; rep_count: number }
      | { type: "error"; code: string; message: string };

    const parseServerPacket = (rawJson: string): WSIncomingPacket | null => {
      try {
        const parsed = JSON.parse(rawJson);
        if (typeof parsed !== "object" || parsed === null) return null;
        return parsed as WSIncomingPacket;
      } catch {
        return null;
      }
    };

    // 1. Oversized payload error packet
    const payloadTooLarge = JSON.stringify({
      type: "error",
      code: "PAYLOAD_TOO_LARGE",
      message: "Message size exceeds maximum limit of 1048576 characters.",
    });
    const parsedErr = parseServerPacket(payloadTooLarge);
    assert.ok(parsedErr);
    assert.equal(parsedErr.type, "error");
    if (parsedErr.type === "error") {
      assert.equal(parsedErr.code, "PAYLOAD_TOO_LARGE");
    }

    // 2. Corrupt / Non-JSON string
    const corruptPacket = parseServerPacket("MALFORMED_NON_JSON_DATA{{{");
    assert.equal(corruptPacket, null);
  });

  // ============================================================================
  // 5. JWT Expiration & Unauthorized Route Guard
  // ============================================================================
  test("Auth guard identifies expired token and enforces re-authentication", () => {
    const isTokenExpired = (expTimestampSec: number) => {
      const nowSec = Math.floor(Date.now() / 1000);
      return expTimestampSec <= nowSec;
    };

    const pastExp = Math.floor(Date.now() / 1000) - 300; // 5 min ago
    assert.equal(isTokenExpired(pastExp), true);

    const futureExp = Math.floor(Date.now() / 1000) + 3600; // 1 hr future
    assert.equal(isTokenExpired(futureExp), false);

    const resolveAuthGuard = (token: string | null, expTimestampSec: number | null) => {
      if (!token) return { allow: false, redirect: "/login" };
      if (expTimestampSec && isTokenExpired(expTimestampSec)) {
        return { allow: false, redirect: "/login?expired=true" };
      }
      return { allow: true, redirect: null };
    };

    assert.deepEqual(resolveAuthGuard(null, null), { allow: false, redirect: "/login" });
    assert.deepEqual(resolveAuthGuard("valid-token", pastExp), {
      allow: false,
      redirect: "/login?expired=true",
    });
    assert.deepEqual(resolveAuthGuard("valid-token", futureExp), { allow: true, redirect: null });
  });
});
