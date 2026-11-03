# Contributing

1. Fork and create a branch from `main`.
2. Set up Python 3.12 and install dependencies:
   ```sh
   python3.12 -m venv .venv && source .venv/bin/activate
   pip install -r requirements-lock.txt
   ```
3. Make your change and run the checks the CI runs:
   ```sh
   python -m pytest -q
   python -m evaluation.run
   python -m evaluation.benchmark
   ```
4. Open a pull request describing what changed and why.

See [HOW_TO_RUN.md](HOW_TO_RUN.md) and [DESIGN.md](DESIGN.md) for more detail.
