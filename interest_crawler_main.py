"""Orchestration candidate script that manually runs the main interest data collection modules in sequence.

It calls the collection of ticker, news, research, foreign indices, commodities, macro, and market breadth.
Because it includes external requests and DB writes, confirm the target modules and environment variables before actually running.
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
    """Call the run functions of the main collection modules in order."""

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
