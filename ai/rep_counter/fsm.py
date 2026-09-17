import enum


class RepStage(str, enum.Enum):
    START = "START"
    ECCENTRIC = "ECCENTRIC"       # Lowering / loading phase
    INFLECTION = "INFLECTION"     # Peak stretch / turnaround point
    CONCENTRIC = "CONCENTRIC"     # Pushing / lifting phase
    COMPLETED = "COMPLETED"       # Returned to lockout


class RepStateCounter:
    """
    Generic Finite State Machine for rep counting with hysteresis.
    """

    def __init__(
        self,
        start_threshold: float = 160.0,
        inflection_threshold: float = 90.0,
        hysteresis_deg: float = 5.0,
    ):
        self.start_threshold = start_threshold
        self.inflection_threshold = inflection_threshold
        self.hysteresis = hysteresis_deg
        self.stage = RepStage.START
        self.rep_count = 0

    def update(self, angle: float) -> tuple[RepStage, bool]:
        """
        Updates the FSM state given current joint angle.

        Returns:
            (current_stage, rep_completed_flag)
        """
        rep_completed = False

        if self.stage == RepStage.START:
            if angle < (self.start_threshold - self.hysteresis):
                self.stage = RepStage.ECCENTRIC

        elif self.stage == RepStage.ECCENTRIC:
            if angle <= self.inflection_threshold:
                self.stage = RepStage.INFLECTION
            elif angle > (self.start_threshold - self.hysteresis):
                self.stage = RepStage.START  # Incomplete / aborted rep

        elif self.stage == RepStage.INFLECTION:
            if angle > (self.inflection_threshold + self.hysteresis):
                self.stage = RepStage.CONCENTRIC

        elif self.stage == RepStage.CONCENTRIC:
            if angle >= self.start_threshold:
                self.stage = RepStage.START
                self.rep_count += 1
                rep_completed = True

        return self.stage, rep_completed

    def reset(self):
        self.stage = RepStage.START
        self.rep_count = 0
