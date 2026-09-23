"""ECS/Fargate 전용 interest non-GUI daily crawler orchestration.

Does not include the KRX GUI-dependent steps.
Excluded:
- interest_krx_login_new
- interest_program
- interest_shortsell

External requests and DB writes occur when run, so use it only in the paper operational environment.
"""

from datetime import datetime
import time

import interest_news
import interest_agency
import interest_foreignindex
import interest_commodity
import interest_macroeconomic
import interest_price
import interest_investorflow
import interest_marketbreadth


def run_step(name, func):
    start = datetime.now()

    try:
        result = func()
        elapsed = (datetime.now() - start).total_seconds()

        if isinstance(result, dict):
            status = result.get("status", "SUCCESS")
        else:
            status = "SUCCESS"

        return {
            "name": name,
            "status": status,
            "elapsed": elapsed,
            "error": "-"
        }

    except Exception as e:
        elapsed = (datetime.now() - start).total_seconds()

        return {
            "name": name,
            "status": "FAILED",
            "elapsed": elapsed,
            "error": str(e)
        }


def main():
    print("=" * 100, flush=True)
    print("INTEREST DAILY NON-GUI ORCHESTRATION", flush=True)
    print("=" * 100, flush=True)
    print("Starting non-GUI crawler steps...", flush=True)

    results = []

    # -----------------------------
    # 1. NAVER
    # -----------------------------
    results.append(run_step("interest_news", interest_news.run))
    results.append(run_step("interest_agency", interest_agency.run))
    time.sleep(2)

    # -----------------------------
    # 2. GLOBAL
    # -----------------------------
    results.append(run_step("interest_foreignindex", interest_foreignindex.run))
    results.append(run_step("interest_commodity", interest_commodity.run))
    results.append(run_step("interest_macroeconomic", interest_macroeconomic.run))
    time.sleep(2)

    # -----------------------------
    # 3. PRICE + FLOW
    # -----------------------------
    results.append(run_step("interest_price", interest_price.run))
    results.append(run_step("interest_investorflow", interest_investorflow.run))
    time.sleep(2)

    # -----------------------------
    # 4. DERIVED
    # -----------------------------
    results.append(run_step("interest_marketbreadth", interest_marketbreadth.run))

    print("\n" + "=" * 100, flush=True)
    print("NON-GUI DAILY ORCHESTRATION SUMMARY", flush=True)
    print("=" * 100, flush=True)

    failed = []

    for r in results:
        print(
            f"{r['status']:<8} | {r['name']:<22} | "
            f"elapsed={r['elapsed']:>8.2f}s | error={r['error']}",
            flush=True
        )

        if r["status"] == "FAILED":
            failed.append(r)

    if failed:
        failed_names = [r["name"] for r in failed]
        raise RuntimeError(f"NON-GUI crawler failed steps: {failed_names}")


if __name__ == "__main__":
    main()
