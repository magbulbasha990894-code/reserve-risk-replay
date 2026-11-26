"""Replay actuarial reserve estimates without using late-published observations."""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import date
from fractions import Fraction
import json
from pathlib import Path


@dataclass(frozen=True)
class Movement:
    movement_id: str
    cohort: int
    segment: str
    booked_year: int
    published: date
    cents: int

    def __post_init__(self):
        if not self.movement_id or not self.segment or self.cohort > self.booked_year:
            raise ValueError("invalid movement key or development year")
        if self.published.year < self.booked_year:
            raise ValueError("publication cannot precede booking year")


def read_ledger(path):
    with Path(path).open(newline="", encoding="utf-8") as fh:
        return [Movement(r["movement_id"], int(r["cohort"]), r["segment"],
                         int(r["booked_year"]), date.fromisoformat(r["published"]), int(r["cents"]))
                for r in csv.DictReader(fh)]


def triangle(ledger, as_of: date, max_age):
    """Take the latest version visible at the snapshot; revisions replace, never add."""
    latest = {}
    versions = set()
    identity = {}
    for m in ledger:
        key = m.movement_id, m.published
        if key in versions:
            raise ValueError(f"duplicate version: {m.movement_id} on {m.published}")
        versions.add(key)
        key = m.cohort, m.segment, m.booked_year
        if identity.setdefault(m.movement_id, key) != key:
            raise ValueError("movement identity changed across revisions")
        if m.published <= as_of and m.booked_year <= as_of.year:
            if m.movement_id not in latest or latest[m.movement_id].published < m.published:
                latest[m.movement_id] = m
    increments = {}
    for m in latest.values():
        age = m.booked_year - m.cohort
        if age <= max_age:
            pair = m.cohort, m.segment
            row = increments.setdefault(pair, {})
            row[age] = row.get(age, 0) + m.cents
    # A year-end age cell is observable only if every age up to it is present.
    # Missing cells are not treated as zero. Use an explicit zero ledger entry for
    # observed no-movement cells.
    result = {}
    for pair, row in increments.items():
        balance = 0
        result[pair] = {}
        for i in range(max_age + 1):
            if i not in row:
                break
            balance += row[i]
            if balance < 0:
                raise ValueError("cumulative paid became negative")
            result[pair][i] = balance
    return result


def factors(vintage, cohort, segment, from_age, max_age, min_support):
    """Use prior cohorts only; fall back from segment to pooled rows, with disclosed counts."""
    result = []
    for age in range(from_age, max_age):
        eligible = [(s, row) for (y, s), row in vintage.items()
                    if y < cohort and age + 1 in row and row[age] > 0]
        local = [row for s, row in eligible if s == segment]
        rows = local if len(local) >= min_support else [row for _, row in eligible]
        if len(rows) < min_support:
            raise ValueError(f"insufficient support for age {age} to {age + 1}")
        # Volume-weighted paid development, not an unweighted mean of ratios.
        ratio = Fraction(sum(row[age + 1] for row in rows), sum(row[age] for row in rows))
        result.append((ratio, len(rows), "segment" if rows is local else "pooled"))
    return result


def backtest(ledger, max_age=3, evaluation_year=2022, minimum_support=2):
    """Replay every available origin from age zero through one before maturity."""
    if max_age < 1 or minimum_support < 1:
        raise ValueError("positive max age and minimum support required")
    label_cutoff = date(evaluation_year, 12, 31)
    truth = triangle(ledger, label_cutoff, max_age)
    vintages = {}
    cases = []
    excluded = []
    for (cohort, segment), actual in sorted(truth.items()):
        if max_age not in actual:
            excluded.append({"cohort": cohort, "segment": segment, "reason": "label not mature"})
            continue
        for age in range(max_age):
            origin = date(cohort + age, 12, 31)
            if origin not in vintages:
                vintages[origin] = triangle(ledger, origin, max_age)
            vintage = vintages[origin]
            balance = vintage.get((cohort, segment), {})
            key = {"cohort": cohort, "segment": segment, "age": age, "as_of": origin.isoformat()}
            try:
                if age not in balance:
                    raise ValueError("origin observation unavailable")
                links = factors(vintage, cohort, segment, age, max_age, minimum_support)
            except ValueError as ex:
                excluded.append({**key, "reason": str(ex)})
                continue
            estimate = Fraction(balance[age])
            for ratio, _, _ in links:
                estimate *= ratio
            cases.append({**key, "paid_cents": balance[age], "actual_ultimate_cents": actual[max_age],
                          "baseline_cents": balance[age], "estimate_cents": round(estimate),
                          "estimated_reserve_cents": round(estimate) - balance[age],
                          "links": [{"age": age + i, "count": n, "source": s, "factor": str(f)}
                                    for i, (f, n, s) in enumerate(links)]})
    return {"evaluation_as_of": label_cutoff.isoformat(), "case_count": len(cases),
            "metrics": metrics(cases),
            "metrics_by_age": {str(age): metrics([c for c in cases if c["age"] == age])
                              for age in range(max_age)},
            "cases": cases, "excluded": excluded}


def metrics(cases):
    actual = sum(x["actual_ultimate_cents"] for x in cases)
    def one(field):
        errors = [x[field] - x["actual_ultimate_cents"] for x in cases]
        return {"mean_absolute_error_cents": round(sum(map(abs, errors)) / len(errors), 2) if errors else None,
                "weighted_absolute_error": round(sum(map(abs, errors)) / actual, 6) if actual else None,
                "signed_error_cents": sum(errors) if errors else None}
    return {"n": len(cases), "prior_cohort_development": one("estimate_cents"),
            "paid_to_date_baseline": one("baseline_cents")}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ledger", default="fixtures/illustrative_ledger.csv")
    p.add_argument("--max-age", default=3, type=int)
    p.add_argument("--evaluation-year", default=2022, type=int)
    p.add_argument("--minimum-support", default=2, type=int)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    try:
        result = backtest(read_ledger(args.ledger), args.max_age, args.evaluation_year, args.minimum_support)
    except (OSError, KeyError, ValueError) as ex:
        p.exit(2, f"input error: {ex}\n")
    rendered = json.dumps(result, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
