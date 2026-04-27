#!/bin/bash
# Build a self-contained zipapp using shiv
set -e

cd "$(dirname "$0")/.."

echo "Building pop-quiz zipapp..."

# Build the wheel first
uv build --wheel

# Create the zipapp with shiv
uv run shiv \
    --compressed \
    --console-script pop-quiz \
    --output-file dist/pop-quiz.pyz \
    dist/*.whl

echo ""
echo "Done! Created: dist/pop-quiz.pyz"
echo ""
echo "Usage: python dist/pop-quiz.pyz quiz.yaml"
