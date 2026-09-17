from typing import Dict, List, Tuple

import cv2
import numpy as np

from ai.pose.landmarks import POSE_CONNECTIONS, LandmarkIndex


class PoseVisualizer:
    """
    Renders skeleton overlays, joint angles, squat analytics, and HUD on OpenCV image frames.
    """

    # Color definitions (BGR for OpenCV)
    COLOR_NEON_GREEN = (16, 240, 129)   # #10B981 (RGB) -> (16, 240, 129) (BGR)
    COLOR_CYAN = (212, 182, 6)          # #06B6D4 (RGB) -> (6, 182, 212) (BGR)
    COLOR_AMBER = (11, 158, 245)        # #F59E0B (RGB) -> (11, 158, 245) (BGR)
    COLOR_ROSE = (94, 63, 244)          # #F43F5E (RGB) -> (94, 63, 244) (BGR)
    COLOR_WHITE = (255, 255, 255)
    COLOR_DARK_BG = (22, 13, 9)         # Dark slate HUD background

    def __init__(
        self,
        min_visibility: float = 0.5,
        joint_radius: int = 5,
        bone_thickness: int = 2,
    ):
        self.min_visibility = min_visibility
        self.joint_radius = joint_radius
        self.bone_thickness = bone_thickness

    def draw_skeleton(
        self,
        frame: np.ndarray,
        landmarks: np.ndarray,
        color_joints: Tuple[int, int, int] = COLOR_NEON_GREEN,
        color_bones: Tuple[int, int, int] = COLOR_CYAN,
    ) -> np.ndarray:
        """Draws skeleton bone connections and keypoint circles on an OpenCV frame."""
        if landmarks is None or len(landmarks) < 33:
            return frame

        h, w, _ = frame.shape

        for start_idx, end_idx in POSE_CONNECTIONS:
            pt1 = landmarks[start_idx]
            pt2 = landmarks[end_idx]

            if pt1[3] >= self.min_visibility and pt2[3] >= self.min_visibility:
                x1, y1 = int(pt1[0] * w), int(pt1[1] * h)
                x2, y2 = int(pt2[0] * w), int(pt2[1] * h)
                cv2.line(frame, (x1, y1), (x2, y2), color_bones, self.bone_thickness, cv2.LINE_AA)

        for idx in range(33):
            lm = landmarks[idx]
            if lm[3] >= self.min_visibility:
                cx, cy = int(lm[0] * w), int(lm[1] * h)
                cv2.circle(frame, (cx, cy), self.joint_radius + 2, (0, 0, 0), -1, cv2.LINE_AA)
                cv2.circle(frame, (cx, cy), self.joint_radius, color_joints, -1, cv2.LINE_AA)

        return frame

    def draw_joint_angles(
        self,
        frame: np.ndarray,
        landmarks: np.ndarray,
        angles: Dict[str, float],
    ) -> np.ndarray:
        """Overlays numerical joint angles next to their anatomical positions."""
        if landmarks is None or len(landmarks) < 33:
            return frame

        h, w, _ = frame.shape

        joint_mapping = {
            "left_elbow": LandmarkIndex.LEFT_ELBOW,
            "right_elbow": LandmarkIndex.RIGHT_ELBOW,
            "left_knee": LandmarkIndex.LEFT_KNEE,
            "right_knee": LandmarkIndex.RIGHT_KNEE,
            "left_hip": LandmarkIndex.LEFT_HIP,
            "right_hip": LandmarkIndex.RIGHT_HIP,
        }

        for name, angle_val in angles.items():
            if name in joint_mapping:
                idx = joint_mapping[name]
                lm = landmarks[idx]
                if lm[3] >= self.min_visibility:
                    cx, cy = int(lm[0] * w), int(lm[1] * h)
                    text = f"{int(round(angle_val))} deg"
                    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
                    cv2.rectangle(
                        frame,
                        (cx + 8, cy - th - 6),
                        (cx + 12 + tw, cy + 4),
                        (15, 15, 15),
                        -1,
                    )
                    cv2.putText(
                        frame,
                        text,
                        (cx + 10, cy - 2),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.45,
                        self.COLOR_AMBER,
                        1,
                        cv2.LINE_AA,
                    )

        return frame

    def draw_hud(
        self,
        frame: np.ndarray,
        fps: float,
        has_detection: bool,
    ) -> np.ndarray:
        """Renders the top HUD status banner with FPS and detection indicators."""
        h, w, _ = frame.shape

        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 52), (10, 14, 23), -1)
        cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

        fps_text = f"FPS: {fps:.1f}"
        cv2.putText(
            frame,
            fps_text,
            (16, 32),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            self.COLOR_WHITE,
            2,
            cv2.LINE_AA,
        )

        if has_detection:
            status_text = "TRACKING ACTIVE"
            badge_color = self.COLOR_NEON_GREEN
        else:
            status_text = "SEARCHING FOR PERSON..."
            badge_color = self.COLOR_ROSE

        cv2.circle(frame, (160, 27), 6, badge_color, -1, cv2.LINE_AA)
        cv2.putText(
            frame,
            status_text,
            (176, 32),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            badge_color,
            2,
            cv2.LINE_AA,
        )

        return frame

    def draw_squat_analytics(
        self,
        frame: np.ndarray,
        phase: str,
        rep_count: int,
        valid_reps: int,
        knee_angle: float,
        target_bottom_angle: float = 95.0,
        feedback: List[str] | None = None,
    ) -> np.ndarray:
        """
        Renders real-time squat analysis overlays:
        - Large rep count badge (bottom left)
        - Phase badge with color coding (bottom left)
        - Depth progress gauge / bar (bottom center)
        - Active corrective feedback banner (top middle)
        """
        h, w, _ = frame.shape

        # 1. Rep Count & Phase Badge Card (Bottom Left)
        card_w, card_h = 210, 110
        card_x, card_y = 16, h - card_h - 16

        overlay = frame.copy()
        cv2.rectangle(overlay, (card_x, card_y), (card_x + card_w, card_y + card_h), (10, 14, 23), -1)
        cv2.addWeighted(overlay, 0.85, frame, 0.15, 0, frame)
        cv2.rectangle(frame, (card_x, card_y), (card_x + card_w, card_y + card_h), (40, 50, 70), 1)

        # Rep Counter Header
        cv2.putText(frame, "SQUAT REPS", (card_x + 14, card_y + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1, cv2.LINE_AA)
        cv2.putText(frame, f"{rep_count}", (card_x + 14, card_y + 70), cv2.FONT_HERSHEY_SIMPLEX, 1.4, self.COLOR_NEON_GREEN, 3, cv2.LINE_AA)
        cv2.putText(frame, f"({valid_reps} valid)", (card_x + 95, card_y + 65), cv2.FONT_HERSHEY_SIMPLEX, 0.5, self.COLOR_WHITE, 1, cv2.LINE_AA)

        # Phase Badge with dynamic color
        phase_colors = {
            "standing": (180, 180, 180),
            "descending": self.COLOR_AMBER,
            "bottom": self.COLOR_NEON_GREEN,
            "ascending": self.COLOR_CYAN,
            "completed_rep": self.COLOR_NEON_GREEN,
        }
        phase_color = phase_colors.get(phase.lower(), self.COLOR_WHITE)
        phase_label = f"PHASE: {phase.upper()}"
        cv2.putText(frame, phase_label, (card_x + 14, card_y + 96), cv2.FONT_HERSHEY_SIMPLEX, 0.45, phase_color, 1, cv2.LINE_AA)

        # 2. Depth Progress Bar (Bottom Center)
        bar_x = card_x + card_w + 20
        bar_y = h - 45
        bar_w = 260
        bar_h = 16

        # Calculate progress towards depth (180 -> standing, 95 -> bottom depth)
        clamped_angle = max(target_bottom_angle, min(180.0, knee_angle))
        depth_pct = max(0.0, min(1.0, (180.0 - clamped_angle) / (180.0 - target_bottom_angle)))
        fill_w = int(bar_w * depth_pct)

        # Draw gauge background
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (25, 30, 45), -1)
        # Draw gauge fill
        fill_color = self.COLOR_NEON_GREEN if knee_angle <= target_bottom_angle else self.COLOR_AMBER
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + fill_w, bar_y + bar_h), fill_color, -1)
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (70, 80, 100), 1)

        gauge_text = f"Depth: {int(knee_angle)} deg / Target: {int(target_bottom_angle)} deg"
        cv2.putText(frame, gauge_text, (bar_x, bar_y - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, self.COLOR_WHITE, 1, cv2.LINE_AA)

        # 3. Form Feedback Banner (Top Center)
        if feedback and len(feedback) > 0:
            fb_text = feedback[0]
            (tw, th), _ = cv2.getTextSize(fb_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            fb_x = (w - tw) // 2
            fb_y = 90
            cv2.rectangle(frame, (fb_x - 16, fb_y - th - 10), (fb_x + tw + 16, fb_y + 10), (15, 20, 180), -1)
            cv2.putText(frame, fb_text, (fb_x, fb_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, self.COLOR_WHITE, 2, cv2.LINE_AA)

        return frame
