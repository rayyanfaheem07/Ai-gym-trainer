/**
 * Browser-compatible MediaPipe Pose landmark extractor and abstraction.
 * Generates standardized 33-point body landmarks matching MediaPipe's topology.
 */

import type { LandmarkPoint } from "../types/websocket";

export interface PoseDetectionResult {
  landmarks: LandmarkPoint[];
  timestamp_ms: number;
}

// MediaPipe 33 Landmark Indices
export const POSE_LANDMARKS = {
  NOSE: 0,
  LEFT_EYE_INNER: 1,
  LEFT_EYE: 2,
  LEFT_EYE_OUTER: 3,
  RIGHT_EYE_INNER: 4,
  RIGHT_EYE: 5,
  RIGHT_EYE_OUTER: 6,
  LEFT_EAR: 7,
  RIGHT_EAR: 8,
  MOUTH_LEFT: 9,
  MOUTH_RIGHT: 10,
  LEFT_SHOULDER: 11,
  RIGHT_SHOULDER: 12,
  LEFT_ELBOW: 13,
  RIGHT_ELBOW: 14,
  LEFT_WRIST: 15,
  RIGHT_WRIST: 16,
  LEFT_PINKY: 17,
  RIGHT_PINKY: 18,
  LEFT_INDEX: 19,
  RIGHT_INDEX: 20,
  LEFT_THUMB: 21,
  RIGHT_THUMB: 22,
  LEFT_HIP: 23,
  RIGHT_HIP: 24,
  LEFT_KNEE: 25,
  RIGHT_KNEE: 26,
  LEFT_ANKLE: 27,
  RIGHT_ANKLE: 28,
  LEFT_HEEL: 29,
  RIGHT_HEEL: 30,
  LEFT_FOOT_INDEX: 31,
  RIGHT_FOOT_INDEX: 32,
};

export class BrowserPoseDetector {
  private isInitialized: boolean = false;
  private mediaPipePoseInstance: any = null;

  async initialize(): Promise<boolean> {
    if (this.isInitialized) return true;

    // Check if window.Pose (MediaPipe Pose CDN) is loaded
    if (typeof window !== "undefined" && (window as any).Pose) {
      try {
        const PoseConstructor = (window as any).Pose;
        this.mediaPipePoseInstance = new PoseConstructor({
          locateFile: (file: string) => `https://cdn.jsdelivr.net/npm/@mediapipe/pose/${file}`,
        });
        this.mediaPipePoseInstance.setOptions({
          modelComplexity: 1,
          smoothLandmarks: true,
          minDetectionConfidence: 0.5,
          minTrackingConfidence: 0.5,
        });
        this.isInitialized = true;
        return true;
      } catch (err) {
        console.warn("Failed initializing MediaPipe CDN instance:", err);
      }
    }

    this.isInitialized = true;
    return true;
  }

  async detect(videoElement: HTMLVideoElement): Promise<LandmarkPoint[] | null> {
    if (!videoElement || videoElement.readyState < 2) {
      return null;
    }

    if (this.mediaPipePoseInstance) {
      return new Promise<LandmarkPoint[] | null>((resolve) => {
        this.mediaPipePoseInstance.onResults((results: any) => {
          if (results && results.poseLandmarks && results.poseLandmarks.length >= 33) {
            const formatted: LandmarkPoint[] = results.poseLandmarks.map((lm: any) => ({
              x: lm.x,
              y: lm.y,
              z: lm.z ?? 0,
              visibility: lm.visibility ?? 1.0,
            }));
            resolve(formatted);
          } else {
            resolve(null);
          }
        });
        this.mediaPipePoseInstance.send({ image: videoElement }).catch(() => resolve(null));
      });
    }

    return null;
  }

  dispose(): void {
    if (this.mediaPipePoseInstance && typeof this.mediaPipePoseInstance.close === "function") {
      try {
        this.mediaPipePoseInstance.close();
      } catch {
        // ignore
      }
    }
    this.mediaPipePoseInstance = null;
    this.isInitialized = false;
  }
}
