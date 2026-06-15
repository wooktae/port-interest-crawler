from pathlib import Path

root = Path(r"C:\Workspaces\port_strategy_research")

files_to_create = {
    "research_backtest_market_adapter.py": '''"""Research backtest market decision adapter.

preprocessor market feature row를 port_strategy_common 입력 컨텍스트로 변환하고,
daily / backtest 흐름이 공유할 MarketDecision 값을 반환한다.

이 모듈은 port_strategy_decision 런타임 의존을 제거하기 위해
Strategy Research 내부 adapter로 분리했다.
DB 접근이나 외부 API 호출은 하지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from port_strategy_common.config import MARKET_CONFIG
from port_strategy_common.common_context import CommonMarketContext
from port_strategy_common.common_market import common_decide_market


@dataclass
class MarketDecision:
    signal_type: str
    base_exposure: Decimal
    max_positions: int
    min_score: Decimal
    min_flow: Decimal
    reason: str


CFG = MARKET_CONFIG


def d(v):
    if v is None:
        return Decimal("0")
    return Decimal(str(v))


def evaluate_market(market: dict) -> MarketDecision:
    """공통 market 판단을 호출하고 research backtest용 dataclass로 변환한다."""
    context = CommonMarketContext(
        trade_date=str(market.get("date", "TEST")),
        market_regime_score=float(d(market.get("market_regime_score"))),
        breadth_pressure_score=float(d(market.get("breadth_pressure_score"))),
        flow_pressure_score=float(d(market.get("flow_pressure_score"))),
        macro_pressure_score=float(d(market.get("macro_pressure_score"))),
        program_pressure_score=float(d(market.get("program_pressure_score"))),
        raw=dict(market),
    )

    decision = common_decide_market(context, CFG)

    return MarketDecision(
        signal_type=decision.market_signal,
        base_exposure=Decimal(str(decision.base_exposure)),
        max_positions=decision.max_positions,
        min_score=Decimal(str(decision.min_score)),
        min_flow=Decimal(str(decision.min_flow)),
        reason=decision.reason,
    )
''',
    "research_backtest_filter_adapter.py": '''"""Research backtest buy candidate filter adapter.

stock feature 목록과 market decision을 port_strategy_common 필터 입력으로
맞춰 전달한다.

이 모듈은 port_strategy_decision 런타임 의존을 제거하기 위해
Strategy Research 내부 adapter로 분리했다.
자체 DB 접근은 없으며, decision reason 문자열과 공통 설정 계약을 그대로 유지한다.
"""

from __future__ import annotations

from decimal import Decimal

from port_strategy_common.config import FILTER_CONFIG
from port_strategy_common.common_result import CommonMarketDecision
from port_strategy_common.common_buy_filter import common_filter_buy_candidates


CFG = FILTER_CONFIG


def d(v, default="0"):
    if v is None:
        return Decimal(str(default))
    return Decimal(str(v))


def filter_buy_candidates(stock_rows, decision):
    """공통 buy filter를 호출해 backtest 매수 후보를 선별한다."""
    common_decision = CommonMarketDecision(
        market_signal=decision.signal_type,
        base_exposure=float(decision.base_exposure),
        max_positions=decision.max_positions,
        min_score=float(decision.min_score),
        min_flow=float(decision.min_flow),
        reason=decision.reason,
        detail={},
    )

    return common_filter_buy_candidates(
        stock_rows=stock_rows,
        decision=common_decision,
        config=CFG,
    )
''',
    "research_backtest_sizing_adapter.py": '''"""Research backtest buy candidate sizing adapter.

필터를 통과한 후보와 market decision을 port_strategy_common sizing 입력으로 변환한다.

이 모듈은 port_strategy_decision 런타임 의존을 제거하기 위해
Strategy Research 내부 adapter로 분리했다.
포지션 크기 계산은 port_strategy_common에 위임하며 DB 접근은 하지 않는다.
"""

from __future__ import annotations

from decimal import Decimal

from port_strategy_common.config import SIZING_CONFIG
from port_strategy_common.common_result import CommonMarketDecision
from port_strategy_common.common_buy_sizing import common_allocate_positions


CFG = SIZING_CONFIG


def d(v):
    if v is None:
        return Decimal("0")
    return Decimal(str(v))


def clamp(v, mn, mx):
    return max(mn, min(v, mx))


def allocate_positions(buy_candidates, market_decision):
    """공통 sizing 로직을 호출해 후보별 position_size를 산출한다."""
    common_decision = CommonMarketDecision(
        market_signal=market_decision.signal_type,
        base_exposure=float(market_decision.base_exposure),
        max_positions=market_decision.max_positions,
        min_score=float(market_decision.min_score),
        min_flow=float(market_decision.min_flow),
        reason=market_decision.reason,
        detail={},
    )

    return common_allocate_positions(
        buy_candidates=buy_candidates,
        market_decision=common_decision,
        config=CFG,
    )
''',
}

for name, content in files_to_create.items():
    path = root / name
    path.write_text(content, encoding="utf-8")
    print(f"[OK] created {path.name}")

replacements = {
    "from port_strategy_decision.backtest_filter import filter_buy_candidates":
        "from port_strategy_research.research_backtest_filter_adapter import filter_buy_candidates",
    "from port_strategy_decision.backtest_market import evaluate_market":
        "from port_strategy_research.research_backtest_market_adapter import evaluate_market",
    "from port_strategy_decision.backtest_sizing import allocate_positions":
        "from port_strategy_research.research_backtest_sizing_adapter import allocate_positions",
}

updated_files = []

for path in root.glob("*.py"):
    if path.name == "patch_research_decision_dependency.py":
        continue

    text = path.read_text(encoding="utf-8-sig")
    new_text = text

    for old, new in replacements.items():
        new_text = new_text.replace(old, new)

    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
        updated_files.append(path.name)

print("[OK] updated imports:", updated_files)

# 한글 확인: 신규 adapter 파일 앞부분을 utf-8로 다시 읽어 출력
for name in files_to_create:
    path = root / name
    preview = path.read_text(encoding="utf-8")[:300]
    print("")
    print(f"--- preview: {name} ---")
    print(preview)

# 남은 decision 직접 의존 확인
remaining = []

for path in root.glob("*.py"):
    if path.name == "patch_research_decision_dependency.py":
        continue

    text = path.read_text(encoding="utf-8-sig")
    for pattern in (
        "port_strategy_decision.backtest_filter",
        "port_strategy_decision.backtest_market",
        "port_strategy_decision.backtest_sizing",
    ):
        if pattern in text:
            remaining.append((path.name, pattern))

print("")
if remaining:
    print("[WARN] remaining decision adapter imports:")
    for file_name, pattern in remaining:
        print(f"  - {file_name}: {pattern}")
else:
    print("[OK] no remaining port_strategy_decision backtest adapter imports")