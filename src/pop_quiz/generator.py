import asyncio
import base64
import io
import random
import time
from pathlib import Path

import httpx
import yaml
from openai import AsyncOpenAI
from PIL import Image
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)

from pop_quiz.models import Quiz

console = Console()


async def process_image(client: AsyncOpenAI, prompt: str) -> str | None:
    """Download, resize, and base64 encode an image from a prompt."""
    try:
        response = await client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )
        url = response.data[0].url

        async with httpx.AsyncClient() as http_client:
            response = await http_client.get(url, timeout=30.0)
            response.raise_for_status()
            content = response.content

        # Run CPU-bound image processing in a thread
        def _process():
            img = Image.open(io.BytesIO(content))
            img.thumbnail((400, 300))
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=70, optimize=True)
            return base64.b64encode(buffer.getvalue()).decode("utf-8")

        b64_data = await asyncio.to_thread(_process)
        return f"data:image/jpeg;base64,{b64_data}"

    except Exception as e:
        console.print(
            f"[red]Failed to process image for prompt '{prompt}': {e}[/red]"
        )
        return None


async def generate_quiz_async(
    api_key: str,
    no_images: bool = False,
    difficulty: str = "medium",
    num_questions: int = 10,
    theme: str | None = None,
    language: str = "English",
) -> tuple[Quiz, Path]:
    """Generate a random quiz using OpenAI and save it to a file."""
    client = AsyncOpenAI(api_key=api_key)

    theme_instruction = (
        f"The quiz should be about: {theme}."
        if theme
        else "The quiz should have a random theme."
    )
    language_instruction = (
        "Write all user-facing text (title, description, questions, choices) "
        f"in {language}. Keep YAML keys in English."
    )

    prompt = f"""
    Generate a fun and cohesive pop quiz in YAML format.
    Difficulty level: {difficulty}.
    If difficulty is 'progressive', start with easy questions and make them progressively harder.
    The YAML should have the following structure:
    title: <string>
    slug: <string, 1-3 words, lowercase, hyphen-separated, for filename>
    description: <string>
    questions:
      - question: <string>
        choices: [<string>, <string>, ...]
        correct: <int index of correct answer>
        time_limit: <int seconds, default 30>
        image_prompt: <string>

    {theme_instruction}
    {language_instruction}
    Include {num_questions} questions.
    Each question should have 2-4 choices.
    
    CRITICAL INSTRUCTIONS:
    1. Ensure all questions and answers are FACTUALLY CORRECT. Double check your facts.
    2. For 'image_prompt', provide a short visual description of the subject matter.
       - Hard difficulty: Do NOT include image prompts.
       - Medium difficulty: Include image prompts sparingly.
       - Easy difficulty: Include image prompts for all questions.
       - Progressive difficulty: Include image prompts for the first half of questions only.
    3. IMPORTANT: The 'image_prompt' MUST NOT contain the answer text or any text that reveals the solution.
    4. The image should be RELEVANT to the question's theme but ABSTRACT enough not to reveal the answer.
       - It should set the mood or provide a subtle hint.
       - It must NOT be random or unrelated.
       - It must NOT directly depict the answer.
       - Bad: "A picture of the Eiffel Tower" (for a question about Paris landmarks - too revealing)
       - Bad: "A random abstract pattern" (too unrelated)
       - Good: "An artistic impression of a romantic European city at sunset, impressionist style" (sets mood, relevant, not revealing)
    5. Do not include markdown formatting like ```yaml.
    """

    console.print("[bold green]Generating quiz with OpenAI...[/bold green]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        progress.add_task(description="Generating quiz content...", total=None)
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are a creative quiz generator.",
                },
                {"role": "user", "content": prompt},
            ],
        )

    content = response.choices[0].message.content
    if not content:
        raise ValueError("No content received from OpenAI")

    # Strip markdown code blocks if present
    if content.startswith("```yaml"):
        content = content[7:]
    elif content.startswith("```"):
        content = content[3:]

    if content.endswith("```"):
        content = content[:-3]

    content = content.strip()

    # Validate YAML
    try:
        data = yaml.safe_load(content)
        # Basic validation
        if "title" not in data or "questions" not in data:
            raise ValueError("Missing title or questions")

        # Prepare image generation list
        images_to_process = []
        for i, q in enumerate(data["questions"]):
            img_prompt = q.pop("image_prompt", None)

            if no_images:
                continue

            if difficulty == "hard":
                continue

            if difficulty == "medium" and random.random() > 0.33:
                continue

            if difficulty == "progressive" and i >= len(data["questions"]) / 2:
                continue

            if not img_prompt:
                # Fallback to title if no prompt provided
                img_prompt = data.get("title", "Quiz") + " abstract"

            images_to_process.append((q, img_prompt))

        # Process images
        if images_to_process:
            console.print(
                f"[bold blue]Prefetching and embedding {len(images_to_process)} images...[/bold blue]"
            )

            async def _process_item(q, prompt, task_id, progress):
                image_data = await process_image(client, prompt)
                if image_data:
                    q["image"] = image_data
                else:
                    q.pop("image", None)
                progress.advance(task_id)

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
            ) as progress:
                task_id = progress.add_task(
                    "[cyan]Processing images...", total=len(images_to_process)
                )

                tasks = []
                for q, prompt in images_to_process:
                    tasks.append(_process_item(q, prompt, task_id, progress))

                await asyncio.gather(*tasks)

        # Re-serialize to ensure fixes are saved
        content = yaml.dump(data, sort_keys=False)

    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML received: {e}")

    # Save to file
    output_dir = Path("generated")
    output_dir.mkdir(exist_ok=True)

    slug = data.get("slug", "quiz")
    # Sanitize slug just in case
    slug = "".join(c for c in slug if c.isalnum() or c in "-_").strip()
    if not slug:
        slug = f"quiz_{int(time.time())}"

    filename = f"{slug}.yaml"
    path = output_dir / filename
    path = path.resolve()
    path.write_text(content)

    console.print(f"[bold green]Quiz saved to {path}[/bold green]")

    return Quiz.from_yaml(path), path


def generate_quiz(
    api_key: str,
    no_images: bool = False,
    difficulty: str = "medium",
    num_questions: int = 10,
    theme: str | None = None,
    language: str = "English",
) -> tuple[Quiz, Path]:
    return asyncio.run(
        generate_quiz_async(
            api_key,
            no_images,
            difficulty,
            num_questions,
            theme,
            language,
        )
    )
