"""Seed a workspace domain with compiled curriculum (testbed helper).

Usage (from product/backend):
    python scripts/seed_domain.py <domain-id> [source-domain-id]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from apore.domains import seed, store  # noqa: E402

PROGRAM_ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    domain_id = sys.argv[1]
    source = sys.argv[2] if len(sys.argv) > 2 else "discrete-math"
    record = store.load_domain(domain_id)
    copied = seed.seed_domain(record, program_root=PROGRAM_ROOT, source_domain_id=source)
    print(f"Seeded {record.domain_id} with chapters: {copied or 'none (already seeded)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
