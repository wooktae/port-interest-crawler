"""interest 데이터 일일 수집 단계를 순서대로 실행하는 운영 orchestration 후보 스크립트다.

KRX 로그인, 뉴스, 가격, 수급, 공매도 등 여러 수집 모듈의 run 함수를 호출한다.
실행 시 외부 요청, Selenium/Chrome, DB 쓰기가 연쇄적으로 발생하므로 운영 환경에서만 사용한다.
"""

from datetime import datetime
import time

# 각 모듈 import
import interest_krx_login_new
import interest_news
import interest_agency
import interest_foreignindex
import interest_commodity
import interest_macroeconomic
import interest_price
import interest_investorflow
import interest_program
import interest_shortsell
import interest_marketbreadth


def run_step(name, func):

    start = datetime.now()

    try:
        result = func()

        elapsed = (datetime.now() - start).total_seconds()

        return {
            "name": name,
            "status": result.get("status", "SUCCESS"),
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
    """일일 수집 모듈을 정해진 순서로 실행하고 단계별 결과를 요약한다."""

    print("=" * 100)
    print("INTEREST DAILY ORCHESTRATION")
    print("=" * 100)
    print("Starting....\n")

    results = []

    # -----------------------------
    # 1. NAVER
    # -----------------------------
    results.append(run_step("interest_news", interest_news.run))
    results.append(run_step("interest_agency", interest_agency.run))
    time.sleep(2)

    # -----------------------------
    # 2. GLOBAL (yfinance)
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

    # -----------------------------
    # 5. KRX 로그인
    # -----------------------------
    results.append(run_step("krx_login", interest_krx_login_new.run))
    time.sleep(2)

    # -----------------------------
    # 6. KRX DATA
    # -----------------------------
    results.append(run_step("interest_program", interest_program.run))
    results.append(run_step("interest_shortsell", interest_shortsell.run))
    time.sleep(2)

    # -----------------------------
    # SUMMARY
    # -----------------------------
    print("\n" + "=" * 100)
    print("DAILY ORCHESTRATION SUMMARY")
    print("=" * 100)

    for r in results:
        print(
            f"{r['status']:<8} | {r['name']:<22} | "
            f"elapsed={r['elapsed']:>8.2f}s | error={r['error']}"
        )


if __name__ == "__main__":
    main()
