"""Tests for the state module."""

from pop_quiz.models import Answer, Question, Quiz, QuizPhase
from pop_quiz.state import GameState


def make_quiz(num_questions: int = 2, time_limit: int = 30) -> Quiz:
    """Create a simple quiz for testing."""
    questions = [
        Question(
            text=f"Question {i + 1}?",
            choices=["A", "B", "C", "D"],
            correct_index=i % 4,
            time_limit_seconds=time_limit,
        )
        for i in range(num_questions)
    ]
    return Quiz(title="Test Quiz", questions=questions)


class TestGameStateCreate:
    """Tests for GameState creation."""

    def test_create_generates_pin(self) -> None:
        """GameState.create should generate a 6-digit PIN."""
        state = GameState.create(make_quiz())
        assert len(state.pin) == 6
        assert state.pin.isdigit()

    def test_create_starts_in_lobby(self) -> None:
        """New game should start in lobby phase."""
        state = GameState.create(make_quiz())
        assert state.phase == QuizPhase.LOBBY

    def test_create_shuffles_indices(self) -> None:
        """Create should generate shuffled indices for all questions."""
        quiz = make_quiz(num_questions=3)
        state = GameState.create(quiz)
        assert len(state.shuffled_indices) == 3
        for i in range(3):
            assert i in state.shuffled_indices
            assert sorted(state.shuffled_indices[i]) == [0, 1, 2, 3]

    def test_create_no_participants(self) -> None:
        """New game should have no participants."""
        state = GameState.create(make_quiz())
        assert len(state.participants) == 0


class TestShuffling:
    """Tests for question shuffling."""

    def test_get_shuffled_question_returns_all_choices(self) -> None:
        """Shuffled question should contain all original choices."""
        state = GameState.create(make_quiz())
        choices, _ = state.get_shuffled_question(0)
        assert sorted(choices) == ["A", "B", "C", "D"]

    def test_shuffled_correct_index_points_to_correct_answer(self) -> None:
        """Shuffled correct index should point to the correct answer."""
        quiz = Quiz(
            title="Test",
            questions=[
                Question(
                    text="Q",
                    choices=["Wrong1", "Wrong2", "Correct", "Wrong3"],
                    correct_index=2,
                )
            ],
        )
        state = GameState.create(quiz)
        choices, correct_idx = state.get_shuffled_question(0)
        assert choices[correct_idx] == "Correct"


class TestParticipants:
    """Tests for participant management."""

    def test_add_participant_in_lobby(self) -> None:
        """Should add participant in lobby phase."""
        state = GameState.create(make_quiz())
        participant = state.add_participant()
        assert participant is not None
        assert participant.id in state.participants
        assert participant.display_name  # Should have a name

    def test_add_participant_generates_server_id(self) -> None:
        """Should generate server-side UUID for new participants."""
        state = GameState.create(make_quiz())
        # Even with a stored_id, new participants get server-generated IDs
        participant = state.add_participant("custom-id")
        assert participant is not None
        # ID should be a UUID, not the provided string
        assert participant.id != "custom-id"
        assert len(participant.id) == 36  # UUID format

    def test_add_participant_reconnect(self) -> None:
        """Should return existing participant on reconnect."""
        state = GameState.create(make_quiz())
        p1 = state.add_participant()
        p2 = state.add_participant(p1.id)  # Use the server-generated ID
        assert p1 is p2
        assert len(state.participants) == 1

    def test_add_participant_after_start_fails(self) -> None:
        """Should not add new participants after quiz starts."""
        state = GameState.create(make_quiz())
        state.add_participant()
        state.start_quiz()
        new_participant = state.add_participant()
        assert new_participant is None
        assert len(state.participants) == 1

    def test_reconnect_after_start_works(self) -> None:
        """Should allow reconnection after quiz starts."""
        state = GameState.create(make_quiz())
        p1 = state.add_participant()
        state.start_quiz()
        p2 = state.add_participant(p1.id)  # Use server-generated ID
        assert p2 is p1

    def test_remove_participant_in_lobby(self) -> None:
        """Should remove participant in lobby phase."""
        state = GameState.create(make_quiz())
        p = state.add_participant()
        assert state.remove_participant(p.id) is True
        assert p.id not in state.participants

    def test_remove_participant_not_in_lobby(self) -> None:
        """Should not remove participant after quiz starts."""
        state = GameState.create(make_quiz())
        p = state.add_participant()
        state.start_quiz()
        assert state.remove_participant(p.id) is False
        assert p.id in state.participants

    def test_remove_nonexistent_participant(self) -> None:
        """Should return False when removing nonexistent participant."""
        state = GameState.create(make_quiz())
        assert state.remove_participant("does-not-exist") is False


class TestQuizFlow:
    """Tests for quiz flow management."""

    def test_start_quiz_success(self) -> None:
        """Should start quiz with participants."""
        state = GameState.create(make_quiz())
        state.add_participant()
        assert state.start_quiz() is True
        assert state.phase == QuizPhase.COUNTDOWN

    def test_start_quiz_no_participants(self) -> None:
        """Should not start quiz without participants."""
        state = GameState.create(make_quiz())
        assert state.start_quiz() is False
        assert state.phase == QuizPhase.LOBBY

    def test_start_quiz_twice(self) -> None:
        """Should not start quiz twice."""
        state = GameState.create(make_quiz())
        state.add_participant()
        state.start_quiz()
        assert state.start_quiz() is False

    def test_start_question(self) -> None:
        """start_question should transition to question phase."""
        state = GameState.create(make_quiz())
        p = state.add_participant()
        state.start_quiz()
        state.start_question()
        assert state.phase == QuizPhase.QUESTION
        assert state.question_start_time > 0
        assert p.id in state.scores_at_question_start

    def test_reveal_answer(self) -> None:
        """reveal_answer should transition to reveal phase."""
        state = GameState.create(make_quiz())
        state.add_participant()
        state.start_quiz()
        state.start_question()
        state.reveal_answer()
        assert state.phase == QuizPhase.REVEAL

    def test_next_question_advances(self) -> None:
        """next_question should advance to next question."""
        state = GameState.create(make_quiz(num_questions=3))
        state.add_participant()
        state.start_quiz()
        state.start_question()
        state.reveal_answer()

        assert state.current_question == 0
        assert state.next_question() is True
        assert state.current_question == 1
        assert state.phase == QuizPhase.COUNTDOWN

    def test_next_question_finishes_quiz(self) -> None:
        """next_question should finish quiz after last question."""
        state = GameState.create(make_quiz(num_questions=1))
        state.add_participant()
        state.start_quiz()
        state.start_question()
        state.reveal_answer()

        assert state.next_question() is False
        assert state.phase == QuizPhase.FINISHED


class TestAnswerSubmission:
    """Tests for answer submission."""

    def _setup_question_state(self) -> tuple[GameState, str]:
        """Set up a state ready for answering. Returns (state, participant_id)."""
        state = GameState.create(make_quiz())
        p = state.add_participant()
        state.start_quiz()
        state.start_question()
        return state, p.id

    def test_submit_correct_answer(self) -> None:
        """Should accept correct answer and award points."""
        state, pid = self._setup_question_state()
        _, correct_idx = state.get_shuffled_question(0)

        answer = Answer(
            participant_id=pid,
            question_index=0,
            choice_index=correct_idx,
        )
        assert state.submit_answer(answer) is True
        assert state.participants[pid].score > 0

    def test_submit_wrong_answer(self) -> None:
        """Should accept wrong answer but not award points."""
        state, pid = self._setup_question_state()
        _, correct_idx = state.get_shuffled_question(0)
        wrong_idx = (correct_idx + 1) % 4

        answer = Answer(
            participant_id=pid,
            question_index=0,
            choice_index=wrong_idx,
        )
        assert state.submit_answer(answer) is True
        assert state.participants[pid].score == 0

    def test_submit_answer_wrong_phase(self) -> None:
        """Should reject answer in wrong phase."""
        state = GameState.create(make_quiz())
        p = state.add_participant()
        state.start_quiz()
        # Still in COUNTDOWN, not QUESTION

        answer = Answer(
            participant_id=p.id,
            question_index=0,
            choice_index=0,
        )
        assert state.submit_answer(answer) is False

    def test_submit_answer_wrong_question(self) -> None:
        """Should reject answer for wrong question index."""
        state, pid = self._setup_question_state()

        answer = Answer(
            participant_id=pid,
            question_index=1,  # Wrong question
            choice_index=0,
        )
        assert state.submit_answer(answer) is False

    def test_submit_answer_unknown_participant(self) -> None:
        """Should reject answer from unknown participant."""
        state, _ = self._setup_question_state()

        answer = Answer(
            participant_id="unknown",
            question_index=0,
            choice_index=0,
        )
        assert state.submit_answer(answer) is False

    def test_submit_answer_twice(self) -> None:
        """Should reject duplicate answer."""
        state, pid = self._setup_question_state()

        answer = Answer(
            participant_id=pid,
            question_index=0,
            choice_index=0,
        )
        assert state.submit_answer(answer) is True
        assert state.submit_answer(answer) is False

    def test_submit_answer_invalid_choice_index(self) -> None:
        """Should reject answer with invalid choice index."""
        state, pid = self._setup_question_state()

        answer = Answer(
            participant_id=pid,
            question_index=0,
            choice_index=99,  # Out of bounds
        )
        assert state.submit_answer(answer) is False


class TestLeaderboard:
    """Tests for leaderboard functionality."""

    def test_leaderboard_sorted_by_score(self) -> None:
        """Leaderboard should be sorted by score descending."""
        state = GameState.create(make_quiz())
        p1 = state.add_participant()
        p2 = state.add_participant()
        p3 = state.add_participant()

        p1.score = 100
        p2.score = 300
        p3.score = 200

        leaderboard = state.leaderboard
        assert leaderboard[0].id == p2.id
        assert leaderboard[1].id == p3.id
        assert leaderboard[2].id == p1.id

    def test_answers_count(self) -> None:
        """answers_count should track answered participants."""
        state = GameState.create(make_quiz())
        p1 = state.add_participant()
        state.add_participant()
        state.start_quiz()
        state.start_question()

        assert state.answers_count == 0

        state.submit_answer(
            Answer(
                participant_id=p1.id,
                question_index=0,
                choice_index=0,
            )
        )
        assert state.answers_count == 1


class TestStateViews:
    """Tests for state view generation."""

    def test_get_current_question(self) -> None:
        """Should return current question."""
        state = GameState.create(make_quiz(num_questions=2))
        assert state.get_current_question() == state.quiz.questions[0]

        state.current_question = 1
        assert state.get_current_question() == state.quiz.questions[1]

    def test_get_current_question_out_of_range(self) -> None:
        """Should return None when out of range."""
        state = GameState.create(make_quiz(num_questions=1))
        state.current_question = 5
        assert state.get_current_question() is None

    def test_host_state_contains_required_fields(self) -> None:
        """Host state should contain all required fields."""
        state = GameState.create(make_quiz())
        state.add_participant()
        host_state = state.get_state_for_host()

        assert "phase" in host_state
        assert "quiz_title" in host_state
        assert "current_question_index" in host_state
        assert "total_questions" in host_state
        assert "participants" in host_state
        assert "answers_count" in host_state

    def test_participant_state_contains_required_fields(self) -> None:
        """Participant state should contain all required fields."""
        state = GameState.create(make_quiz())
        p = state.add_participant()
        p_state = state.get_state_for_participant(p.id)

        assert "phase" in p_state
        assert "quiz_title" in p_state
        assert "display_name" in p_state
        assert "score" in p_state

    def test_participant_score_hidden_during_question(self) -> None:
        """Participant score should use saved score during question phase."""
        state = GameState.create(make_quiz())
        p = state.add_participant()
        state.start_quiz()
        state.start_question()

        # Submit correct answer
        _, correct_idx = state.get_shuffled_question(0)
        state.submit_answer(
            Answer(
                participant_id=p.id,
                question_index=0,
                choice_index=correct_idx,
            )
        )

        # Score should still show 0 (saved at question start)
        p_state = state.get_state_for_participant(p.id)
        assert p_state["score"] == 0

        # After reveal, score should update
        state.reveal_answer()
        p_state = state.get_state_for_participant(p.id)
        assert p_state["score"] > 0

    def test_host_state_points_gained_in_reveal(self) -> None:
        """Host should see points_gained during reveal phase."""
        state = GameState.create(make_quiz())
        p = state.add_participant()
        state.start_quiz()
        state.start_question()

        _, correct_idx = state.get_shuffled_question(0)
        state.submit_answer(
            Answer(
                participant_id=p.id,
                question_index=0,
                choice_index=correct_idx,
            )
        )

        state.reveal_answer()
        host_state = state.get_state_for_host()
        participant_data = host_state["participants"][0]
        assert "points_gained" in participant_data
        assert participant_data["points_gained"] > 0
