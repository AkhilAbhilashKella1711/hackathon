#!/bin/bash

# Ensure the script exits on errors
set -e

echo "Killing sessions if existing..."
tmux kill-session -t server 2>/dev/null || true

echo "Starting server..."
tmux new-session -d -s server
tmux send-keys -t server "source venv/bin/activate" C-m
tmux send-keys -t server "export ENVIRONMENT=development" C-m
tmux send-keys -t server "python3 main.py" C-m
tmux send-keys -t server "uvicorn server.main:app --reload --host 0.0.0.0 --port 5005" C-m
echo "Started server"

echo "All sessions started successfully!"
