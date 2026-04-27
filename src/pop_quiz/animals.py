"""Fun animal name generator for participants."""

import random
import threading
import unicodedata
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from enum import StrEnum
from typing import Self


class AnimalEmoji(StrEnum):
    """Animal emoji characters looked up by Unicode name."""

    ANT = unicodedata.lookup("ant")
    BADGER = unicodedata.lookup("badger")
    BAT = unicodedata.lookup("bat")
    BEAR = unicodedata.lookup("bear face")
    BEAVER = unicodedata.lookup("beaver")
    BEETLE = unicodedata.lookup("beetle")
    BIRD = unicodedata.lookup("bird")
    BISON = unicodedata.lookup("bison")
    BLOWFISH = unicodedata.lookup("blowfish")
    BOAR = unicodedata.lookup("boar")
    BUFFALO = unicodedata.lookup("water buffalo")
    BUG = unicodedata.lookup("bug")
    BUTTERFLY = unicodedata.lookup("butterfly")
    CAMEL = unicodedata.lookup("bactrian camel")
    CAT = unicodedata.lookup("cat")
    CHICK = unicodedata.lookup("front-facing baby chick")
    CHICKEN = unicodedata.lookup("chicken")
    CHIPMUNK = unicodedata.lookup("chipmunk")
    COCKROACH = unicodedata.lookup("cockroach")
    CORAL = unicodedata.lookup("coral")
    COW = unicodedata.lookup("cow face")
    CRAB = unicodedata.lookup("crab")
    CRICKET = unicodedata.lookup("cricket")
    CROCODILE = unicodedata.lookup("crocodile")
    DEER = unicodedata.lookup("deer")
    DODO = unicodedata.lookup("dodo")
    DOG = unicodedata.lookup("dog")
    DOLPHIN = unicodedata.lookup("dolphin")
    DONKEY = unicodedata.lookup("donkey")
    DOVE = unicodedata.lookup("dove of peace")
    DRAGON = unicodedata.lookup("dragon face")
    DROMEDARY = unicodedata.lookup("dromedary camel")
    DUCK = unicodedata.lookup("duck")
    EAGLE = unicodedata.lookup("eagle")
    ELEPHANT = unicodedata.lookup("elephant")
    FEATHER = unicodedata.lookup("feather")
    FISH = unicodedata.lookup("fish")
    FLAMINGO = unicodedata.lookup("flamingo")
    FLY = unicodedata.lookup("fly")
    FOX = unicodedata.lookup("fox face")
    GIRAFFE = unicodedata.lookup("giraffe face")
    GOAT = unicodedata.lookup("goat")
    GOOSE = unicodedata.lookup("goose")
    GORILLA = unicodedata.lookup("gorilla")
    HAMSTER = unicodedata.lookup("hamster face")
    HEDGEHOG = unicodedata.lookup("hedgehog")
    HIPPOPOTAMUS = unicodedata.lookup("hippopotamus")
    HONEYBEE = unicodedata.lookup("honeybee")
    HORSE = unicodedata.lookup("horse face")
    JELLYFISH = unicodedata.lookup("jellyfish")
    KANGAROO = unicodedata.lookup("kangaroo")
    KOALA = unicodedata.lookup("koala")
    LADY_BEETLE = unicodedata.lookup("lady beetle")
    LEOPARD = unicodedata.lookup("leopard")
    LION = unicodedata.lookup("lion face")
    LIZARD = unicodedata.lookup("lizard")
    LLAMA = unicodedata.lookup("llama")
    LOBSTER = unicodedata.lookup("lobster")
    MAMMOTH = unicodedata.lookup("mammoth")
    MICROBE = unicodedata.lookup("microbe")
    MONKEY = unicodedata.lookup("monkey")
    MOOSE = unicodedata.lookup("moose")
    MOSQUITO = unicodedata.lookup("mosquito")
    MOUSE = unicodedata.lookup("mouse face")
    OCTOPUS = unicodedata.lookup("octopus")
    ORANGUTAN = unicodedata.lookup("orangutan")
    OTTER = unicodedata.lookup("otter")
    OWL = unicodedata.lookup("owl")
    OX = unicodedata.lookup("ox")
    OYSTER = unicodedata.lookup("oyster")
    PANDA = unicodedata.lookup("panda face")
    PARROT = unicodedata.lookup("parrot")
    PEACOCK = unicodedata.lookup("peacock")
    PENGUIN = unicodedata.lookup("penguin")
    PIG = unicodedata.lookup("pig face")
    POODLE = unicodedata.lookup("poodle")
    RABBIT = unicodedata.lookup("rabbit face")
    RACCOON = unicodedata.lookup("raccoon")
    RAM = unicodedata.lookup("ram")
    RAT = unicodedata.lookup("rat")
    RHINOCEROS = unicodedata.lookup("rhinoceros")
    ROOSTER = unicodedata.lookup("rooster")
    SAUROPOD = unicodedata.lookup("sauropod")
    SCORPION = unicodedata.lookup("scorpion")
    SEAL = unicodedata.lookup("seal")
    SHARK = unicodedata.lookup("shark")
    SHEEP = unicodedata.lookup("sheep")
    SHRIMP = unicodedata.lookup("shrimp")
    SKUNK = unicodedata.lookup("skunk")
    SLOTH = unicodedata.lookup("sloth")
    SNAIL = unicodedata.lookup("snail")
    SNAKE = unicodedata.lookup("snake")
    SPIDER = unicodedata.lookup("spider")
    SPIRAL_SHELL = unicodedata.lookup("spiral shell")
    SPOUTING_WHALE = unicodedata.lookup("spouting whale")
    SQUID = unicodedata.lookup("squid")
    SWAN = unicodedata.lookup("swan")
    T_REX = unicodedata.lookup("t-rex")
    TIGER = unicodedata.lookup("tiger face")
    TROPICAL_FISH = unicodedata.lookup("tropical fish")
    TURKEY = unicodedata.lookup("turkey")
    TURTLE = unicodedata.lookup("turtle")
    UNICORN = unicodedata.lookup("unicorn face")
    WHALE = unicodedata.lookup("whale")
    WING = unicodedata.lookup("wing")
    WOLF = unicodedata.lookup("wolf face")
    WORM = unicodedata.lookup("worm")
    ZEBRA = unicodedata.lookup("zebra face")

    @property
    def pretty_name(self) -> str:
        """Return human-readable name with spaces instead of underscores."""
        return self.name.replace("_", " ")


@dataclass(slots=True, frozen=True)
class Animal:
    """An animal with emoji and display name."""

    emoji: AnimalEmoji
    name: str

    def __str__(self) -> str:
        return f"{self.emoji} {self.name}"

    @classmethod
    def random(cls) -> Self:
        """Get a random unique animal from the pool (thread-safe)."""
        with _animal_generator_lock:
            return next(_animal_generator)


def _create_animal_generator(adjectives: Iterable[str]) -> Iterator[Animal]:
    """Generate shuffled animals, cycling infinitely through combinations."""
    while True:
        animals = [
            Animal(emoji, f"{adj} {emoji.pretty_name}".title())
            for adj in adjectives
            for emoji in AnimalEmoji
        ]
        random.shuffle(animals)
        yield from animals


_ADJECTIVES = [
    "amazing",
    "ambitious",
    "bamboozled",
    "bouncy",
    "brave",
    "bright",
    "bubbly",
    "calm",
    "cheeky",
    "cheerful",
    "chunky",
    "clumsy",
    "confused",
    "cool",
    "creative",
    "cuddly",
    "dancing",
    "daring",
    "dizzy",
    "dynamic",
    "eager",
    "energetic",
    "enthusiastic",
    "exciting",
    "fancy",
    "fearless",
    "fidgety",
    "fluffy",
    "friendly",
    "funny",
    "gentle",
    "giggling",
    "goofy",
    "grumpy",
    "happy",
    "harmonious",
    "hiccuping",
    "hungry",
    "innovative",
    "inspiring",
    "intrepid",
    "jazzy",
    "jiggly",
    "jolly",
    "joyful",
    "jubilant",
    "jumping",
    "keen",
    "lazy",
    "lively",
    "lucky",
    "mighty",
    "noble",
    "noisy",
    "outgoing",
    "passionate",
    "prickly",
    "quirky",
    "radiant",
    "silly",
    "sleepy",
    "sneezy",
    "sparkly",
    "speedy",
    "spiky",
    "spirited",
    "squishy",
    "tranquil",
    "unstoppable",
    "vibrant",
    "wiggly",
    "wise",
    "wobbly",
    "zany",
    "zealous",
]

_animal_generator = _create_animal_generator(_ADJECTIVES)
_animal_generator_lock = threading.Lock()
