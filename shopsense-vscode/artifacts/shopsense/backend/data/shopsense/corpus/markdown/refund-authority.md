# Refund Authorisation and Escalation Matrix

## KARTWAY CUSTOMER OPERATIONS POLICY MANUAL
### MODULE 8: REFUND AUTHORISATION MATRIX AND FINANCIAL DISCRETION
**Document ID:** POL-OPS-804  
**Effective Date:** 12 October 2024  
**Applies To:** All Customer Support Agents, Team Leads, Operations Managers, Finance Department Personnel, and Automated Support Systems.

---

### 8.1 PURPOSE AND SCOPE
This policy establishes mandatory financial thresholds and approval hierarchies for all customer refunds, order cancellations, and goodwill credits processed within the Kartway platform. Adherence to these limits is mandatory for all operations personnel and automated systems.

---

### 8.2 DEFINITIONS AND CALCULATION OF NET REFUND VALUE
1. **Net Refund Value:** The final monetary amount returned to the customer after the deduction of any applicable restocking fees and return pickup fees.
2. **Approval Tier Determination:** The tier required to authorize a transaction is strictly determined by the Net Refund Value, calculated as:
   $$\text{Net Refund Value} = \text{Gross Paid Amount} - (\text{Restocking Fee} + \text{Pickup Fee})$$
3. **Replacement Orders:** A product replacement request shall be authorized at the exact same approval tier as a monetary refund of the total amount paid for the original order.

---

### 8.3 REFUND AUTHORISATION MATRIX
Every refund request, regardless of the underlying reason (including but not limited to transit damage, item not received, defective merchandise, or order cancellation prior to dispatch), must be authorized in accordance with the following thresholds:

| Approval Tier | Minimum Net Refund Value (INR) | Maximum Net Refund Value (INR) | Authorized Roles / Systems |
| :--- | :--- | :--- | :--- |
| **Tier 1** | 0 | 2,000 | • Frontline Support Agent<br>• Automated Assistant (Bot) |
| **Tier 2** | 2,001 | 10,000 | • Team Lead |
| **Tier 3** | 10,001 | 50,000 | • Operations Manager |
| **Tier 4** | 50,001 | No Upper Limit | • Finance Department |

---

### 8.4 AUTOMATED SYSTEM RESTRICTIONS
1. **Hard Threshold Cap:** The automated assistant (bot) acting alone is strictly prohibited from auto-approving any refund or replacement where the Net Refund Value exceeds 2,000 INR.
2. **Override Prohibition:** The 2,000 INR automated cap cannot be overridden under any circumstances, regardless of customer loyalty tier, account age, sentiment analysis scores, or executive escalation tags. Any automated workflow attempting to exceed 2,000 INR must route the ticket to a human queue matching the appropriate tier in Section 8.3.

---

### 8.5 CANCELLATIONS PRIOR TO DISPATCH
1. **Pre-Dispatch Prepaid Orders:** Cancellations requested before dispatch are subject to the standard Refund Authorisation Matrix set forth in Section 8.3, based on the Net Refund Value.
2. **Cash-on-Delivery (COD) Orders:** A Cash-on-Delivery order cancelled prior to dispatch involves zero monetary exchange. Consequently, such cancellations require no funds to be returned and do not require approval from any tier within the matrix.

---

### 8.6 GOODWILL CREDITS
1. **Wallet Issuance:** Goodwill credits represent discretionary service recovery funds issued exclusively to the customer's Kartway digital wallet.
2. **Issuing Authority:** Goodwill credits may be issued by any operational tier, including frontline agents and the automated assistant.
3. **Value Cap:** The maximum goodwill credit that may be issued is capped strictly at 500 INR per order. No tier possesses the authority to issue goodwill exceeding 500 INR on a single order.
4. **Frequency Limit:** A maximum of exactly one (1) goodwill credit may be issued per unique order.
5. **Stacking Prohibition:** Goodwill credits may not be stacked, combined, or issued concurrently with a full monetary refund on the same order. An order may receive either a monetary refund or a goodwill credit, but never both.
