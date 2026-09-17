from typing import Dict, Type

from ai.exercises.base import BaseExerciseAnalyzer
from ai.exercises.bicep_curl import BicepCurlExercise
from ai.exercises.lunge import LungeExercise
from ai.exercises.pushup import PushupExercise
from ai.exercises.shoulder_press import ShoulderPressExercise
from ai.exercises.squat import SquatDetector


class ExerciseRegistry:
    """
    Factory registry for dynamically creating exercise analyzers.
    Adheres to Open-Closed Principle: New exercises can be registered at runtime
    without modifying existing exercise implementations.
    """

    _registry: Dict[str, Type[BaseExerciseAnalyzer]] = {
        "squat": SquatDetector,
        "pushup": PushupExercise,
        "bicep_curl": BicepCurlExercise,
        "lunge": LungeExercise,
        "shoulder_press": ShoulderPressExercise,
    }

    @classmethod
    def get_exercise(cls, name: str, **kwargs) -> BaseExerciseAnalyzer | None:
        """Instantiates registered exercise analyzer by name."""
        exercise_class = cls._registry.get(name.lower())
        if exercise_class:
            return exercise_class(**kwargs)
        return None

    @classmethod
    def register(cls, name: str, exercise_class: Type[BaseExerciseAnalyzer]) -> None:
        """Dynamically registers a new exercise analyzer."""
        cls._registry[name.lower()] = exercise_class

    @classmethod
    def list_available(cls) -> list[str]:
        """Returns list of all available registered exercise names."""
        return list(cls._registry.keys())
