"use client";

import { useState, useRef, useCallback, useEffect } from "react";

export interface CameraState {
  isActive: boolean;
  isLoading: boolean;
  error: string | null;
  permissionDenied: boolean;
}

export function useCamera() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [cameraState, setCameraState] = useState<CameraState>({
    isActive: false,
    isLoading: false,
    error: null,
    permissionDenied: false,
  });

  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setCameraState({
      isActive: false,
      isLoading: false,
      error: null,
      permissionDenied: false,
    });
  }, []);

  const startCamera = useCallback(async (constraints?: MediaStreamConstraints) => {
    setCameraState({
      isActive: false,
      isLoading: true,
      error: null,
      permissionDenied: false,
    });

    if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      setCameraState({
        isActive: false,
        isLoading: false,
        error: "Camera access is not supported by your browser.",
        permissionDenied: false,
      });
      return false;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia(
        constraints || {
          video: {
            width: { ideal: 640 },
            height: { ideal: 480 },
            frameRate: { ideal: 30, max: 30 },
            facingMode: "user",
          },
          audio: false,
        }
      );

      streamRef.current = stream;

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }

      setCameraState({
        isActive: true,
        isLoading: false,
        error: null,
        permissionDenied: false,
      });
      return true;
    } catch (err: any) {
      const isDenied =
        err.name === "NotAllowedError" ||
        err.name === "PermissionDeniedError" ||
        err.message?.includes("Permission denied");

      setCameraState({
        isActive: false,
        isLoading: false,
        error: isDenied
          ? "Camera permission denied. Please allow camera access in your browser settings to track form."
          : err.message || "Failed to start camera feed.",
        permissionDenied: isDenied,
      });
      return false;
    }
  }, []);

  useEffect(() => {
    return () => {
      stopCamera();
    };
  }, [stopCamera]);

  return {
    videoRef,
    cameraState,
    startCamera,
    stopCamera,
  };
}
