"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import {
  AnalysisResultResponse,
  LandmarkPoint,
  SessionStartedResponse,
  SessionStoppedResponse,
  SessionSummary,
  WSServerMessage,
} from "@/types";

export type WSConnectionStatus = "disconnected" | "connecting" | "connected" | "error";

interface UseWebSocketOptions {
  onAnalysisResult?: (result: AnalysisResultResponse) => void;
  onSessionStarted?: (started: SessionStartedResponse) => void;
  onSessionStopped?: (stopped: SessionStoppedResponse) => void;
  onError?: (code: string, message: string) => void;
}

export function useWebSocket(options: UseWebSocketOptions = {}) {
  const [status, setStatus] = useState<WSConnectionStatus>("disconnected");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [latestAnalysis, setLatestAnalysis] = useState<AnalysisResultResponse | null>(null);
  const [lastSummary, setLastSummary] = useState<SessionSummary | null>(null);
  const [lastError, setLastError] = useState<{ code: string; message: string } | null>(null);

  const socketRef = useRef<WebSocket | null>(null);
  const pingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const optionsRef = useRef(options);
  optionsRef.current = options;

  const getWsBaseUrl = useCallback(() => {
    if (process.env.NEXT_PUBLIC_WS_URL) {
      return process.env.NEXT_PUBLIC_WS_URL;
    }
    if (typeof window !== "undefined") {
      const loc = window.location;
      const protocol = loc.protocol === "https:" ? "wss:" : "ws:";
      const host = loc.hostname;
      const port = "8000"; // default backend port
      return `${protocol}//${host}:${port}/api/v1/ws/stream`;
    }
    return "ws://localhost:8000/api/v1/ws/stream";
  }, []);

  const disconnect = useCallback(() => {
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }
    if (socketRef.current) {
      try {
        socketRef.current.close(1000, "Client closed connection");
      } catch {
        // ignore
      }
      socketRef.current = null;
    }
    setStatus("disconnected");
  }, []);

  const connect = useCallback(
    (token: string) => {
      if (!token) {
        setLastError({ code: "AUTH_REQUIRED", message: "Missing JWT authentication token." });
        setStatus("error");
        return;
      }

      disconnect();
      setStatus("connecting");
      setLastError(null);

      const baseUrl = getWsBaseUrl();
      const wsUrl = `${baseUrl}${baseUrl.includes("?") ? "&" : "?"}token=${encodeURIComponent(token)}`;

      try {
        const ws = new WebSocket(wsUrl);
        socketRef.current = ws;

        ws.onopen = () => {
          // Heartbeat interval every 15s
          pingIntervalRef.current = setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
              ws.send(JSON.stringify({ type: "ping" }));
            }
          }, 15000);
        };

        ws.onmessage = (event) => {
          try {
            const data: WSServerMessage = JSON.parse(event.data);

            if (data.type === "connected") {
              setStatus("connected");
              setSessionId(data.session_id);
              setLastError(null);
            } else if (data.type === "analysis_result") {
              setLatestAnalysis(data);
              optionsRef.current.onAnalysisResult?.(data);
            } else if (data.type === "session_started") {
              setSessionId(data.session_id);
              optionsRef.current.onSessionStarted?.(data);
            } else if (data.type === "session_stopped") {
              setLastSummary(data.summary);
              optionsRef.current.onSessionStopped?.(data);
            } else if (data.type === "pong") {
              // pong received
            } else if (data.type === "error") {
              setLastError({ code: data.code, message: data.message });
              optionsRef.current.onError?.(data.code, data.message);
            }
          } catch (parseErr) {
            console.warn("WebSocket parse warning:", parseErr);
          }
        };

        ws.onerror = () => {
          setStatus("error");
          setLastError({
            code: "WS_CONNECTION_ERROR",
            message: "Unable to establish WebSocket connection with the AI server.",
          });
        };

        ws.onclose = (event) => {
          if (pingIntervalRef.current) {
            clearInterval(pingIntervalRef.current);
            pingIntervalRef.current = null;
          }
          if (event.code === 1008) {
            setStatus("error");
            setLastError({
              code: "AUTH_FAILED",
              message: "Authentication failed. Token is invalid, expired, or missing.",
            });
          } else {
            setStatus("disconnected");
          }
        };
      } catch (err: any) {
        setStatus("error");
        setLastError({
          code: "WS_INIT_FAILED",
          message: err.message || "Failed to initialize WebSocket.",
        });
      }
    },
    [disconnect, getWsBaseUrl]
  );

  const sendMessage = useCallback((msg: object) => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify(msg));
      return true;
    }
    return false;
  }, []);

  const startSession = useCallback(
    (exercise: string = "squat", workoutId?: string) => {
      return sendMessage({
        type: "start_session",
        exercise,
        workout_id: workoutId || undefined,
      });
    },
    [sendMessage]
  );

  const stopSession = useCallback(
    (saveToDb: boolean = true) => {
      return sendMessage({
        type: "stop_session",
        save_to_db: saveToDb,
      });
    },
    [sendMessage]
  );

  const sendPoseFrame = useCallback(
    (landmarks: LandmarkPoint[], exercise?: string) => {
      return sendMessage({
        type: "pose_frame",
        timestamp_ms: Date.now(),
        exercise,
        landmarks,
      });
    },
    [sendMessage]
  );

  const setExercise = useCallback(
    (exercise: string) => {
      return sendMessage({
        type: "set_exercise",
        exercise,
      });
    },
    [sendMessage]
  );

  const reset = useCallback(() => {
    return sendMessage({ type: "reset" });
  }, [sendMessage]);

  const ping = useCallback(() => {
    return sendMessage({ type: "ping" });
  }, [sendMessage]);

  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  return {
    status,
    sessionId,
    latestAnalysis,
    lastSummary,
    lastError,
    connect,
    disconnect,
    startSession,
    stopSession,
    sendPoseFrame,
    setExercise,
    reset,
    ping,
  };
}
