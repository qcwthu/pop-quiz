"""Command-line interface for the quiz application."""

import argparse
import os
import sys
import webbrowser
from pathlib import Path
from typing import NoReturn

import questionary
import uvicorn
from rich.console import Console

from pop_quiz import server
from pop_quiz.generator import generate_quiz
from pop_quiz.models import Quiz
from pop_quiz.state import GameState

console = Console()


def interactive_mode() -> argparse.Namespace:
    """Run interactive mode to gather all parameters."""
    console.print("\n[bold cyan]Pop Quiz Interactive Setup[/bold cyan]\n")

    # Ask whether to load or generate
    quiz_source = questionary.select(
        "Quiz source:",
        choices=["Generate new quiz", "Load existing quiz file"],
        default="Generate new quiz",
    ).ask()

    quiz_file = None
    difficulty = "medium"
    num_questions = 10
    theme = None
    language = "English"
    no_images = False

    if quiz_source == "Load existing quiz file":
        quiz_file_str = questionary.text("Quiz file path:", default="").ask()
        if quiz_file_str:
            quiz_file = Path(quiz_file_str)
    else:  # Generate new quiz
        console.print("\n[bold cyan]Quiz Generation Options[/bold cyan]\n")

        # Difficulty
        difficulty = questionary.select(
            "Difficulty level:",
            choices=["easy", "medium", "hard", "progressive"],
            default="medium",
        ).ask()

        # Number of questions
        num_questions_str = questionary.text(
            "Number of questions:", default="10"
        ).ask()
        num_questions = int(num_questions_str)

        # Theme
        theme = questionary.text(
            "Theme (leave empty for random):", default=""
        ).ask()
        if not theme:
            theme = None

        # Language
        language = questionary.text("Language:", default="English").ask()

        # Images
        no_images = questionary.confirm(
            "Disable image generation?", default=False
        ).ask()

    console.print()

    # Use default server settings
    port = 8000
    host = "0.0.0.0"
    no_browser = False

    # Create namespace object compatible with argparse
    return argparse.Namespace(
        quiz_file=quiz_file,
        difficulty=difficulty,
        num_questions=num_questions,
        theme=theme,
        language=language,
        no_images=no_images,
        port=port,
        host=host,
        no_browser=no_browser,
    )


def main() -> None:
    """Main entry point for the pop-quiz CLI."""
    # Check if running in interactive mode (no arguments provided)
    if len(sys.argv) == 1:
        args = interactive_mode()
    else:
        args = parse_args()

    if args.quiz_file:
        if not args.quiz_file.exists():
            die(f"Quiz file not found: {args.quiz_file}")

        try:
            quiz = Quiz.from_yaml(args.quiz_file)
        except Exception as e:
            die(f"Error loading quiz: {e}")
    else:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            die("No quiz file provided and OPENAI_API_KEY not set.")

        try:
            quiz, _ = generate_quiz(
                api_key,
                no_images=args.no_images,
                difficulty=args.difficulty,
                num_questions=args.num_questions,
                theme=args.theme,
                language=args.language,
            )
        except Exception as e:
            die(f"Error generating quiz: {e}")

    print(f"Loaded quiz: {quiz.title}")
    print(f"Questions: {len(quiz.questions)}")

    game = GameState.create(quiz)
    # Inject game state into the app
    server.app.state.game = game

    url = f"http://localhost:{args.port}"
    print(f"\nPIN: {game.pin}")
    print(f"Starting server on {url}")

    if not args.no_browser:
        webbrowser.open(url)

    uvicorn.run(server.app, host=args.host, port=args.port, log_level="info")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="pop-quiz",
        description="Host a pop quiz from a YAML file",
    )
    parser.add_argument(
        "quiz_file",
        type=Path,
        nargs="?",
        help="Path to the quiz YAML file",
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=8000,
        help="Port to run the server on (default: 8000)",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind the server to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Don't open the browser automatically",
    )
    parser.add_argument(
        "--no-images",
        action="store_true",
        help="Disable image generation",
    )
    parser.add_argument(
        "--difficulty",
        choices=["easy", "medium", "hard", "progressive"],
        default="medium",
        help="Difficulty level of the quiz (default: medium)",
    )
    parser.add_argument(
        "--num-questions",
        "-n",
        type=int,
        default=10,
        help="Number of questions to generate (default: 10)",
    )
    parser.add_argument(
        "--theme",
        "-t",
        type=str,
        help="Theme for the quiz (e.g., 'space', 'history', 'science'). If not specified, a random theme will be chosen.",
    )
    parser.add_argument(
        "--language",
        "-l",
        default="English",
        help="Language for generated quiz content (default: English).",
    )
    return parser.parse_args()


def die(message: str, code: int = 1) -> NoReturn:
    """Print error message and exit."""
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(code)


if __name__ == "__main__":
    main()
