#!/usr/bin/env bash
# setup_ollama.sh — One-shot script to install Ollama and pull the recommended model
# Run: chmod +x setup_ollama.sh && ./setup_ollama.sh

set -e

MODEL="${OLLAMA_MODEL:-qwen2.5:7b}"
OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"

echo "========================================"
echo "  Credit Intel — Ollama Setup Script"
echo "========================================"
echo "Model   : $MODEL"
echo "Host    : $OLLAMA_HOST"
echo ""

# ── 1. Install Ollama if not present ────────────────────────────────────────
if ! command -v ollama &>/dev/null; then
    echo "[1/4] Installing Ollama..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS: brew install
        if command -v brew &>/dev/null; then
            brew install ollama
        else
            echo "  Homebrew not found. Install from: https://ollama.com/download"
            exit 1
        fi
    else
        # Linux: official install script
        curl -fsSL https://ollama.com/install.sh | sh
    fi
else
    echo "[1/4] Ollama already installed ($(ollama --version 2>/dev/null || echo 'version unknown'))"
fi

# ── 2. Start Ollama server in the background ────────────────────────────────
echo "[2/4] Starting Ollama server..."
if ! curl -s "${OLLAMA_HOST}/api/tags" &>/dev/null; then
    ollama serve &>/tmp/ollama.log &
    OLLAMA_PID=$!
    echo "  Ollama PID: $OLLAMA_PID (logs: /tmp/ollama.log)"
    sleep 3   # Wait for server to start
else
    echo "  Ollama server already running."
fi

# Verify server is up
if ! curl -s "${OLLAMA_HOST}/api/tags" &>/dev/null; then
    echo "ERROR: Ollama server did not start. Check /tmp/ollama.log"
    exit 1
fi
echo "  Server is up ✓"

# ── 3. Pull the model ────────────────────────────────────────────────────────
echo "[3/4] Pulling model: $MODEL"
echo "  This may take a few minutes on first run (downloads ~4-9 GB)..."
ollama pull "$MODEL"
echo "  Model pulled ✓"

# ── 4. Smoke test ────────────────────────────────────────────────────────────
echo "[4/4] Running smoke test..."
RESPONSE=$(curl -s "${OLLAMA_HOST}/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"$MODEL\",
    \"messages\": [{\"role\": \"user\", \"content\": \"Reply with only: {\\\"status\\\": \\\"ok\\\"}\"}],
    \"response_format\": {\"type\": \"json_object\"},
    \"stream\": false
  }" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['choices'][0]['message']['content'])" 2>/dev/null || echo "FAILED")

if echo "$RESPONSE" | grep -q "ok"; then
    echo "  JSON response test passed ✓"
else
    echo "  WARNING: Smoke test response: $RESPONSE"
    echo "  The model may still work — some models format JSON slightly differently."
fi

echo ""
echo "========================================"
echo "  Setup complete!"
echo "  Model '$MODEL' is ready."
echo ""
echo "  In your .env file set:"
echo "    LLM_PROVIDER=auto"
echo "    OLLAMA_HOST=$OLLAMA_HOST"
echo "    OLLAMA_MODEL=$MODEL"
echo "========================================"
