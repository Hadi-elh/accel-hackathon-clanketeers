"""Rules audit on real notices. Zero API calls, zero cost.

python -m eval.rules_audit --limit 500

Prints every notice a rule would reject, with the evidence sentence, so a human can scan for
false rejections (the only rules failure that loses a match). Also reports coverage: the share
of the real stream the rules decide for free. Read every REJECT line; it takes two minutes.
"""
from __future__ import annotations

import argparse
from collections import Counter

from models import rules


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=500)
    ap.add_argument("--notices-file")
    ap.add_argument("--profile", default="vandijk")
    a = ap.parse_args(argv)

    from eval.run import load_profile, load_unlabelled
    profile = load_profile(a.profile)
    notices = [it["notice"] for it in load_unlabelled(a.limit, a.notices_file)]
    fired, hits, conflicts = Counter(), Counter(), 0
    for n in notices:
        t = rules.triage(n, profile)
        for h in t.positive_hits:
            hits[h] += 1
        if t.reject:
            fired[t.rule] += 1
            print(f"REJECT {t.rule:<13} {n.get('id')}  | {t.reject['evidence'][:140]}")
        elif t.positive_hits and any(rx.search(n.get("body") or "")
                                     for rx, _, _ in rules._COMPILED.values()):
            conflicts += 1
    total = len(notices)
    print(f"\n{total} notices | rules decide {sum(fired.values())} "
          f"({100 * sum(fired.values()) / max(total, 1):.0f}%) for free | {dict(fired)}")
    print(f"negative pattern present but blocked by a positive keyword: {conflicts} "
          f"(sent to the model instead of rejected)")
    print(f"most common positive keywords: {hits.most_common(12)}")


if __name__ == "__main__":
    main()
