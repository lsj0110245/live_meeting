#!/bin/bash
set -e

# Model directory (Docker volume mount point)
MODEL_DIR="./ai_models"
mkdir -p "$MODEL_DIR"

echo "Downloading AI models to $MODEL_DIR..."

# 1. Download Whisper Model (small)
# Note: The whisper service often downloads on first run, but pre-downloading is safer for air-gapped envs.
echo "Checking Whisper model..."
# Actual download logic depends on the specific docker image's cache structure.
# For now, we create a placeholder to ensure volume permissions are correct.
mkdir -p "$MODEL_DIR/whisper"

# 2. Download LLM Model (Llama 3 - GGUF format for CPU/GPU efficiency)
# Using HuggingFace Hub CLI tool if available, or curl
echo "Downloading Llama 3 (Quantized)..."
mkdir -p "$MODEL_DIR/llm"

# Example: Download Mistral-7B-Instruct-v0.2.Q4_K_M.gguf (placeholder URL)
# curl -L -o "$MODEL_DIR/llm/model.gguf" "https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf"

echo "Download script placeholder created. Real download commands should be uncommented based on model selection."
