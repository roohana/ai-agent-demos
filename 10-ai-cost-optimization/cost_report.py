"""Token and cost report for LLM workloads (demo with synthetic usage data).

  python cost_report.py --generate      # writes sample usage.csv (synthetic)
  python cost_report.py                 # prints cost by app/model, waste signals and a forecast

Prices below are ILLUSTRATIVE placeholders. Replace PRICES with your own contract/list prices per 1M tokens.
"""
import argparse
import csv
import random
from collections import defaultdict
from datetime import date, timedelta

PRICES = {  # (input, output) per 1M tokens, illustrative only
    "large-model": (5.00, 15.00),
    "small-model": (0.15, 0.60),
}
APPS = {  # app -> (model, avg prompt tokens, avg completion tokens, requests per day)
    "finance-copilot": ("large-model", 5200, 380, 900),
    "hr-faq-bot": ("large-model", 3100, 250, 1500),
    "doc-summariser": ("small-model", 2400, 300, 2200),
    "sow-generator": ("large-model", 7800, 1900, 120),
}


def generate(path="usage.csv", days=30):
    random.seed(7)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "app", "model", "requests", "prompt_tokens", "completion_tokens"])
        for d in range(days):
            day = date(2026, 9, 26) + timedelta(days=d)
            for app, (model, pt, ct, rq) in APPS.items():
                n = int(rq * random.uniform(0.85, 1.15) * (1 + d * 0.006))
                w.writerow([day, app, model, n, int(n * pt * random.uniform(0.95, 1.05)), int(n * ct * random.uniform(0.95, 1.05))])


def cost(model, p, c):
    pin, pout = PRICES[model]
    return p / 1e6 * pin + c / 1e6 * pout


def report(path="usage.csv"):
    rows = list(csv.DictReader(open(path)))
    by_app = defaultdict(lambda: {"req": 0, "p": 0, "c": 0, "cost": 0.0, "model": ""})
    by_day = defaultdict(float)
    for r in rows:
        a = by_app[r["app"]]
        p, c, n = int(r["prompt_tokens"]), int(r["completion_tokens"]), int(r["requests"])
        a.update(model=r["model"])
        a["req"] += n; a["p"] += p; a["c"] += c
        k = cost(r["model"], p, c)
        a["cost"] += k
        by_day[r["date"]] += k
    total = sum(a["cost"] for a in by_app.values())
    print(f"Total cost: {total:,.2f} over {len(by_day)} days\n")
    print(f"{'app':<18}{'model':<13}{'requests':>10}{'avg prompt':>12}{'avg compl.':>12}{'cost':>10}{'share':>8}")
    for name, a in sorted(by_app.items(), key=lambda kv: -kv[1]["cost"]):
        print(f"{name:<18}{a['model']:<13}{a['req']:>10,}{a['p']/a['req']:>12,.0f}{a['c']/a['req']:>12,.0f}{a['cost']:>10,.2f}{a['cost']/total:>8.0%}")
    print("\nWaste signals")
    for name, a in by_app.items():
        ratio = a["p"] / max(a["c"], 1)
        if ratio > 10:
            print(f"- {name}: prompt/completion ratio {ratio:.0f}:1. Check system prompt length, history trimming and retrieved context size.")
        if a["model"] == "large-model" and a["p"] / a["req"] > 2500 and a["c"] / a["req"] < 400:
            alt = cost("small-model", a["p"], a["c"])
            print(f"- {name}: short answers on a large model. Evaluate the small model; indicative saving up to {a['cost'] - alt:,.2f} (verify quality first).")
    days = sorted(by_day)
    last7 = sum(by_day[d] for d in days[-7:]) / 7
    prev7 = sum(by_day[d] for d in days[-14:-7]) / 7
    growth = last7 / prev7 - 1
    print(f"\nForecast: last 7 days average {last7:,.2f}/day ({growth:+.1%} vs previous week); next 30 days ~ {last7 * 30:,.0f} at current run rate.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--generate", action="store_true")
    ap.add_argument("--file", default="usage.csv")
    a = ap.parse_args()
    if a.generate:
        generate(a.file)
        print("wrote", a.file)
    else:
        report(a.file)
