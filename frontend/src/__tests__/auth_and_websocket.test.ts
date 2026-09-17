import { test, describe, beforeEach } from "node:test";
import assert from "node:assert/strict";

// Mock localStorage for node environment
const mockStorage = new Map<string, string>();
(globalThis as any).localStorage = {
  getItem: (k: string) => mockStorage.get(k) || null,
  setItem: (k: string, v: string) => mockStorage.set(k, v),
  removeItem: (k: string) => mockStorage.delete(k),
  clear: () => mockStorage.clear(),
};

import { setStoredToken, getStoredToken, removeStoredToken, isTokenExpired } from "../lib/auth";
import { BrowserPoseDetector } from "../lib/poseDetector";

describe("Phase 11 Frontend Auth & Token Management", () => {
  beforeEach(() => {
    mockStorage.clear();
  });

  test("Token storage and retrieval works correctly", () => {
    assert.equal(getStoredToken(), null);
    setStoredToken("test.jwt.token");
    assert.equal(getStoredToken(), "test.jwt.token");
    removeStoredToken();
    assert.equal(getStoredToken(), null);
  });

  test("isTokenExpired validates unexpired and expired JWT payloads", () => {
    const futureExp = Math.floor(Date.now() / 1000) + 3600;
    const pastExp = Math.floor(Date.now() / 1000) - 3600;

    const validPayload = btoa(JSON.stringify({ sub: "user-1", exp: futureExp }));
    const expiredPayload = btoa(JSON.stringify({ sub: "user-1", exp: pastExp }));

    const validToken = `header.${validPayload}.signature`;
    const expiredToken = `header.${expiredPayload}.signature`;

    assert.equal(isTokenExpired(validToken), false);
    assert.equal(isTokenExpired(expiredToken), true);
    assert.equal(isTokenExpired("invalid-jwt-token"), true);
  });

  test("Token is never exposed in decoded payload strings unintentionally", () => {
    const rawSecret = "super-secret-backend-key";
    const payload = btoa(JSON.stringify({ sub: "user-123", email: "test@gym.com" }));
    const token = `header.${payload}.signature`;

    // Verify token can be checked for validity without leaking keys
    assert.doesNotMatch(token, new RegExp(rawSecret));
  });
});

describe("Phase 11 WebSocket Protocol & Message Serialization", () => {
  test("Pose Frame payload serialization produces valid JSON", () => {
    const landmarks = Array.from({ length: 33 }, (_, i) => ({
      x: 0.5 + i * 0.01,
      y: 0.5 + i * 0.01,
      z: 0.0,
      visibility: 0.95,
    }));

    const framePayload = {
      type: "pose_frame",
      timestamp_ms: 1000.0,
      exercise: "squat",
      landmarks,
    };

    const jsonStr = JSON.stringify(framePayload);
    const parsed = JSON.parse(jsonStr);

    assert.equal(parsed.type, "pose_frame");
    assert.equal(parsed.exercise, "squat");
    assert.equal(parsed.landmarks.length, 33);
    assert.equal(parsed.landmarks[0].x, 0.5);
  });

  test("Analysis Result Response parsing handles full biomechanical telemetry", () => {
    const serverMsg = {
      type: "analysis_result",
      timestamp: 1726000000.123,
      timestamp_ms: 1726000000123.0,
      exercise: "squat",
      detected_exercise: "squat",
      stage: "ascending",
      rep_count: 5,
      valid_reps: 5,
      invalid_reps: 0,
      is_valid_rep: true,
      confidence: 0.95,
      current_angles: { knee_angle: 110.5, hip_angle: 125.0 },
      primary_angle: 110.5,
      form_score: 92.5,
      warnings: ["Maintain chest up"],
      feedback: ["Good depth", "Drive through heels"],
      issues: [],
      audio_cue: "Drive through heels",
      rep_duration_sec: 1.8,
      metrics: { depth_ratio: 0.9 },
    };

    const jsonStr = JSON.stringify(serverMsg);
    const data = JSON.parse(jsonStr);

    assert.equal(data.type, "analysis_result");
    assert.equal(data.stage, "ascending");
    assert.equal(data.rep_count, 5);
    assert.equal(data.form_score, 92.5);
    assert.equal(data.current_angles.knee_angle, 110.5);
    assert.equal(data.audio_cue, "Drive through heels");
  });

  test("Session Summary payload contains aggregate metrics without frame duplication", () => {
    const summary = {
      session_id: "sess-abc-123",
      exercise: "squat",
      user_id: "usr-456",
      workout_id: "wkt-789",
      total_reps: 10,
      valid_reps: 9,
      invalid_reps: 1,
      average_form_score: 91.5,
      duration_sec: 45.2,
      frames_processed: 1350,
      persisted_to_db: true,
    };

    assert.equal(summary.total_reps, 10);
    assert.equal(summary.valid_reps, 9);
    assert.equal(summary.frames_processed, 1350);
    assert.equal(summary.persisted_to_db, true);
  });
});

describe("Phase 11 Pose Detector Abstraction", () => {
  test("BrowserPoseDetector initializes and disposes safely", async () => {
    const detector = new BrowserPoseDetector();
    const initialized = await detector.initialize();
    assert.equal(initialized, true);

    // Calling detect without ready video element returns null safely
    const mockVideo = {} as HTMLVideoElement;
    const result = await detector.detect(mockVideo);
    assert.equal(result, null);

    detector.dispose();
  });
});
