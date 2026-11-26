"""Regenerate the fictional ledger using integer arithmetic and a local seed."""
import csv
from pathlib import Path
import random


def generate(path):
    rng = random.Random(8381)
    with Path(path).open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(("movement_id", "cohort", "segment", "booked_year", "published", "cents"))
        for cohort in range(2008, 2023):
            for segment, development in (("property", (56, 24, 13, 7)), ("casualty", (35, 33, 21, 11))):
                base = rng.randint(30000, 40000) + 1500 * (cohort - 2008)
                for age, share in enumerate(development):
                    booked = cohort + age
                    key = f"{cohort}-{segment}-{age}"
                    cents = 100 * (base * share // 100 + rng.randint(-1200, 1200))
                    # A shifted tail simulates deteriorating development, and some reports
                    # are published after the nominal year end.
                    if segment == "casualty" and cohort >= 2016 and age == 3:
                        cents += 250000
                    delay = (cohort + age + (segment == "casualty")) % 9 == 0
                    published = f"{booked+1}-01-20" if delay else f"{booked}-11-20"
                    w.writerow((key, cohort, segment, booked, published, cents))
                    if (cohort + age) % 6 == 0:
                        w.writerow((key, cohort, segment, booked, f"{booked+2}-02-06", cents - 17000))


if __name__ == "__main__":
    generate(Path(__file__).parent / "fixtures/illustrative_ledger.csv")
