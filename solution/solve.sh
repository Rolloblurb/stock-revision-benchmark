#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cp "$root/reference/reconcile.py" "$root/starter/reconcile.py"
printf '%s\n' 'Reference copied to starter/reconcile.py'
