import json
from datetime import datetime
from collections import defaultdict
from typing import Any
from statistics import mean, stdev
from constants.dummy import sample


def analyze_financial_data(aa_data: dict | str) -> dict:
    if isinstance(aa_data, str):
        aa_data = json.loads(aa_data)

    summary = {
        "data_overview": extract_data_overview(aa_data),
        "accounts": [],
        "aggregated_insights": {},
        "behavioral_patterns": {},
        "financial_health_indicators": {},
        "personalization_context": {}
    }

    all_transactions = []

    # Process each FIP's data
    for fip_data in aa_data.get("fiData", []):
        fip_id = fip_data.get("fipID", "unknown")

        for account_data in fip_data.get("data", []):
            decrypted = account_data.get("decryptedFI", {})
            account = decrypted.get("account", {})
            account_type = decrypted.get("type", account.get("type", "unknown"))

            account_summary = analyze_account(account, account_type, fip_id)
            summary["accounts"].append(account_summary)

            # Collect transactions for aggregate analysis
            txns = account.get("transactions", {}).get("transaction", [])
            all_transactions.extend(txns)

    # Generate aggregate insights across all accounts
    summary["aggregated_insights"] = generate_aggregate_insights(summary["accounts"])
    summary["behavioral_patterns"] = analyze_behavioral_patterns(all_transactions)
    summary["financial_health_indicators"] = calculate_financial_health(summary)
    summary["personalization_context"] = generate_personalization_context(summary)

    return summary


def extract_data_overview(aa_data: dict) -> dict:
    """Extract high-level metadata about the data."""
    data_range = aa_data.get("dataRange", {})

    from_date = parse_date(data_range.get("from", ""))
    to_date = parse_date(data_range.get("to", ""))

    return {
        "consent_id": aa_data.get("consentId"),
        "data_session_id": aa_data.get("dataSessionId"),
        "data_from": from_date.isoformat() if from_date else None,
        "data_to": to_date.isoformat() if to_date else None,
        "data_span_days": (to_date - from_date).days if from_date and to_date else None,
        "total_fips": len(aa_data.get("fiData", [])),
        "fetch_timestamp": aa_data.get("timestamp")
    }


def analyze_account(account: dict, account_type: str, fip_id: str) -> dict:
    """Analyze a single account and return its summary."""
    profile = account.get("profile", {})
    summary_data = account.get("summary", {})
    transactions = account.get("transactions", {})

    # Extract holder info (with privacy in mind - we keep minimal PII)
    holders = profile.get("holders", {})
    holder_list = holders.get("holder", [])
    holder_info = None
    if holder_list:
        h = holder_list[0]
        holder_info = {
            "name": h.get("name", "") if h.get("name") else None,
            "has_nominee": h.get("nominee") != "NOT-REGISTERED",
            "kyc_compliant": h.get("ckycCompliance") == "true"
        }

    # Analyze transactions
    txn_analysis = analyze_transactions(transactions.get("transaction", []))

    # Build account summary based on type
    account_summary = {
        "account_type": account_type,
        "masked_account": account.get("maskedAccNumber"),
        "fip_id": fip_id,
        "holder_info": holder_info,
        "account_details": extract_account_details(summary_data, account_type),
        "transaction_summary": txn_analysis
    }

    return account_summary


def extract_account_details(summary: dict, account_type: str) -> dict:
    """Extract relevant account details based on account type."""
    base_details = {
        "branch": summary.get("branch"),
        "ifsc": summary.get("ifsc"),
        "opening_date": summary.get("openingDate")
    }

    if account_type in ["recurring_deposit", "term_deposit", "deposit"]:
        base_details.update({
            "principal_amount": safe_float(summary.get("principalAmount")),
            "current_value": safe_float(summary.get("currentValue")),
            "maturity_amount": safe_float(summary.get("maturityAmount")),
            "maturity_date": summary.get("maturityDate"),
            "interest_rate": safe_float(summary.get("interestRate")),
            "compounding_frequency": summary.get("compoundingFrequency"),
            "tenure_months": safe_int(summary.get("tenureMonths")),
            "recurring_amount": safe_float(summary.get("recurringAmount")) if account_type == "recurring_deposit" else None
        })
    elif account_type in ["savings", "current"]:
        base_details.update({
            "current_balance": safe_float(summary.get("currentBalance")),
            "available_balance": safe_float(summary.get("availableBalance")),
            "currency": summary.get("currency", "INR"),
            "status": summary.get("status")
        })
    elif account_type == "credit_card":
        base_details.update({
            "credit_limit": safe_float(summary.get("creditLimit")),
            "available_credit": safe_float(summary.get("availableCredit")),
            "current_due": safe_float(summary.get("currentDue")),
            "total_due": safe_float(summary.get("totalDueAmount")),
            "due_date": summary.get("dueDate"),
            "reward_points": safe_float(summary.get("loyaltyPoints"))
        })

    return base_details


def analyze_transactions(transactions: list) -> dict:
    """Comprehensive transaction analysis."""
    if not transactions:
        return {"total_transactions": 0, "message": "No transactions found"}

    # Parse all transactions
    parsed_txns = []
    for txn in transactions:
        parsed = {
            "amount": safe_float(txn.get("amount", 0)),
            "mode": txn.get("mode", "UNKNOWN"),
            "type": txn.get("type", "UNKNOWN"),
            "narration": txn.get("narration", ""),
            "timestamp": parse_date(txn.get("transactionTimestamp", "")),
            "balance": safe_float(txn.get("balance", 0)),
            "reference": txn.get("reference")
        }
        if parsed["timestamp"]:
            parsed_txns.append(parsed)

    if not parsed_txns:
        return {"total_transactions": len(transactions), "message": "Could not parse transaction dates"}

    # Sort by timestamp
    parsed_txns.sort(key=lambda x: x["timestamp"])

    # Calculate date range
    date_range = {
        "earliest": parsed_txns[0]["timestamp"].isoformat(),
        "latest": parsed_txns[-1]["timestamp"].isoformat(),
        "span_days": (parsed_txns[-1]["timestamp"] - parsed_txns[0]["timestamp"]).days
    }

    # Amount statistics
    amounts = [t["amount"] for t in parsed_txns]
    amount_stats = {
        "total": round(sum(amounts), 2),
        "average": round(mean(amounts), 2),
        "min": round(min(amounts), 2),
        "max": round(max(amounts), 2),
        "std_dev": round(stdev(amounts), 2) if len(amounts) > 1 else 0
    }

    # Breakdown by transaction type
    by_type = defaultdict(lambda: {"count": 0, "total": 0, "amounts": []})
    for txn in parsed_txns:
        t = txn["type"]
        by_type[t]["count"] += 1
        by_type[t]["total"] += txn["amount"]
        by_type[t]["amounts"].append(txn["amount"])

    type_breakdown = {}
    for t, data in by_type.items():
        type_breakdown[t] = {
            "count": data["count"],
            "total": round(data["total"], 2),
            "average": round(mean(data["amounts"]), 2),
            "percentage_of_total": round((data["total"] / amount_stats["total"]) * 100, 1) if amount_stats["total"] > 0 else 0
        }

    # Breakdown by payment mode
    by_mode = defaultdict(lambda: {"count": 0, "total": 0})
    for txn in parsed_txns:
        m = txn["mode"]
        by_mode[m]["count"] += 1
        by_mode[m]["total"] += txn["amount"]

    mode_breakdown = {
        mode: {"count": data["count"], "total": round(data["total"], 2)}
        for mode, data in by_mode.items()
    }

    # Monthly breakdown
    monthly = defaultdict(lambda: {"count": 0, "total": 0})
    for txn in parsed_txns:
        month_key = txn["timestamp"].strftime("%Y-%m")
        monthly[month_key]["count"] += 1
        monthly[month_key]["total"] += txn["amount"]

    monthly_breakdown = {
        k: {"count": v["count"], "total": round(v["total"], 2)}
        for k, v in sorted(monthly.items())
    }

    # Balance trajectory
    balances = [t["balance"] for t in parsed_txns if t["balance"] > 0]
    balance_stats = {}
    if balances:
        balance_stats = {
            "starting": balances[0],
            "ending": balances[-1],
            "highest": max(balances),
            "lowest": min(balances),
            "average": round(mean(balances), 2),
            "trend": "increasing" if balances[-1] > balances[0] else "decreasing" if balances[-1] < balances[0] else "stable"
        }

    # Identify large/unusual transactions (> 2 std dev from mean)
    threshold = amount_stats["average"] + (2 * amount_stats["std_dev"]) if amount_stats["std_dev"] > 0 else amount_stats["max"]
    large_transactions = [
        {
            "amount": t["amount"],
            "type": t["type"],
            "mode": t["mode"],
            "date": t["timestamp"].isoformat()
        }
        for t in parsed_txns if t["amount"] > threshold
    ][:10]  # Limit to top 10

    return {
        "total_transactions": len(parsed_txns),
        "date_range": date_range,
        "amount_statistics": amount_stats,
        "by_transaction_type": type_breakdown,
        "by_payment_mode": mode_breakdown,
        "monthly_breakdown": monthly_breakdown,
        "balance_statistics": balance_stats,
        "notable_large_transactions": large_transactions
    }


def analyze_behavioral_patterns(all_transactions: list) -> dict:
    """Analyze behavioral patterns across all transactions."""
    if not all_transactions:
        return {"message": "No transactions to analyze"}

    parsed = []
    for txn in all_transactions:
        ts = parse_date(txn.get("transactionTimestamp", ""))
        if ts:
            parsed.append({
                "timestamp": ts,
                "amount": safe_float(txn.get("amount", 0)),
                "mode": txn.get("mode"),
                "type": txn.get("type"),
                "weekday": ts.weekday(),
                "hour": ts.hour,
                "day_of_month": ts.day
            })

    if not parsed:
        return {"message": "Could not parse transactions"}

    # Day of week patterns
    weekday_counts = defaultdict(int)
    weekday_amounts = defaultdict(float)
    weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    for t in parsed:
        weekday_counts[t["weekday"]] += 1
        weekday_amounts[t["weekday"]] += t["amount"]

    most_active_day = max(weekday_counts, key=weekday_counts.get) if weekday_counts else 0

    # Hour patterns
    hour_counts = defaultdict(int)
    for t in parsed:
        hour_counts[t["hour"]] += 1

    peak_hours = sorted(hour_counts.items(), key=lambda x: -x[1])[:3]

    # Day of month patterns (for recurring payments detection)
    day_counts = defaultdict(int)
    for t in parsed:
        day_counts[t["day_of_month"]] += 1

    frequent_days = [day for day, count in day_counts.items() if count >= 3]

    # Payment mode preferences
    mode_counts = defaultdict(int)
    for t in parsed:
        mode_counts[t["mode"]] += 1

    total_txns = len(parsed)
    preferred_mode = max(mode_counts, key=mode_counts.get) if mode_counts else "UNKNOWN"
    mode_percentages = {
        mode: round((count / total_txns) * 100, 1)
        for mode, count in mode_counts.items()
    }

    return {
        "most_active_weekday": weekday_names[most_active_day],
        "weekday_distribution": {
            weekday_names[i]: {"count": weekday_counts[i], "total_amount": round(weekday_amounts[i], 2)}
            for i in range(7)
        },
        "peak_transaction_hours": [{"hour": h, "count": c} for h, c in peak_hours],
        "recurring_payment_days": sorted(frequent_days),
        "preferred_payment_mode": preferred_mode,
        "payment_mode_distribution": mode_percentages,
        "total_analyzed_transactions": total_txns
    }


def generate_aggregate_insights(accounts: list) -> dict:
    """Generate aggregate insights across all accounts."""
    total_value = 0
    total_transactions = 0
    account_types = defaultdict(int)

    deposit_accounts = []

    for acc in accounts:
        account_types[acc["account_type"]] += 1

        details = acc.get("account_details", {})
        txn_summary = acc.get("transaction_summary", {})

        # Sum up values
        if details.get("current_value"):
            total_value += details["current_value"]
        elif details.get("current_balance"):
            total_value += details["current_balance"]

        total_transactions += txn_summary.get("total_transactions", 0)

        # Track deposits for maturity planning
        if acc["account_type"] in ["recurring_deposit", "term_deposit"]:
            deposit_accounts.append({
                "type": acc["account_type"],
                "maturity_date": details.get("maturity_date"),
                "maturity_amount": details.get("maturity_amount"),
                "interest_rate": details.get("interest_rate")
            })

    return {
        "total_accounts": len(accounts),
        "account_type_distribution": dict(account_types),
        "estimated_total_value": round(total_value, 2),
        "total_transactions_analyzed": total_transactions,
        "deposit_accounts": deposit_accounts,
        "has_nominee_registered": any(
            (acc.get("holder_info") or {}).get("has_nominee", False)
            for acc in accounts
            if acc is not None
        )
    }


def calculate_financial_health(summary: dict) -> dict:
    """Calculate financial health indicators."""
    indicators = {
        "diversification_score": 0,
        "transaction_regularity": "unknown",
        "balance_trend": "unknown",
        "risk_indicators": [],
        "positive_indicators": []
    }

    # Diversification score based on account types
    account_types = summary.get("aggregated_insights", {}).get("account_type_distribution", {})
    indicators["diversification_score"] = min(len(account_types) * 20, 100)

    # Check for positive indicators
    if summary.get("aggregated_insights", {}).get("has_nominee_registered"):
        indicators["positive_indicators"].append("Nominee registered for accounts")

    # Check deposit health
    deposits = summary.get("aggregated_insights", {}).get("deposit_accounts", [])
    if deposits:
        indicators["positive_indicators"].append(f"Active savings in {len(deposits)} deposit account(s)")

    # Transaction patterns
    patterns = summary.get("behavioral_patterns", {})
    if patterns.get("total_analyzed_transactions", 0) > 50:
        indicators["transaction_regularity"] = "high"
        indicators["positive_indicators"].append("Regular transaction activity")
    elif patterns.get("total_analyzed_transactions", 0) > 20:
        indicators["transaction_regularity"] = "moderate"
    else:
        indicators["transaction_regularity"] = "low"

    # Balance trend from accounts
    for acc in summary.get("accounts", []):
        balance_stats = acc.get("transaction_summary", {}).get("balance_statistics", {})
        if balance_stats.get("trend") == "increasing":
            indicators["balance_trend"] = "positive"
            indicators["positive_indicators"].append("Balance showing upward trend")
            break
        elif balance_stats.get("trend") == "decreasing":
            indicators["balance_trend"] = "negative"
            indicators["risk_indicators"].append("Balance showing downward trend")

    return indicators


def generate_personalization_context(summary: dict) -> dict:
    """
    Generate a context object specifically designed for LLM personalization.
    This is the primary output for crafting personalized responses.
    """
    context = {
        "user_profile": {},
        "financial_snapshot": {},
        "conversation_hints": [],
        "recommended_topics": [],
        "avoid_topics": []
    }

    # User profile hints
    accounts = summary.get("accounts", [])
    if accounts:
        holder = accounts[0].get("holder_info") or {}
        context["user_profile"]["kyc_status"] = "compliant" if holder.get("kyc_compliant") else "pending"
        context["user_profile"]["nominee_status"] = "registered" if holder.get("has_nominee") else "not_registered"
    # Financial snapshot for quick reference
    insights = summary.get("aggregated_insights", {})
    context["financial_snapshot"] = {
        "total_accounts": insights.get("total_accounts", 0),
        "estimated_portfolio_value": insights.get("estimated_total_value", 0),
        "primary_account_types": list(insights.get("account_type_distribution", {}).keys()),
        "has_deposits": len(insights.get("deposit_accounts", [])) > 0
    }

    # Behavioral insights
    patterns = summary.get("behavioral_patterns", {})
    context["financial_snapshot"]["preferred_payment_mode"] = patterns.get("preferred_payment_mode")
    context["financial_snapshot"]["most_active_day"] = patterns.get("most_active_weekday")

    # Health indicators
    health = summary.get("financial_health_indicators", {})
    context["financial_snapshot"]["health_score"] = health.get("diversification_score", 0)

    # Generate conversation hints
    if not insights.get("has_nominee_registered"):
        context["conversation_hints"].append("User hasn't registered nominees - could benefit from estate planning discussion")
        context["recommended_topics"].append("nominee_registration")

    if health.get("diversification_score", 0) < 40:
        context["conversation_hints"].append("Low diversification - may benefit from investment diversification advice")
        context["recommended_topics"].append("portfolio_diversification")

    deposits = insights.get("deposit_accounts", [])
    upcoming_maturities = []
    for dep in deposits:
        mat_date = parse_date(dep.get("maturity_date", ""))
        if mat_date:
            # Make comparison timezone-naive
            mat_date_naive = mat_date.replace(tzinfo=None) if mat_date.tzinfo else mat_date
            days_to_maturity = (mat_date_naive - datetime.now()).days
            if 0 < days_to_maturity <= 90:
                upcoming_maturities.append({
                    "type": dep["type"],
                    "days_remaining": days_to_maturity,
                    "amount": dep.get("maturity_amount")
                })

    if upcoming_maturities:
        context["conversation_hints"].append(f"{len(upcoming_maturities)} deposit(s) maturing within 90 days")
        context["recommended_topics"].append("reinvestment_options")
        context["financial_snapshot"]["upcoming_maturities"] = upcoming_maturities

    if health.get("balance_trend") == "negative":
        context["conversation_hints"].append("Balance trend is negative - user might benefit from budgeting tips")
        context["recommended_topics"].append("expense_management")

    # Topics to potentially avoid (sensitive areas)
    if health.get("risk_indicators"):
        context["avoid_topics"].append("aggressive_investments")

    return context


# Utility functions
def parse_date(date_str: str) -> datetime | None:
    """Parse various date formats."""
    if not date_str:
        return None

    formats = [
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S+00:00",
        "%Y-%m-%d",
    ]

    # Handle timezone offset format like +00:00
    if "+" in date_str and date_str.count(":") >= 2:
        # Remove colon from timezone
        parts = date_str.rsplit("+", 1)
        if len(parts) == 2 and ":" in parts[1]:
            tz_part = parts[1].replace(":", "")
            date_str = parts[0] + "+" + tz_part

    for fmt in formats:
        try:
            return datetime.strptime(date_str.replace("Z", "+0000"), fmt.replace("Z", "%z"))
        except ValueError:
            continue

    # Fallback: try parsing just the date part
    try:
        return datetime.fromisoformat(date_str[:19])
    except ValueError:
        return None


def safe_float(value: Any) -> float:
    """Safely convert to float."""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def safe_int(value: Any) -> int:
    """Safely convert to int."""
    if value is None:
        return 0
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0


def get_summary_for_llm(aa_data: dict | str) -> str:
    """
    Convenience function that returns a formatted string summary
    ready to be injected into an LLM prompt.
    """
    analysis = analyze_financial_data(aa_data)

    # Create a condensed, LLM-friendly summary
    context = analysis["personalization_context"]
    snapshot = context["financial_snapshot"]

    lines = [
        "=== USER FINANCIAL CONTEXT ===",
        f"Portfolio Overview: {snapshot.get('total_accounts', 0)} accounts, estimated value ₹{snapshot.get('estimated_portfolio_value', 0):,.2f}",
        f"Account Types: {', '.join(snapshot.get('primary_account_types', []))}",
        f"Financial Health Score: {snapshot.get('health_score', 0)}/100",
        f"Preferred Payment: {snapshot.get('preferred_payment_mode', 'N/A')}",
        f"Most Active Day: {snapshot.get('most_active_day', 'N/A')}",
        "",
        "Key Insights:"
    ]

    for hint in context.get("conversation_hints", []):
        lines.append(f"  • {hint}")

    if context.get("recommended_topics"):
        lines.append(f"\nRecommended Discussion Topics: {', '.join(context['recommended_topics'])}")

    if snapshot.get("upcoming_maturities"):
        lines.append("\nUpcoming Maturities:")
        for mat in snapshot["upcoming_maturities"]:
            lines.append(f"  • {mat['type']}: ₹{mat.get('amount', 0):,.2f} in {mat['days_remaining']} days")

    lines.append("\n=== END CONTEXT ===")

    return "\n".join(lines)


# Example usage and testing
if __name__ == "__main__":

    print("Usage: python financial_analyzer.py <path_to_aa_data.json>")
    print("\nRunning with sample test...")


    data = sample

    # Run analysis
    result = analyze_financial_data(data)

    print("\n" + "="*60)
    print("FULL ANALYSIS RESULT")
    print("="*60)
    print(json.dumps(result, indent=2, default=str))

    print("\n" + "="*60)
    print("LLM-READY SUMMARY")
    print("="*60)
    print(get_summary_for_llm(data))
