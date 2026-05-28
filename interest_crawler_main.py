"""관심 데이터 주요 수집 모듈을 수동으로 순차 실행하는 orchestration 후보 스크립트다.

ticker, 뉴스, 리서치, 해외지수, 원자재, 매크로, market breadth 수집을 호출한다.
외부 요청과 DB 쓰기가 포함되므로 실제 실행 전 대상 모듈과 환경변수를 확인한다.
"""

import interest_ticker_main
import interest_ticker_finance
import interest_ticker_value
import interest_news
import interest_agency
import interest_foreignindex
import interest_commodity
import interest_macroeconomic
import interest_marketbreadth


def run():
    """주요 수집 모듈의 run 함수를 순서대로 호출한다."""

    print("=================================")
    print("INTEREST CRAWLER START")
    print("=================================")

    interest_ticker_main.run()
    interest_ticker_finance.run()
    interest_ticker_value.run()

    interest_news.run()
    interest_agency.run()

    interest_foreignindex.run()
    interest_commodity.run()
    interest_macroeconomic.run()
    interest_marketbreadth.run()

    print("=================================")
    print("INTEREST CRAWLER DONE")
    print("=================================")


if __name__ == "__main__":
    run()
