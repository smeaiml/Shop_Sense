# Return Fraud and Abuse Prevention Standard

### SECTION 14: RETURN ABUSE AND FRAUD MONITORING

#### 14.1 Purpose and Scope
This policy establishes the operational criteria, thresholds, and mandatory handling procedures for customer accounts exhibiting high return volumes, serial refund requests, or indicators of transactional abuse on the Kartway marketplace. Support agents are strictly bound by the rules detailed herein.

#### 14.2 Return-Rate Review Threshold
14.2.1 An account shall be automatically referred to the Kartway Risk and Review Queue when both of the following conditions are met:
(a) The account maintains a return rate of $0.40$ or higher (representing $40\%$ or more of all lifetime orders returned); and
(b) The account has a history of at least $10$ lifetime orders.

14.2.2 The outcome of the review referenced in clause 14.2.1 shall result in one of two formal statuses: Account Cleared or Account Flagged.

14.2.3 Notwithstanding the threshold in clause 14.2.1, the Kartway Fraud Operations Team retains the authority to manually flag any account based on corroborating risk evidence, irrespective of the account's specific return rate.

#### 14.3 Serial Refund Requesters
14.3.1 A customer account shall be classified as a "Serial Refund Requester" upon submitting $3$ or more refund requests within a rolling $90$-day window.

14.3.2 Upon classification under clause 14.3.1, the account shall be placed under review immediately.

#### 14.4 Operational Restrictions During Review or Flag Status
14.4.1 While an account is in a Flagged status or Under Review status, no refund, return, or replacement may be approved automatically by any system workflow or agent tool, regardless of the monetary value of the transaction.

14.4.2 Any request for a refund, return, or replacement originating from an account designated as Flagged or Under Review must be manually routed to the Fraud Desk using the designated system routing tag `account_under_review`.

#### 14.5 Prohibition on Status Disclosure
14.5.1 Support agents and automated assistant modules are strictly prohibited from confirming, denying, or otherwise disclosing to a customer that their account is flagged, under review, or subject to fraud monitoring.

14.5.2 In response to customer inquiries regarding delayed refunds or blocked automated approvals, agents shall state only that the transaction requires standard administrative verification.

#### 14.6 Escalation Route for Suspected Fraud
14.6.1 Where an agent identifies patterns indicative of deliberate fraudulent activity beyond standard return abuse (including but not limited to Wardrobing rings, item substitution, or unauthorized chargeback manipulation), the agent shall immediately escalate the ticket via the internal ticketing system to the Kartway Fraud Operations Queue, setting the priority level to Tier-1 High Risk.
