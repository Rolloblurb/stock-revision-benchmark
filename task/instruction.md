# Task: reconcile stock with revised events

Implement `starter/reconcile.py` as a Python command-line program. A shipment's
stock movement may be corrected, voided, recorded late, or given an effective
time in another time zone. The program must produce stock as known at a cutoff.
This is an original simulated exercise, not an account of a production incident.

## Invocation

```text
python starter/reconcile.py --inventory PATH --revisions PATH --as-of TIMESTAMP --output PATH
```

`TIMESTAMP` has the form `YYYY-MM-DDTHH:MM:SS[.ffffff]Z` or the same form with
a numeric UTC offset `+HH:MM` or `-HH:MM`; a fractional part has 1-6 digits.
All timestamps must include an explicit offset and represent valid dates and
times. Compare instants after converting them to UTC. An output path must differ
from both input paths. The output's parent directory must already exist.

Both inputs are UTF-8 CSV, with the exact headers and order shown below. Blank
records, missing or extra fields, and invalid CSV are errors. Identifiers must
match `[A-Za-z0-9][A-Za-z0-9._-]*`. Do not trim values or ignore malformed
rows, even if their `recorded_at` is after the cutoff.

`inventory.csv`:

```text
sku,opening_stock
```

Each SKU appears at most once. `opening_stock` is 1-12 decimal digits and is
nonnegative. A header-only inventory is allowed.

`revisions.csv`:

```text
event_id,sku,delta,effective_at,recorded_at,status
```

`delta` is an integer with 1-12 decimal digits, optionally preceded by `+` or
`-`. `status` is exactly `posted` or `void`. Both timestamps follow the format
above. A header-only revisions file is allowed.

## Rules

1. For each `event_id`, consider only revisions with `recorded_at <= as_of`.
2. Select the maximum eligible `recorded_at` instant. A repeated latest revision
   with the same SKU, integer delta, effective instant, and status is harmless,
   even if equivalent timestamps are written using different offsets.
3. If two latest revisions for the same event have different semantic payloads,
   report an error. Conflicts at older timestamps do not matter if superseded.
4. A selected revision contributes its delta only if its status is `posted`
   and its effective instant is `<= as_of`. A selected `void` or future-effective
   revision suppresses the event; do not fall back to an older revision.
5. A contributing revision referring to an unknown SKU is an error. An unknown
   SKU in a non-contributing revision is allowed, provided the row is valid.
6. Output every inventory SKU, sorted lexicographically. `net_change` is the
   sum of the selected contributing deltas. `closing_stock` is opening plus
   net change; negative closing stock is permitted.

The output is UTF-8 CSV with LF line endings and the exact header
`sku,opening_stock,net_change,closing_stock`. Normal successful execution exits
0 with no stdout. `--help` may print help to stdout and exit 0.
Invalid inputs or output errors exit 2 with an `error:` message on stderr and
no stdout. Validate before replacing the output: on any validation failure an
existing output file must remain unchanged. Do not overwrite either input.

## Validate your implementation

By default, the test suite evaluates the reference. To evaluate a candidate:

Windows CMD:

```bat
set STOCK_TASK_CANDIDATE=%CD%\starter\reconcile.py
python -m unittest discover -s tests -v
```

Linux/macOS:

```sh
STOCK_TASK_CANDIDATE="$PWD/starter/reconcile.py" python -m unittest discover -s tests -v
```

The starter intentionally fails until implemented. The repository includes the
reference solution for learning, so this public exercise is not a hidden test.
