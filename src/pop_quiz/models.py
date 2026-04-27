"""Data models for the quiz application."""

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Self

import yaml


class QuizPhase(StrEnum):
    """Phases of a quiz game."""

    LOBBY = "lobby"
    COUNTDOWN = "countdown"
    QUESTION = "question"
    REVEAL = "reveal"
    FINISHED = "finished"


@dataclass(slots=True, frozen=True)
class Question:
    """A single quiz question with multiple choice answers."""

    text: str
    choices: list[str]
    correct_index: int
    time_limit_seconds: int = 30
    image_url: str | None = None

    def __post_init__(self) -> None:
        if not 0 <= self.correct_index < len(self.choices):
            raise ValueError(
                f"correct_index {self.correct_index} out of range for {len(self.choices)} choices"
            )
        if not 2 <= len(self.choices) <= 6:
            raise ValueError(f"Need 2-6 choices, got {len(self.choices)}")


@dataclass(slots=True)
class Quiz:
    """A complete quiz with metadata and questions."""

    title: str
    questions: list[Question]
    description: str = ""

    @classmethod
    def from_yaml(cls, path: Path) -> Self:
        """Load a quiz from a YAML file."""
        data = yaml.safe_load(path.read_text())
        questions = [
            Question(
                text=q["question"],
                choices=q["choices"],
                correct_index=q["correct"],
                time_limit_seconds=q.get("time_limit", 30),
                image_url=q.get("image"),
            )
            for q in data["questions"]
        ]
        return cls(
            title=data["title"],
            description=data.get("description", ""),
            questions=questions,
        )


@dataclass(slots=True)
class Participant:
    """A quiz participant."""

    id: str
    display_name: str
    score: int = 0
    answers: dict[int, int] = field(default_factory=dict)
    answer_times_seconds: dict[int, float] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class Answer:
    """An answer submission from a participant."""

    participant_id: str
    question_index: int
    choice_index: int
