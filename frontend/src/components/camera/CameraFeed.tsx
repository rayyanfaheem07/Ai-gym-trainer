"use client";

import React, { forwardRef } from "react";
import { Camera, CameraOff, Loader2 } from "lucide-react";
import { CameraState } from "@/hooks/useCamera";

interface CameraFeedProps {
  cameraState: CameraState;
  onRetry?: () => void;
}

export const CameraFeed = forwardRef<HTMLVideoElement, CameraFeedProps>(
  ({ cameraState, onRetry }, ref) => {
    const { isActive, isLoading, error, permissionDenied } = cameraState;

    return (
      <div className="relative w-full aspect-video bg-gray-950 rounded-2xl overflow-hidden border border-gray-800 flex items-center justify-center shadow-inner">
        {/* Live Webcam Video */}
        <video
          ref={ref}
          autoPlay
          playsInline
          muted
          className={`w-full h-full object-cover transform -scale-x-100 ${
            !isActive ? "hidden" : "block"
          }`}
        />

        {/* Loading State */}
        {isLoading && (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-gray-400 gap-3 bg-gray-950/80 backdrop-blur-sm">
            <Loader2 className="w-8 h-8 animate-spin text-emerald-400" />
            <span className="text-sm font-medium">Requesting camera permissions...</span>
          </div>
        )}

        {/* Error / Permission Denied State */}
        {error && !isLoading && (
          <div className="absolute inset-0 flex flex-col items-center justify-center p-6 text-center bg-gray-950/90 gap-3">
            <div className="w-12 h-12 rounded-2xl bg-rose-500/10 border border-rose-500/20 flex items-center justify-center text-rose-400">
              <CameraOff className="w-6 h-6" />
            </div>
            <div className="max-w-sm">
              <h4 className="font-bold text-white text-sm">
                {permissionDenied ? "Camera Access Denied" : "Camera Error"}
              </h4>
              <p className="text-xs text-rose-300/80 mt-1">{error}</p>
            </div>
            {onRetry && (
              <button
                onClick={onRetry}
                className="mt-2 px-4 py-1.5 rounded-xl bg-gray-800 hover:bg-gray-700 text-white text-xs font-semibold transition-all"
              >
                Retry Camera
              </button>
            )}
          </div>
        )}

        {/* Inactive Standby State */}
        {!isActive && !isLoading && !error && (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-gray-500 gap-2">
            <Camera className="w-8 h-8" />
            <span className="text-xs">Camera standby — Click Start to begin</span>
          </div>
        )}
      </div>
    );
  }
);

CameraFeed.displayName = "CameraFeed";
