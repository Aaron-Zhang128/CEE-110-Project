#!/usr/bin/env python3
"""Splice the case-history data into index.html.

index.html is a single self-contained file that never touches the network, so
the data has to live inside it rather than be fetched. This writes a compact JS
array between the CASES-BEGIN / CASES-END markers in the page, leaving the rest
of the file untouched.

Run after build_antecedent_rainfall.py:  python3 embed_cases.py
"""

import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = os.path.join(os.path.dirname(HERE), "index.html")
BEGIN, END = "  // CASES-BEGIN", "  // CASES-END"


def num(v):
    if v in (None, "", "None"):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return int(f) if f == int(f) else round(f, 1)


def main():
    with open(os.path.join(HERE, "landfill-failures.csv"), encoding="utf-8") as f:
        facts = {r["id"]: r for r in csv.DictReader(f)}
    with open(os.path.join(HERE, "antecedent-rainfall.json"), encoding="utf-8") as f:
        rain = json.load(f)

    cases = []
    for r in rain:
        s = facts[r["id"]]
        case = {
            "id": r["id"],
            "short": s["short"],
            "site": s["site"],
            "place": s["city"] + ", " + s["country"],
            "date": s["failure_date"],
            "deaths": num(s["deaths"]),
            "volume": num(s["volume_m3"]),
            "implicated": s["rainfall_implicated"],
            "trigger": s["reported_trigger"],
            "source": s["source"],
        }
        if r.get("station_id"):
            case.update({
                "gauge": r["station_name"].title(),
                "network": r["source"],
                "km": num(r["distance_km"]),
                "p1": num(r.get("p1_mm")), "p3": num(r.get("p3_mm")),
                "p7": num(r.get("p7_mm")), "p15": num(r.get("p15_mm")),
                "p30": num(r.get("p30_mm")), "p60": num(r.get("p60_mm")),
                "p7obs": num(r.get("p7_days_observed")),
                "p30obs": num(r.get("p30_days_observed")),
                "p7shift": num(r.get("p7_mm_shift1")),
                "p7pct": num(r.get("p7_pctl")), "p30pct": num(r.get("p30_pctl")),
                "p7ret": num(r.get("p7_return_yr")), "p30ret": num(r.get("p30_return_yr")),
                "daily": r.get("daily_mm") or [],
            })
        cases.append(case)

    cases.sort(key=lambda c: c["date"])
    body = ",\n".join("    " + json.dumps(c, ensure_ascii=False, separators=(",", ":"))
                      for c in cases)
    block = BEGIN + "\n  const CASES = [\n" + body + "\n  ];\n" + END

    with open(PAGE, encoding="utf-8") as f:
        page = f.read()
    i, j = page.find(BEGIN), page.find(END)
    if i < 0 or j < 0:
        raise SystemExit("markers %s / %s not found in %s" % (BEGIN, END, PAGE))
    page = page[:i] + block + page[j + len(END):]
    with open(PAGE, "w", encoding="utf-8") as f:
        f.write(page)
    print("embedded %d cases into %s" % (len(cases), PAGE))


if __name__ == "__main__":
    main()
