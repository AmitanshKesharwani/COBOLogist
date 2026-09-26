"""
claims_eligibility.py — Python translation of legacy/claims_eligibility.cbl

Implements the claims-eligibility adjudication logic translated from the
COBOL source. Accepts the same input fields as the COBOL WORKING-STORAGE
record and returns (payable, payout_amount) mirroring WS-PAYABLE and
WS-PAYOUT-AMOUNT.

Date arithmetic matches the COBOL exactly: WS-DAYS-SINCE-LAPSE is computed
by raw integer subtraction of two YYYYMMDD integers, and
WS-POLICY-TENURE-YEARS by integer division of each date by 10000.
"""


def evaluate_claim(
    policy_status: str,
    policy_start_date: int,
    lapse_date: int,
    claim_date: int,
    claim_amount: float,
    coverage_limit: float,
    state_code: str,
    incident_description: str,
    fiscal_qtr_end_flag: str,
) -> tuple[str, float]:
    """Evaluate a single insurance claim.

    Parameters match the COBOL WORKING-STORAGE input fields 1-to-1.
    Returns (payable, payout_amount) where payable is 'Y' or 'N'.
    """
    # --- Initialise outputs (mirrors COBOL MAIN-PROCEDURE init) ---
    payable: str = "N"
    payout_amount: float = 0.0

    # --- Scratch variables (mirrors COBOL integer arithmetic exactly) ---
    # WS-DAYS-SINCE-LAPSE = WS-CLAIM-DATE - WS-LAPSE-DATE
    days_since_lapse: int = claim_date - lapse_date

    # WS-POLICY-TENURE-YEARS = (lapse_date // 10000) - (policy_start_date // 10000)
    start_year: int = policy_start_date // 10000
    lapse_year: int = lapse_date // 10000
    policy_tenure_years: int = lapse_year - start_year

    # --- STANDARD-ELIGIBILITY-RULE ---
    if policy_status == "A" and claim_amount <= coverage_limit:
        payable = "Y"
        payout_amount = claim_amount

    # --- GRACE-PERIOD-RULE ---
    if policy_status == "L" and days_since_lapse <= 30 and policy_tenure_years > 5:
        payable = "Y"
        payout_amount = claim_amount

    # --- STATE-CARVE-OUT-RULE ---
    if state_code == "NY" and incident_description.strip() == "":
        payable = "Y"
        payout_amount = claim_amount

    return payable, payout_amount
