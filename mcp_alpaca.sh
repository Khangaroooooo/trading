#!/bin/zsh
# Launch the official Alpaca MCP server (paper mode), reading keys from .env at runtime.
set -a
source /Users/kkhangaroo/trading/.env
set +a
export ALPACA_API_KEY="$ALPACA_PAPER_KEY"
export ALPACA_SECRET_KEY="$ALPACA_PAPER_SECRET"
export ALPACA_PAPER_TRADE=true
exec /Users/kkhangaroo/.local/bin/uvx alpaca-mcp-server
