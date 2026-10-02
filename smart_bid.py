"""
HIMAN Smart Bid Pricing — v1.0
================================
Job ka budget dekh ke best bid price suggest karta hai.

Logic:
- Agar client ka budget $10-20 hai → tum $12-15 bid karo (competitive but not lowest)
- Agar budget $20-50 hai        → $18-35 bid karo
- Agar budget $50-100 hai       → $45-70 bid karo
- Agar budget $100-200 hai      → $85-140 bid karo
- Agar budget $200+  hai        → 75-80% of max
- Agar budget nahi likha        → job type ke hisab se average market rate

Strategy:
- Sabse sasta bid mat karo (client sochta hai quality kharab hogi)
- Sabse mehnga bhi mat karo (win rate girega)
- Sweet spot = top 30% bids ka lower end
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class BidSuggestion:
    bid_amount: float          # Suggested bid ($)
    bid_range_low: float       # Minimum acceptable ($)
    bid_range_high: float      # Maximum acceptable ($)
    strategy: str              # Explanation
    confidence: str            # high / medium / low
    delivery_days: int         # Estimated delivery days
    milestone: bool            # Milestone payment recommend karo?


# ── Market rates by job type (USD) ───────────────────────────────────────────
MARKET_RATES = {
    "dev":       {"min": 25, "avg": 60,  "max": 150},
    "writer":    {"min": 15, "avg": 35,  "max": 80},
    "data":      {"min": 10, "avg": 25,  "max": 60},
    "design":    {"min": 20, "avg": 50,  "max": 120},
    "marketing": {"min": 20, "avg": 55,  "max": 130},
}

# ── Delivery days by job type ─────────────────────────────────────────────────
DELIVERY_DAYS = {
    "dev":       3,
    "writer":    2,
    "data":      1,
    "design":    3,
    "marketing": 2,
}


def _parse_budget(raw: str) -> tuple[float, float]:
    """
    Budget string se min/max nikalo.
    Examples:
      "$50-100"   → (50.0, 100.0)
      "$30"       → (30.0, 30.0)
      "50 USD"    → (50.0, 50.0)
      "$100-$200" → (100.0, 200.0)
      ""          → (0.0, 0.0)
    """
    if not raw:
        return 0.0, 0.0
    nums = re.findall(r"\d+(?:\.\d+)?", raw)
    if not nums:
        return 0.0, 0.0
    floats = [float(n) for n in nums]
    if len(floats) == 1:
        return floats[0], floats[0]
    return floats[0], floats[-1]


def suggest_bid(
    budget_raw: str,
    job_kind: str = "writer",
    title: str = "",
    description: str = "",
) -> BidSuggestion:
    """
    Job ke budget aur type ke hisab se best bid suggest karo.

    Args:
        budget_raw: Budget string jaise "$50-100", "$30 USD", ""
        job_kind: dev / writer / data / design / marketing
        title: Job title (optional, for better estimate)
        description: Job desc (optional)

    Returns:
        BidSuggestion object with all details
    """
    kind = job_kind if job_kind in MARKET_RATES else "writer"
    bmin, bmax = _parse_budget(budget_raw)
    market = MARKET_RATES[kind]
    days = DELIVERY_DAYS[kind]

    # ── Case 1: Budget nahi likha ──────────────────────────────────────────
    if bmin == 0 and bmax == 0:
        avg = market["avg"]
        low = market["min"]
        high = market["avg"]
        bid = avg * 0.8  # 20% discount on average — attract client

        # Job title se estimate adjust karo
        combined = (title + " " + description).lower()
        if any(w in combined for w in ["urgent", "asap", "today", "immediately"]):
            bid = avg  # urgent jobs — don't discount
        if any(w in combined for w in ["simple", "easy", "quick", "small", "basic"]):
            bid = max(market["min"], avg * 0.6)
        if any(w in combined for w in ["complex", "advanced", "large", "full", "complete", "system"]):
            bid = avg * 1.2

        return BidSuggestion(
            bid_amount=round(bid, 0),
            bid_range_low=round(low, 0),
            bid_range_high=round(high, 0),
            strategy=(
                f"Budget nahi likha — market average ${market['avg']} ke hisab se "
                f"${bid:.0f} bid karo. Na bahut sasta, na mehnga. "
                f"Proposal mein likho: 'My rate for this is ${bid:.0f}.'"
            ),
            confidence="medium",
            delivery_days=days,
            milestone=bid > 50,
        )

    # ── Case 2: Budget given ───────────────────────────────────────────────
    # Use budget max as reference
    ref = bmax if bmax > 0 else bmin

    # Tiered strategy
    if ref <= 10:
        # Very low — skip ya minimum bid karo
        bid = max(10, ref * 0.9)
        strategy = (
            f"⚠️ Budget bahut kam hai (${ref:.0f}). "
            f"Agar karna chahte ho toh ${bid:.0f} bid karo — lekin yeh worth it nahi hai. "
            f"Skip karne ki salah."
        )
        confidence = "low"

    elif ref <= 20:
        # $10-20 range → bid $12-16
        bid = ref * 0.80
        bid = max(12, min(bid, 16))
        strategy = (
            f"Budget ${bmin:.0f}-${bmax:.0f} — Competitive bid: ${bid:.0f}. "
            f"21 bids hain average pe — middle mein raho. "
            f"Proposal mein speed aur quality emphasize karo."
        )
        confidence = "high"

    elif ref <= 50:
        # $20-50 range → bid 70-80% of max
        bid = ref * 0.75
        bid = max(18, min(bid, 40))
        strategy = (
            f"Budget ${bmin:.0f}-${bmax:.0f} — Bid ${bid:.0f} (75% of max). "
            f"Client ko lagega value mil raha hai. "
            f"Proposal mein past similar work mention karo."
        )
        confidence = "high"

    elif ref <= 100:
        # $50-100 range → bid 65-70% of max
        bid = ref * 0.68
        bid = max(35, min(bid, 70))
        strategy = (
            f"Budget ${bmin:.0f}-${bmax:.0f} — Bid ${bid:.0f}. "
            f"Don't go below $35 — too cheap signals low quality. "
            f"Offer 1 free revision to sweeten the deal."
        )
        confidence = "high"

    elif ref <= 200:
        # $100-200 → bid 70-75%
        bid = ref * 0.72
        bid = max(75, min(bid, 150))
        strategy = (
            f"Budget ${bmin:.0f}-${bmax:.0f} — Bid ${bid:.0f}. "
            f"Is range mein clients quality prefer karte hain. "
            f"Milestone payment suggest karo (50% advance, 50% on delivery)."
        )
        confidence = "high"

    elif ref <= 500:
        # $200-500 → bid 75-80%
        bid = ref * 0.77
        bid = max(150, min(bid, 400))
        strategy = (
            f"Budget ${bmin:.0f}-${bmax:.0f} — Bid ${bid:.0f}. "
            f"Bada project hai — detailed proposal likhna zaroori hai. "
            f"Milestone payment ZAROOR karo."
        )
        confidence = "medium"

    else:
        # $500+ → bid 70-75%
        bid = ref * 0.72
        bid = max(350, bid)
        strategy = (
            f"Budget ${bmin:.0f}-${bmax:.0f} — Bid ${bid:.0f}. "
            f"Bahut bada project — pehle requirements clear karo, phir final price. "
            f"Milestone MUST."
        )
        confidence = "medium"

    # Delivery days adjust by project size
    if ref > 200:
        days = days * 2
    elif ref > 100:
        days = max(days, 3)

    return BidSuggestion(
        bid_amount=round(bid, 0),
        bid_range_low=round(bmin, 0),
        bid_range_high=round(bmax, 0),
        strategy=strategy,
        confidence=confidence,
        delivery_days=days,
        milestone=ref > 100,
    )


def bid_line(suggestion: BidSuggestion) -> str:
    """
    Proposal mein add karne ke liye ek line:
    'My bid: $35 | Delivery: 2 days | Revisions included'
    """
    milestone_note = " | 50% advance + 50% on delivery" if suggestion.milestone else ""
    return (
        f"My bid: ${suggestion.bid_amount:.0f}"
        f" | Delivery: {suggestion.delivery_days} day{'s' if suggestion.delivery_days > 1 else ''}"
        f" | Revisions included"
        f"{milestone_note}"
    )


def format_for_dashboard(s: BidSuggestion) -> dict:
    """Dashboard display ke liye dict format."""
    conf_emoji = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(s.confidence, "⚪")
    return {
        "bid_amount": s.bid_amount,
        "bid_range": f"${s.bid_range_low:.0f} – ${s.bid_range_high:.0f}" if s.bid_range_high > 0 else "N/A",
        "strategy": s.strategy,
        "confidence": f"{conf_emoji} {s.confidence.title()}",
        "delivery_days": s.delivery_days,
        "milestone": s.milestone,
        "bid_line": bid_line(s),
    }


# ── Quick test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    test_cases = [
        ("$10-20",    "writer",    "Write 5 blog posts about AI"),
        ("$50-100",   "dev",       "Python automation script"),
        ("$100-200",  "design",    "Logo design for tech startup"),
        ("",          "data",      "Data entry 500 rows simple"),
        ("$500-1000", "dev",       "Full e-commerce website"),
        ("$15",       "marketing", "Social media posts"),
    ]
    print("=" * 60)
    print("HIMAN Smart Bid Pricing — Test")
    print("=" * 60)
    for budget, kind, title in test_cases:
        s = suggest_bid(budget, kind, title)
        print(f"\nJob: {title}")
        print(f"Budget: {budget or 'N/A'} | Type: {kind}")
        print(f"Suggested Bid: ${s.bid_amount:.0f}")
        print(f"Strategy: {s.strategy}")
        print(f"Bid Line: {bid_line(s)}")
        print("-" * 40)
