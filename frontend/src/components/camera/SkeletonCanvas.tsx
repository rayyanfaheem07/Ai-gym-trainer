"use client";

import React, { useRef, useEffect } from "react";
import { LandmarkPoint } from "@/types";

interface SkeletonCanvasProps {
  landmarks?: LandmarkPoint[];
  width?: number;
  height?: number;
}

const POSE_CONNECTIONS: [number, number][] = [
  // Upper body
  [11, 12], // Left Shoulder - Right Shoulder
  [11, 13], // Left Shoulder - Left Elbow
  [13, 15], // Left Elbow - Left Wrist
  [12, 14], // Right Shoulder - Right Elbow
  [14, 16], // Right Elbow - Right Wrist
  // Torso
  [11, 23], // Left Shoulder - Left Hip
  [12, 24], // Right Shoulder - Right Hip
  [23, 24], // Left Hip - Right Hip
  // Lower body
  [23, 25], // Left Hip - Left Knee
  [25, 27], // Left Knee - Left Ankle
  [24, 26], // Right Hip - Right Knee
  [26, 28], // Right Knee - Right Ankle
];

export const SkeletonCanvas: React.FC<SkeletonCanvasProps> = ({
  landmarks = [],
  width = 640,
  height = 480,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.clearRect(0, 0, width, height);

    if (!landmarks || landmarks.length < 33) return;

    // Draw skeletal bone lines
    ctx.lineWidth = 3;
    ctx.strokeStyle = "rgba(16, 185, 129, 0.75)"; // Emerald-500
    ctx.lineCap = "round";

    POSE_CONNECTIONS.forEach(([startIdx, endIdx]) => {
      const p1 = landmarks[startIdx];
      const p2 = landmarks[endIdx];

      if (p1 && p2 && (p1.visibility ?? 1) > 0.4 && (p2.visibility ?? 1) > 0.4) {
        ctx.beginPath();
        ctx.moveTo(p1.x * width, p1.y * height);
        ctx.lineTo(p2.x * width, p2.y * height);
        ctx.stroke();
      }
    });

    // Draw landmark keypoint dots
    landmarks.forEach((lm) => {
      if ((lm.visibility ?? 1) > 0.4) {
        ctx.beginPath();
        ctx.arc(lm.x * width, lm.y * height, 4.5, 0, 2 * Math.PI);
        ctx.fillStyle = "#10B981";
        ctx.fill();
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 1.5;
        ctx.stroke();
      }
    });
  }, [landmarks, width, height]);

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
      className="absolute inset-0 w-full h-full pointer-events-none transform -scale-x-100"
    />
  );
};
