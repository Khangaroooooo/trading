# trading — Claude-trader paper experiment

Paper-trading research repo. Knowledge base: `~/Documents/Evervault/research/finance/` (synthesis, charter, findings). Pre-flight task: `~/Documents/Evervault/tasks/finance-paper-testing-preflight.md`.

- `.env` (gitignored): Alpaca PAPER keys. Never commit, never paste in chat.
- `smoke_test.py`: read-only connectivity check (account + SPY quote).
- Rules of the road: paper only; US stocks only; risk limits hard-coded outside the LLM; every live-order path (future) requires human approval.
