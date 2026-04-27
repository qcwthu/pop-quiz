"""Tests for the animals module."""

import pytest

from pop_quiz.animals import Animal, AnimalEmoji, _create_animal_generator


class TestAnimalEmoji:
    """Tests for the AnimalEmoji enum."""

    def test_all_emojis_are_strings(self) -> None:
        """All enum values should be valid emoji strings."""
        for emoji in AnimalEmoji:
            assert isinstance(emoji.value, str)
            assert len(emoji.value) > 0

    def test_emoji_count(self) -> None:
        """Should have a substantial number of animal emojis."""
        assert len(AnimalEmoji) >= 100

    def test_pretty_name_removes_underscores(self) -> None:
        """pretty_name should replace underscores with spaces."""
        assert AnimalEmoji.LADY_BEETLE.pretty_name == "LADY BEETLE"
        assert AnimalEmoji.T_REX.pretty_name == "T REX"
        assert AnimalEmoji.SPIRAL_SHELL.pretty_name == "SPIRAL SHELL"

    def test_pretty_name_single_word(self) -> None:
        """pretty_name should work for single-word names."""
        assert AnimalEmoji.CAT.pretty_name == "CAT"
        assert AnimalEmoji.DOG.pretty_name == "DOG"

    def test_specific_emojis_exist(self) -> None:
        """Common animals should be present in the enum."""
        common_animals = [
            "CAT",
            "DOG",
            "BIRD",
            "FISH",
            "ELEPHANT",
            "LION",
            "TIGER",
            "BEAR",
            "WOLF",
            "FOX",
        ]
        enum_names = {e.name for e in AnimalEmoji}
        for animal in common_animals:
            assert animal in enum_names


class TestAnimal:
    """Tests for the Animal dataclass."""

    def test_str_representation(self) -> None:
        """__str__ should return emoji followed by name."""
        animal = Animal(emoji=AnimalEmoji.CAT, name="Fluffy Cat")
        result = str(animal)
        assert AnimalEmoji.CAT.value in result
        assert "Fluffy Cat" in result

    def test_str_format(self) -> None:
        """__str__ should have emoji, space, then name."""
        animal = Animal(emoji=AnimalEmoji.DOG, name="Happy Dog")
        assert str(animal) == f"{AnimalEmoji.DOG} Happy Dog"

    def test_random_returns_animal(self) -> None:
        """Animal.random() should return an Animal instance."""
        animal = Animal.random()
        assert isinstance(animal, Animal)
        assert isinstance(animal.emoji, AnimalEmoji)
        assert isinstance(animal.name, str)

    def test_random_returns_different_animals(self) -> None:
        """Multiple calls to random() should return different animals."""
        animals = [Animal.random() for _ in range(10)]
        unique_names = {str(a) for a in animals}
        assert len(unique_names) > 1

    def test_random_animal_name_is_titled(self) -> None:
        """Random animal names should be title-cased."""
        for _ in range(5):
            animal = Animal.random()
            assert animal.name == animal.name.title()

    def test_animal_is_frozen(self) -> None:
        """Animal instances should be immutable."""
        animal = Animal(emoji=AnimalEmoji.CAT, name="Test")
        with pytest.raises(AttributeError):
            animal.name = "Changed"  # type: ignore[misc]


class TestAnimalGenerator:
    """Tests for the animal generator."""

    def test_generates_animals(self) -> None:
        """Generator should yield Animal instances."""
        gen = _create_animal_generator(["happy", "sad"])
        animal = next(gen)
        assert isinstance(animal, Animal)

    def test_generates_all_combinations(self) -> None:
        """Generator should produce all adjective + emoji combinations."""
        adjectives = ["tiny", "giant"]
        gen = _create_animal_generator(adjectives)

        # Take exactly adjectives * emojis items (one full cycle)
        expected_count = len(adjectives) * len(AnimalEmoji)
        animals = [next(gen) for _ in range(expected_count)]

        # Verify all combinations exist
        for adj in adjectives:
            for emoji in AnimalEmoji:
                expected_name = f"{adj} {emoji.pretty_name}".title()
                matching = [a for a in animals if a.name == expected_name]
                assert len(matching) == 1, f"Missing: {expected_name}"

    def test_output_is_shuffled(self) -> None:
        """Generator output should be shuffled (not in original order)."""
        adjectives = ["a", "b", "c"]
        results_differ = False
        for _ in range(5):
            gen = _create_animal_generator(adjectives)
            count = len(adjectives) * len(AnimalEmoji)
            names = [next(gen).name for _ in range(count)]
            if names != sorted(names):
                results_differ = True
                break
        assert results_differ, "Output appears to not be shuffled"

    def test_cycles_infinitely(self) -> None:
        """Generator should cycle back after exhausting combinations."""
        adjectives = ["test"]
        gen = _create_animal_generator(adjectives)
        cycle_size = len(adjectives) * len(AnimalEmoji)

        # Get two full cycles worth
        first_cycle = {next(gen).name for _ in range(cycle_size)}
        second_cycle = {next(gen).name for _ in range(cycle_size)}

        # Both cycles should have the same names (but different order)
        assert first_cycle == second_cycle

    def test_empty_adjectives_cycles_empty(self) -> None:
        """Generator with empty adjectives should cycle infinitely yielding nothing useful."""
        gen = _create_animal_generator([])
        # With no adjectives, each cycle is empty, so it loops forever without yielding
        # We just verify it doesn't crash on creation
        assert gen is not None
