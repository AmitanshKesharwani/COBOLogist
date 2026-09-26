      *================================================================
      * PROGRAM:     CLAIMS-ELIGIBILITY
      * DESCRIPTION: Determines whether an insurance claim is payable
      *              and computes the payout amount.
      *              Input fields are expected to be populated in
      *              WORKING-STORAGE by the calling harness before
      *              MAIN-PROCEDURE is invoked.
      *================================================================
       IDENTIFICATION DIVISION.
       PROGRAM-ID. CLAIMS-ELIGIBILITY.
       AUTHOR.     LEGACY-SYSTEMS-TEAM.

      *================================================================
       DATA DIVISION.
       WORKING-STORAGE SECTION.

      *----------------------------------------------------------------
      * INPUT FIELDS
      *----------------------------------------------------------------
      * Policy status: A = Active, L = Lapsed
       01  WS-POLICY-STATUS            PIC X(1).

      * Policy start date (YYYYMMDD)
       01  WS-POLICY-START-DATE        PIC 9(8).

      * Date policy lapsed (YYYYMMDD); zero-filled if still active
       01  WS-LAPSE-DATE               PIC 9(8).

      * Date claim was filed (YYYYMMDD)
       01  WS-CLAIM-DATE               PIC 9(8).

      * Dollar amount of the submitted claim
       01  WS-CLAIM-AMOUNT             PIC 9(7)V99 COMP-3.

      * Maximum coverage amount defined in the policy
       01  WS-COVERAGE-LIMIT           PIC 9(7)V99 COMP-3.

      * Two-letter state code for the policyholder
       01  WS-STATE-CODE               PIC X(2).

      * Free-text incident description; spaces = not provided
       01  WS-INCIDENT-DESCRIPTION     PIC X(100).

      * Y = this claim date falls on the last day of a fiscal quarter
       01  WS-FISCAL-QTR-END-FLAG      PIC X(1).

      *----------------------------------------------------------------
      * COMPUTED WORKING VARIABLES  (populated in MAIN-PROCEDURE
      * before rule paragraphs are called)
      *----------------------------------------------------------------
      * Whole days between lapse date and claim date
       01  WS-DAYS-SINCE-LAPSE         PIC 9(4).

      * Whole years the policy was continuously active before lapsing
       01  WS-POLICY-TENURE-YEARS      PIC 9(3).

      * Scratch fields for date arithmetic
       01  WS-LAPSE-YEAR               PIC 9(4).
       01  WS-START-YEAR               PIC 9(4).
       01  WS-CLAIM-DATE-NUM           PIC 9(8).
       01  WS-LAPSE-DATE-NUM           PIC 9(8).

      *----------------------------------------------------------------
      * OUTPUT FIELDS
      *----------------------------------------------------------------
      * Y = claim is payable, N = claim is denied
       01  WS-PAYABLE                  PIC X(1).

      * Final payout amount (may differ from claim amount after
      * adjustments)
       01  WS-PAYOUT-AMOUNT            PIC 9(7)V99 COMP-3.

      *================================================================
       PROCEDURE DIVISION.

      *----------------------------------------------------------------
       MAIN-PROCEDURE.
      *----------------------------------------------------------------
           INITIALIZE WS-PAYABLE
           MOVE 'N'             TO WS-PAYABLE
           MOVE ZEROS           TO WS-PAYOUT-AMOUNT

      *    --- Compute days since lapse (simple YYYYMMDD subtraction;
      *        sufficient precision for the 30-day threshold check) ---
           MOVE WS-CLAIM-DATE   TO WS-CLAIM-DATE-NUM
           MOVE WS-LAPSE-DATE   TO WS-LAPSE-DATE-NUM
           SUBTRACT WS-LAPSE-DATE-NUM FROM WS-CLAIM-DATE-NUM
               GIVING WS-DAYS-SINCE-LAPSE

      *    --- Compute policy tenure in whole years ---
           DIVIDE WS-POLICY-START-DATE BY 10000
               GIVING WS-START-YEAR REMAINDER WS-LAPSE-DATE-NUM
           DIVIDE WS-LAPSE-DATE BY 10000
               GIVING WS-LAPSE-YEAR REMAINDER WS-CLAIM-DATE-NUM
           SUBTRACT WS-START-YEAR FROM WS-LAPSE-YEAR
               GIVING WS-POLICY-TENURE-YEARS

      *    --- Evaluate rules in priority order ---
           PERFORM STANDARD-ELIGIBILITY-RULE
           PERFORM GRACE-PERIOD-RULE
           PERFORM STATE-CARVE-OUT-RULE
           PERFORM ORPHAN-RULE

           STOP RUN.

      *----------------------------------------------------------------
       STANDARD-ELIGIBILITY-RULE.
      *----------------------------------------------------------------
      *    Core eligibility check: policy must be active and the
      *    submitted amount must not exceed the coverage limit.
           IF WS-POLICY-STATUS   = 'A'
           AND WS-CLAIM-AMOUNT  <= WS-COVERAGE-LIMIT
               MOVE 'Y'           TO WS-PAYABLE
               MOVE WS-CLAIM-AMOUNT TO WS-PAYOUT-AMOUNT
           END-IF.

      *----------------------------------------------------------------
      * Grandfather clause for long-tenured policyholders: a claim
      * filed within the 30-day grace window after a policy lapse is
      * still payable provided the policy had been continuously active
      * for more than 5 years prior to lapsing.
      *----------------------------------------------------------------
       GRACE-PERIOD-RULE.
      *----------------------------------------------------------------
           IF WS-POLICY-STATUS          = 'L'
           AND WS-DAYS-SINCE-LAPSE     <= 30
           AND WS-POLICY-TENURE-YEARS   > 5
               MOVE 'Y'                 TO WS-PAYABLE
               MOVE WS-CLAIM-AMOUNT     TO WS-PAYOUT-AMOUNT
           END-IF.

      *----------------------------------------------------------------
      * 2003 settlement requirement -- see legal/settlement-NY-2003.
      * Claims originating from NY policyholders are payable even
      * when the incident description field has not been provided.
      *----------------------------------------------------------------
       STATE-CARVE-OUT-RULE.
      *----------------------------------------------------------------
           IF WS-STATE-CODE             = 'NY'
           AND WS-INCIDENT-DESCRIPTION  = SPACES
               MOVE 'Y'                 TO WS-PAYABLE
               MOVE WS-CLAIM-AMOUNT     TO WS-PAYOUT-AMOUNT
           END-IF.

      *----------------------------------------------------------------
       ORPHAN-RULE.
      *----------------------------------------------------------------
           IF WS-FISCAL-QTR-END-FLAG    = 'Y'
               COMPUTE WS-PAYOUT-AMOUNT =
                   WS-PAYOUT-AMOUNT * 1.005
           END-IF.
