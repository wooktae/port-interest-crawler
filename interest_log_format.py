# interest_log_format.py

from typing import List, Dict, Optional


LINE = "=" * 100


def _print_header(step_name: str):
    print(LINE)
    print(f"START :: {step_name}")
    print(LINE)
    print("Starting....\n")


def _print_collected_dates(dates: Optional[List[str]]):
    print("[Collected Date]")
    if not dates:
        print("None")
        return

    for d in dates:
        print(d)


def _print_success(lines: Optional[List[str]]):
    if not lines:
        return

    print("\n[Success]")
    for line in lines:
        print(line)


def _print_error(lines: Optional[List[str]]):
    if not lines:
        return

    print("\n[Error]")
    for line in lines:
        print(line)


def _print_failed(lines: Optional[List[str]]):
    if not lines:
        return

    print("\n[Failed]")
    for line in lines:
        print(line)


def print_step_log(step_name: str, result: Dict):
    """
    result schema:
    {
        "status": "SUCCESS" | "FAILED" | "NO_CHANGE",
        "collected_dates": ["2026-03-17", "2026-03-18"],
        "success_lines": [...],
        "error_lines": [...],
        "failed_lines": [...],
        "error_count": 0
    }
    """

    _print_header(step_name)

    # 1. Collected Date (항상 출력)
    _print_collected_dates(result.get("collected_dates"))

    # 2. Success
    _print_success(result.get("success_lines"))

    # 3. Error
    _print_error(result.get("error_lines"))

    # 4. Failed
    _print_failed(result.get("failed_lines"))


# =========================
# DAILY SUMMARY
# =========================

def print_daily_summary(summary_list: List[Dict]):
    """
    summary_list:
    [
        {
            "name": "interest_agency",
            "status": "SUCCESS",
            "elapsed": 3.73,
            "error": "-"
        }
    ]
    """

    print("\n" + LINE)
    print("DAILY ORCHESTRATION SUMMARY")
    print(LINE)

    for s in summary_list:
        status = s.get("status", "-")
        name = s.get("name", "-")
        elapsed = s.get("elapsed", 0)
        error = s.get("error", "-")

        print(f"{status:<7} | {name:<22} | elapsed={elapsed:>8.2f}s | error={error}")