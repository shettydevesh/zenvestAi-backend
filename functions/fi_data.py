from config.database import supabase
from datetime import datetime, date
from collections import defaultdict
import uuid


def get_fi_data(
    user_id: str,
    data_to: str = None
) -> dict:
    """
    Fetch financial data and return in FI_DATA_READY format.
    Never returns None - always returns a valid structure.

    Args:
        user_id: The user's UUID
        data_to: End date (YYYY-MM-DD), defaults to today

    Returns:
        dict: FI_DATA_READY formatted response (never None)
    """
    if data_to is None:
        data_to = date.today().isoformat()

    try:
        # Fetch accounts
        accounts_response = (
            supabase.table('user_financial_accounts')
            .select('*')
            .eq('user_id', user_id)
            .execute()
        )
        accounts = accounts_response.data or []

        if not accounts:
            return _empty_response(data_to)

        # Fetch transactions (no start date filter - get all from beginning)
        account_ids = [acc['id'] for acc in accounts if acc.get('id')]

        if not account_ids:
            return _empty_response(data_to)

        txn_response = (
            supabase.table('account_transactions')
            .select('*')
            .eq('user_id', user_id)
            .in_('account_id', account_ids)
            .lte('transaction_timestamp', f"{data_to}T23:59:59")
            .order('transaction_timestamp')
            .execute()
        )

        # Group transactions by account
        txn_by_account = defaultdict(list)
        for txn in (txn_response.data or []):
            if txn and txn.get('account_id'):
                txn_by_account[txn['account_id']].append(txn)

        # Determine the earliest transaction date for data_from
        all_txns = txn_response.data or []
        if all_txns and all_txns[0].get('transaction_timestamp'):
            data_from = _format_date(all_txns[0]['transaction_timestamp'])
        else:
            # If no transactions, use earliest account opening date
            opening_dates = [acc.get('opening_date') for acc in accounts if acc.get('opening_date')]
            data_from = _format_date(min(opening_dates)) if opening_dates else date.today().isoformat()

        # Build response
        return _build_response(accounts, txn_by_account, data_from, data_to)

    except Exception as e:
        # Log the error but still return a valid empty response
        print(f"Error fetching FI data: {e}")
        return _empty_response(data_to)


def _format_ts(ts: str) -> str:
    """Format timestamp to ISO format. Returns empty string on failure."""
    if not ts:
        return ""
    try:
        if 'T' in str(ts):
            dt = datetime.fromisoformat(str(ts).replace('Z', '+00:00').replace('+00', '+00:00'))
        else:
            dt = datetime.fromisoformat(str(ts).replace(' ', 'T').split('+')[0])
        return dt.strftime('%Y-%m-%dT%H:%M:%S+00:00')
    except Exception:
        return ""


def _format_date(ts: str) -> str:
    """Extract date from timestamp. Returns today's date on failure."""
    if not ts:
        return date.today().isoformat()
    try:
        return str(ts).split('T')[0].split(' ')[0]
    except Exception:
        return date.today().isoformat()


def _build_transaction(t: dict) -> dict:
    """Build a single transaction object with safe defaults."""
    if not t:
        return {
            "amount": "",
            "mode": "",
            "narration": "",
            "reference": "",
            "transactionTimestamp": "",
            "txnId": "",
            "type": "",
            "valueDate": "",
            "balance": ""
        }

    return {
        "amount": str(t.get('amount', '') or ''),
        "mode": t.get('mode', '') or '',
        "narration": t.get('narration', '') or '',
        "reference": str(t.get('reference', '') or ''),
        "transactionTimestamp": _format_ts(t.get('transaction_timestamp')),
        "txnId": t.get('transactions_id', '') or '',
        "type": t.get('type', '') or '',
        "valueDate": _format_ts(t.get('value_date')),
        "balance": str(t.get('balance', '') or '')
    }


def _build_account_summary(acc: dict) -> dict:
    """Build account summary with safe defaults."""
    if not acc:
        acc = {}

    return {
        "accountType": acc.get('account_type_category') or 'RECURRING',
        "branch": acc.get('branch') or '',
        "compoundingFrequency": acc.get('compounding_frequency') or '',
        "description": acc.get('description') or '',
        "ifsc": acc.get('ifsc') or '',
        "interestComputation": acc.get('interest_computation') or '',
        "interestOnMaturity": acc.get('interest_on_maturity') or '',
        "interestPayout": acc.get('interest_payout') or '',
        "interestPeriodicPayoutAmount": acc.get('interest_periodic_payout_amount') or '',
        "interestRate": str(acc.get('interest_rate') or ''),
        "maturityAmount": str(acc.get('maturity_amount') or ''),
        "maturityDate": _format_ts(acc.get('maturity_date')),
        "openingDate": _format_ts(acc.get('opening_date')),
        "principalAmount": str(acc.get('principal_amount') or ''),
        "recurringAmount": str(acc.get('recurring_amount') or ''),
        "recurringDepositDay": str(acc.get('recurring_deposit_day') or ''),
        "tenureDays": str(acc.get('tenure_days') or ''),
        "tenureMonths": str(acc.get('tenure_months') or ''),
        "tenureYears": str(acc.get('tenure_years') or ''),
        "currentValue": str(acc.get('current_value') or '')
    }


def _build_account_data(acc: dict, txns: list) -> dict:
    """Build complete account data structure with safe defaults."""
    if not acc:
        acc = {}
    if not txns:
        txns = []

    # Build transactions list
    formatted_txns = [_build_transaction(t) for t in txns if t]

    # Transaction date range
    if txns and txns[0].get('transaction_timestamp'):
        start_dt = _format_date(txns[0]['transaction_timestamp'])
    else:
        start_dt = _format_date(acc.get('opening_date'))

    if txns and txns[-1].get('transaction_timestamp'):
        end_dt = _format_date(txns[-1]['transaction_timestamp'])
    else:
        end_dt = date.today().isoformat()

    return {
        "linkRefNumber": acc.get('link_ref_number', '') or '',
        "maskedAccNumber": acc.get('masked_acc_number', '') or '',
        "decryptedFI": {
            "account": {
                "linkedAccRef": acc.get('link_ref_number', '') or '',
                "maskedAccNumber": acc.get('masked_acc_number', '') or '',
                "type": acc.get('account_type', '') or '',
                "version": "2.0.0",
                "profile": {
                    "holders": {
                        "type": "SINGLE",
                        "holder": []
                    }
                },
                "summary": _build_account_summary(acc),
                "transactions": {
                    "startDate": start_dt,
                    "endDate": end_dt,
                    "transaction": formatted_txns
                }
            },
            "type": acc.get('account_type', '') or ''
        }
    }


def _build_response(accounts: list, txn_by_account: dict, data_from: str, data_to: str) -> dict:
    """Build the complete FI_DATA_READY response. Never returns None."""

    if not accounts:
        accounts = []
    if not txn_by_account:
        txn_by_account = {}

    # Group by (session, fip)
    fip_groups = defaultdict(list)

    for acc in accounts:
        if not acc:
            continue

        txns = txn_by_account.get(acc.get('id'), [])
        account_data = _build_account_data(acc, txns)

        key = (
            acc.get('fi_data_session_id') or str(uuid.uuid4()),
            acc.get('fip_id') or 'unknown'
        )
        fip_groups[key].append(account_data)

    # Group into FIP objects
    session_data = defaultdict(list)
    for (session_id, fip_id), acc_list in fip_groups.items():
        session_data[session_id].append({
            "fipID": fip_id or 'unknown',
            "data": acc_list or []
        })

    # Get first session
    session_id = list(session_data.keys())[0] if session_data else str(uuid.uuid4())

    return {
        "type": "FI_DATA_READY",
        "status": "COMPLETED",
        "timestamp": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
        "consentId": str(uuid.uuid4()),
        "dataSessionId": session_id or str(uuid.uuid4()),
        "dataRange": {
            "from": f"{data_from}T00:00:00.000Z" if data_from else "",
            "to": f"{data_to}T00:00:00.000Z" if data_to else ""
        },
        "fiData": session_data.get(session_id, []),
        "notificationId": str(uuid.uuid4().int % 100000)
    }


def _empty_response(data_to: str = None) -> dict:
    """Return a valid empty response structure. Never returns None."""
    if not data_to:
        data_to = date.today().isoformat()

    return {
        "type": "FI_DATA_READY",
        "status": "COMPLETED",
        "timestamp": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
        "consentId": str(uuid.uuid4()),
        "dataSessionId": str(uuid.uuid4()),
        "dataRange": {
            "from": "",
            "to": f"{data_to}T00:00:00.000Z"
        },
        "fiData": [],
        "notificationId": "0"
    }
