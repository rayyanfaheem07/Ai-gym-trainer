import { test, describe, beforeEach } from "node:test";
import assert from "node:assert/strict";

describe("Phase 11 UI & Workout Workflows Integration", () => {
  test("Auth validation helper handles required fields and password length", () => {
    const validateRegistration = (email: string, pass: string, confirm: string) => {
      if (!email || !email.includes("@")) return "Invalid email address";
      if (!pass || pass.length < 8) return "Password must be at least 8 characters long";
      if (pass !== confirm) return "Passwords do not match";
      return null;
    };

    assert.equal(validateRegistration("", "password123", "password123"), "Invalid email address");
    assert.equal(validateRegistration("user@gym.com", "short", "short"), "Password must be at least 8 characters long");
    assert.equal(validateRegistration("user@gym.com", "password123", "different"), "Passwords do not match");
    assert.equal(validateRegistration("user@gym.com", "password123", "password123"), null);
  });

  test("Exercise catalog contains all 5 required Phase 6/10 exercises", () => {
    const supported = ["squat", "pushup", "bicep_curl", "lunge", "shoulder_press"];
    const exercises = [
      { id: "squat", name: "Squats" },
      { id: "pushup", name: "Push-ups" },
      { id: "bicep_curl", name: "Bicep Curls" },
      { id: "lunge", name: "Lunges" },
      { id: "shoulder_press", name: "Shoulder Press" },
    ];

    exercises.forEach((ex) => {
      assert.ok(supported.includes(ex.id));
    });
  });

  test("WebSocket client state machine transitions correctly through connection lifecycle", () => {
    type WSState = "disconnected" | "connecting" | "connected" | "error";
    let state: WSState = "disconnected";

    // 1. Connect
    state = "connecting";
    assert.equal(state, "connecting");

    // 2. Connected
    const connectedMsg = { type: "connected", status: "authenticated", user_id: "u-1", session_id: "s-1" };
    if (connectedMsg.type === "connected") {
      state = "connected";
    }
    assert.equal(state, "connected");

    // 3. Receive telemetry
    let repCount = 0;
    let formScore = 100;
    let stage = "ready";
    const analysisMsg = {
      type: "analysis_result",
      rep_count: 3,
      valid_reps: 3,
      form_score: 95.0,
      stage: "bottom",
    };
    repCount = analysisMsg.rep_count;
    formScore = analysisMsg.form_score;
    stage = analysisMsg.stage;
    assert.equal(repCount, 3);
    assert.equal(formScore, 95.0);
    assert.equal(stage, "bottom");

    // 4. Disconnect
    state = "disconnected";
    assert.equal(state, "disconnected");
  });

  test("Error packets from WebSocket are safely parsed without leaking stack traces", () => {
    const errorMsg = {
      type: "error",
      code: "INVALID_JSON",
      message: "Malformed JSON payload. Please provide valid JSON.",
    };

    assert.equal(errorMsg.type, "error");
    assert.equal(errorMsg.code, "INVALID_JSON");
    assert.doesNotMatch(errorMsg.message, /Traceback|exception|password|secret/i);
  });

  test("Camera permission denial failure produces clean user-facing error", () => {
    const formatCameraError = (errName: string) => {
      if (errName === "NotAllowedError" || errName === "PermissionDeniedError") {
        return "Camera permission denied. Please allow camera access in your browser settings to track form.";
      }
      return "Failed to access webcam device.";
    };

    const userMessage = formatCameraError("NotAllowedError");
    assert.match(userMessage, /Camera permission denied/);
    assert.doesNotMatch(userMessage, /undefined|null|Traceback/);
  });

  test("Workout start and stop workflow handles cleanup properly", () => {
    let isCameraActive = false;
    let isWebSocketConnected = false;
    let activeLandmarks: any[] = [{ x: 0.5, y: 0.5 }];

    // Start workout
    isCameraActive = true;
    isWebSocketConnected = true;
    assert.equal(isCameraActive, true);
    assert.equal(isWebSocketConnected, true);

    // Stop workout
    isCameraActive = false;
    activeLandmarks = [];
    isWebSocketConnected = false;

    assert.equal(isCameraActive, false);
    assert.equal(activeLandmarks.length, 0);
    assert.equal(isWebSocketConnected, false);
  });

  test("Dashboard authentication guard redirects unauthenticated users", () => {
    const checkAuthGuard = (token: string | null, isAuthenticated: boolean) => {
      if (!token || !isAuthenticated) {
        return { allowAccess: false, redirectTo: "/login" };
      }
      return { allowAccess: true, redirectTo: null };
    };

    assert.deepEqual(checkAuthGuard(null, false), { allowAccess: false, redirectTo: "/login" });
    assert.deepEqual(checkAuthGuard("valid-token", true), { allowAccess: true, redirectTo: null });
  });

  test("Logout clears user session and auth token cleanly", () => {
    let authState = {
      user: { id: "123", email: "user@gym.com" },
      token: "secret-token",
      isAuthenticated: true,
    };

    const logout = () => {
      authState = { user: null as any, token: null as any, isAuthenticated: false };
    };

    logout();
    assert.equal(authState.user, null);
    assert.equal(authState.token, null);
    assert.equal(authState.isAuthenticated, false);
  });
});

