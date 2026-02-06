#!/bin/bash

# Start Ollama in the background.
/bin/ollama serve &

# Record Process ID.
pid=$!

# Pause for Ollama to face startup.
sleep 5

echo "🔴 Retrieve model: ${LLM_MODEL}..."
ollama pull ${LLM_MODEL}
echo "🟢 Done!"

# Wait for Ollama process to finish.
wait $pid
