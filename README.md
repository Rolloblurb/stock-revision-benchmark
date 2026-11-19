# Stock Revision Benchmark

A simulated command-line task for practicing AI-agent evaluation and test
design. The task asks an agent to reconcile stock when events can be corrected,
voided, recorded late, or expressed in different time zones.

**Provenance:** This is an original personal-practice project created with AI
assistance. The incident and records are synthetic. It is not a claim of a
production incident, industry experience, or acceptance by an evaluation
platform. Review the implementation, run the tests, and describe your own
contribution accurately before presenting it.

## What this demonstrates

- A written, verifiable CLI contract with explicit error behavior.
- Separate starter code, reference solution, example data, and black-box tests.
- Revision precedence, duplicate ties, voids, late records, UTC conversion,
  output integrity, and seeded unseen inputs.
- A container recipe and a CI configuration. The tests themselves require only
  the Python standard library; they can also be collected by pytest.

| Path | Purpose |
| --- | --- |
| `task/instruction.md` | Complete task contract and candidate instructions |
| `starter/reconcile.py` | Intentionally incomplete starting point |
| `reference/reconcile.py` | Working reference implementation |
| `solution/solve.sh` | Copies the reference into the starter (POSIX shell) |
| `tests/test_reconciliation.py` | Independent CLI-level test suite |
| `examples/` | Small CSV example and its expected result |
| `Dockerfile` | Python container for running the tests |
| `.github/workflows/tests.yml` | Optional GitHub Actions test workflow |

## Run the reference and tests

Requires Python 3.10 or newer. In Windows CMD, from this folder:

```bat
python reference\reconcile.py --inventory examples\inventory.csv --revisions examples\revisions.csv --as-of 2026-01-01T12:00:00Z --output stock-report.csv
type stock-report.csv
python -m unittest discover -s tests -v
```

On Linux or macOS, use `/` instead of `\` in paths, and `cat stock-report.csv`
instead of `type`. The example output is also in `examples/expected.csv`.

Optional pytest runner:

```text
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

By default the tests target the reference. To assess a candidate in Windows
CMD, run:

```bat
set "STOCK_TASK_CANDIDATE=%CD%\starter\reconcile.py"
python -m unittest discover -s tests -v
set "STOCK_TASK_CANDIDATE="
```

The starter intentionally fails until implemented. On Linux/macOS, see the
candidate command in `task/instruction.md` or run `sh solution/solve.sh` to
copy the reference into the starter. Running that script changes the starter.

With Docker installed:

```text
docker build -t stock-revision-benchmark .
docker run --rm stock-revision-benchmark
```

The image uses the Python 3.12 slim base and runs the standard-library suite.
The first build needs access to the base image. The build and GitHub workflow
should be run in your own environment before you claim they passed there.

## Scope of the evaluation

The reference solution is deliberately public so the project can be studied.
The suite is a useful demonstration, not a secret benchmark or proof against
all hard-coded submissions. An actual assessment needs independently protected
test cases, a defined environment, and review for shortcut solutions.
