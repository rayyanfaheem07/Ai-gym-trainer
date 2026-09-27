# Real-Time Telemetry Flow Diagram

This diagram documents the sub-10ms per-frame real-time telemetry pipeline, showing how pose frames are generated in the browser, streamed over WebSockets, evaluated in memory, and returned to the athlete's HUD.

```mermaid
sequenceDiagram
    autonumber
    actor Athlete
    participant Camera as Browser Camera
    participant Detector as MediaPipe Pose (Client)
    participant WSClient as Frontend WebSocket
    participant HUD as React Workout HUD
    participant WSServer as FastAPI WebSocket Endpoint
    participant Tracker as WebSocketSessionTracker
    participant Analyzer as ExerciseAnalyzer (FSM)
    participant Rules as Form Violation Engine
    participant DB as PostgreSQL Database

    Athlete->>Camera: Performs exercise movement
    Camera->>Detector: Raw RGB frame (30 FPS)
    Detector->>WSClient: 33 body keypoints (x, y, z, visibility)
    WSClient->>WSServer: pose_frame JSON packet (<= 1MB)
    
    critical In-Memory Frame Processing (~0.6ms)
        WSServer->>Tracker: parse_landmarks_to_numpy()
        Tracker->>Analyzer: analyze_frame(landmarks, timestamp_ms)
        Analyzer->>Analyzer: Calculate 3D joint angles (hip, knee, ankle, elbow)
        Analyzer->>Analyzer: Update FSM state (START -> INFLECTION -> COMPLETE)
        Analyzer->>Rules: Evaluate safety violations & form deviations
        Rules-->>Analyzer: Detected biomechanical issues & penalties
        Analyzer-->>Tracker: Rep count, phase, form score, feedback text
    end

    Tracker-->>WSServer: Formatted analysis_result packet
    WSServer-->>WSClient: analysis_result JSON (WebSocket)
    WSClient-->>HUD: Update repetition counters, gauges, audio cue

    Note over WSServer,DB: NO database writes occur during active streaming!

    opt Athlete completes session (stop_session)
        WSClient->>WSServer: stop_session (save_to_db=true)
        WSServer->>Tracker: stop_session()
        Tracker->>DB: Persist aggregated ExerciseSession & FormIssues
        DB-->>Tracker: Committed session record
        Tracker-->>WSClient: session_stopped with summary payload
        WSClient-->>HUD: Display workout summary modal
    end
```

### Key Architectural Constraints
1. **Zero Database I/O per Frame**: Frame ingestion and biomechanical evaluation run strictly in memory to sustain 30+ FPS throughput without database lock contention.
2. **Deterministic State Transitions**: State transitions (`UP` -> `DOWN` -> `UP`) require hysteresis thresholds (e.g., knee flexion < 100° for squat descent, > 160° for lockout) to prevent double counting from sensor noise.
3. **Payload Protection**: Messages exceeding 1 MB are dropped with `PAYLOAD_TOO_LARGE` errors to protect the event loop.
