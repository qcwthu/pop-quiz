"""Tests for the models module."""

import tempfile
from pathlib import Path

import pytest

from pop_quiz.models import Answer, Participant, Question, Quiz, QuizPhase


class TestQuizPhase:
    """Tests for the QuizPhase enum."""

    def test_all_phases_are_strings(self) -> None:
        """All phase values should be lowercase strings."""
        for phase in QuizPhase:
            assert isinstance(phase.value, str)
            assert phase.value == phase.value.lower()

    def test_phase_values(self) -> None:
        """Phases should have expected string values."""
        assert QuizPhase.LOBBY == "lobby"
        assert QuizPhase.COUNTDOWN == "countdown"
        assert QuizPhase.QUESTION == "question"
        assert QuizPhase.REVEAL == "reveal"
        assert QuizPhase.FINISHED == "finished"

    def test_phase_count(self) -> None:
        """Should have exactly 5 phases."""
        assert len(QuizPhase) == 5


class TestQuestion:
    """Tests for the Question dataclass."""

    def test_valid_question(self) -> None:
        """Should create a question with valid parameters."""
        q = Question(
            text="What is 2+2?",
            choices=["3", "4", "5", "6"],
            correct_index=1,
        )
        assert q.text == "What is 2+2?"
        assert len(q.choices) == 4
        assert q.correct_index == 1
        assert q.time_limit_seconds == 30  # default
        assert q.image_url is None

    def test_question_with_custom_time_limit(self) -> None:
        """Should accept custom time limit."""
        q = Question(
            text="Quick question",
            choices=["A", "B"],
            correct_index=0,
            time_limit_seconds=10,
        )
        assert q.time_limit_seconds == 10

    def test_question_with_image(self) -> None:
        """Should accept image URL."""
        q = Question(
            text="What animal is this?",
            choices=["Cat", "Dog"],
            correct_index=0,
            image_url="https://example.com/cat.jpg",
        )
        assert q.image_url == "https://example.com/cat.jpg"

    def test_correct_index_out_of_range_high(self) -> None:
        """Should raise error when correct_index >= len(choices)."""
        with pytest.raises(ValueError, match="correct_index .* out of range"):
            Question(
                text="Test",
                choices=["A", "B", "C"],
                correct_index=3,
            )

    def test_correct_index_out_of_range_negative(self) -> None:
        """Should raise error when correct_index is negative."""
        with pytest.raises(ValueError, match="correct_index .* out of range"):
            Question(
                text="Test",
                choices=["A", "B"],
                correct_index=-1,
            )

    def test_too_few_choices(self) -> None:
        """Should raise error with less than 2 choices."""
        with pytest.raises(ValueError, match="Need 2-6 choices"):
            Question(
                text="Test",
                choices=["Only one"],
                correct_index=0,
            )

    def test_too_many_choices(self) -> None:
        """Should raise error with more than 6 choices."""
        with pytest.raises(ValueError, match="Need 2-6 choices"):
            Question(
                text="Test",
                choices=["A", "B", "C", "D", "E", "F", "G"],
                correct_index=0,
            )

    def test_minimum_choices(self) -> None:
        """Should accept exactly 2 choices."""
        q = Question(
            text="True or False?", choices=["True", "False"], correct_index=0
        )
        assert len(q.choices) == 2

    def test_maximum_choices(self) -> None:
        """Should accept exactly 6 choices."""
        q = Question(
            text="Pick one",
            choices=["A", "B", "C", "D", "E", "F"],
            correct_index=5,
        )
        assert len(q.choices) == 6

    def test_question_is_frozen(self) -> None:
        """Question should be immutable."""
        q = Question(text="Test", choices=["A", "B"], correct_index=0)
        with pytest.raises(AttributeError):
            q.text = "Changed"  # type: ignore[misc]


class TestQuiz:
    """Tests for the Quiz dataclass."""

    def test_quiz_creation(self) -> None:
        """Should create a quiz with questions."""
        questions = [
            Question(text="Q1", choices=["A", "B"], correct_index=0),
            Question(text="Q2", choices=["X", "Y", "Z"], correct_index=2),
        ]
        quiz = Quiz(title="My Quiz", questions=questions)
        assert quiz.title == "My Quiz"
        assert len(quiz.questions) == 2
        assert quiz.description == ""

    def test_quiz_with_description(self) -> None:
        """Should accept optional description."""
        quiz = Quiz(
            title="Science Quiz",
            questions=[
                Question(text="Q", choices=["A", "B"], correct_index=0)
            ],
            description="Test your science knowledge!",
        )
        assert quiz.description == "Test your science knowledge!"

    def test_from_yaml(self) -> None:
        """Should load quiz from YAML file."""
        yaml_content = """
title: Test Quiz
description: A test quiz
questions:
  - question: What is 1+1?
    choices:
      - "1"
      - "2"
      - "3"
    correct: 1
  - question: Capital of France?
    choices:
      - London
      - Paris
      - Berlin
      - Madrid
    correct: 1
    time_limit: 20
    image: https://example.com/france.jpg
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(yaml_content)
            f.flush()
            quiz = Quiz.from_yaml(Path(f.name))

        assert quiz.title == "Test Quiz"
        assert quiz.description == "A test quiz"
        assert len(quiz.questions) == 2

        q1 = quiz.questions[0]
        assert q1.text == "What is 1+1?"
        assert q1.choices == ["1", "2", "3"]
        assert q1.correct_index == 1
        assert q1.time_limit_seconds == 30  # default

        q2 = quiz.questions[1]
        assert q2.text == "Capital of France?"
        assert q2.time_limit_seconds == 20
        assert q2.image_url == "https://example.com/france.jpg"

    def test_from_yaml_without_description(self) -> None:
        """Should handle YAML without description."""
        yaml_content = """
title: Simple Quiz
questions:
  - question: Test?
    choices: ["Yes", "No"]
    correct: 0
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(yaml_content)
            f.flush()
            quiz = Quiz.from_yaml(Path(f.name))

        assert quiz.title == "Simple Quiz"
        assert quiz.description == ""


class TestParticipant:
    """Tests for the Participant dataclass."""

    def test_participant_creation(self) -> None:
        """Should create participant with required fields."""
        p = Participant(id="abc123", display_name="Happy Cat")
        assert p.id == "abc123"
        assert p.display_name == "Happy Cat"
        assert p.score == 0
        assert p.answers == {}
        assert p.answer_times_seconds == {}

    def test_participant_with_score(self) -> None:
        """Should accept initial score."""
        p = Participant(id="test", display_name="Test", score=500)
        assert p.score == 500

    def test_participant_is_mutable(self) -> None:
        """Participant should be mutable for tracking answers."""
        p = Participant(id="test", display_name="Test")
        p.score = 100
        p.answers[0] = 2
        p.answer_times_seconds[0] = 5.5
        assert p.score == 100
        assert p.answers == {0: 2}
        assert p.answer_times_seconds == {0: 5.5}


class TestAnswer:
    """Tests for the Answer dataclass."""

    def test_answer_creation(self) -> None:
        """Should create answer with all fields."""
        a = Answer(
            participant_id="p1",
            question_index=0,
            choice_index=2,
        )
        assert a.participant_id == "p1"
        assert a.question_index == 0
        assert a.choice_index == 2

    def test_answer_is_frozen(self) -> None:
        """Answer should be immutable."""
        a = Answer(
            participant_id="p1",
            question_index=0,
            choice_index=0,
        )
        with pytest.raises(AttributeError):
            a.choice_index = 1  # type: ignore[misc]
