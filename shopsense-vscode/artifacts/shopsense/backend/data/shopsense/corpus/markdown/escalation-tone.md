# Escalation Triggers and Customer Communication Standard

# Kartway Operations Policy Manual
**Section:** 14 — Human Escalation Triggers  
**Document ID:** POL-KW-14-ESC  
**Effective Date:** 1 April 2024  
**Applies To:** All Tier-1 Support Agents, Team Leads, and Specialist Desks  

---

## 14.1 Purpose and Scope
This document defines the mandatory operational triggers that require an automated or AI-assisted support interaction to be immediately transferred to a human operator or specialist team at Kartway. Support agents are strictly bound by the thresholds, routing destinations, and procedural rules contained herein. No agent or automated system has the discretion to bypass these escalation paths.

## 14.2 Mandatory Escalation Triggers
When any of the conditions defined in clauses 14.2.1 through 14.2.8 occur during a customer interaction, the support agent must immediately halt automated processing and route the ticket to the designated team using the specified escalation code.

### 14.2.1 `human_requested`
* **Condition:** The customer explicitly asks to speak with a human agent, real person, or manager via text input, voice prompt, or button selection.
* **Routing Destination:** `agent` (Tier-1 General Support Queue)
* **SLA for Handover:** Maximum 120 seconds from the time of the request.

### 14.2.2 `angry_or_abusive`
* **Condition:** The customer uses explicit abusive language, profanity, personal insults directed at Kartway staff, or displays unequivocal, sustained anger (characterized by all-caps text, repeated demands for retribution, or aggressive threats not rising to the level of legal action).
* **Routing Destination:** `team_lead` (Operations Team Lead Queue)
* **SLA for Handover:** Immediate transfer upon detection.

### 14.2.3 `repeat_contact`
* **Condition:** The current contact represents the third (3rd) or later distinct customer-initiated contact regarding the same order number (i.e., two or more prior closed or open tickets exist for the identical order ID).
* **Routing Destination:** `team_lead` (Operations Team Lead Queue)
* **SLA for Handover:** Within 1 hour of ticket assignment.

### 14.2.4 `legal_or_regulatory`
* **Condition:** The customer makes any mention of legal action, lawyers, attorneys, courts, formal consumer forums, or regulatory bodies (such as consumer protection agencies or trade commissions).
* **Routing Destination:** `legal_desk` (Kartway Legal and Compliance Department)
* **SLA for Handover:** Within 30 minutes. Agents must not reply to the customer prior to routing.

### 14.2.5 `product_safety`
* **Condition:** The customer mentions any physical harm, personal injury, or a product-safety hazard, specifically including but not limited to: overheating, smoking, electrical sparks, fire, chemical leakage, structural collapse, or choking hazards.
* **Routing Destination:** `safety_desk` (Kartway Product Safety and Quality Assurance Desk)
* **SLA for Handover:** Immediate emergency routing (under 60 seconds).

### 14.2.6 `refund_above_auto_cap`
* **Condition:** The requested refund or replacement has a total calculated value exceeding 2,000 rupees (₹2,000.00).
* **Routing Destination:** `refund_approver` (Finance Escalations Queue)
* **SLA for Handover:** Within 4 hours during standard business hours (08:00–20:00 IST).

### 14.2.7 `account_under_review`
* **Condition:** A refund, return, or replacement request is initiated from an account that is currently flagged or under formal review for return abuse, policy violations, or fraudulent activity within the Kartway Risk Database.
* **Routing Destination:** `fraud_desk` (Kartway Risk and Fraud Operations Desk)
* **SLA for Handover:** Within 2 hours.

### 14.2.8 `delivery_dispute`
* **Condition:** The assigned courier tracking system displays the parcel status as "Delivered", but the customer asserts that the parcel never arrived.
* **Routing Destination:** `agent` (Tier-1 General Support Queue, restricted to Courier Investigation workflow)
* **SLA for Handover:** Within 4 hours to initiate a carrier investigation ticket.

---

## 14.3 Communication Standards and Liability Prohibition

### 14.3.1 Required Tone Guidance
All human agents taking over an escalated interaction must maintain a neutral, empathetic, and professional register. Agents must acknowledge the customer's frustration or specific situation without validating subjective grievances as corporate fault. Responses must be concise, factual, and focused on the procedural resolution steps outlined in internal workflows.

### 14.3.2 Prohibition on Liability Admissions
Support assistants and human agents are strictly prohibited from apologising in any manner that admits legal or operational liability on behalf of Kartway. 

* **Permitted phrasing:** "I am sorry for the frustration this situation has caused you," or "I regret that your experience did not meet our standard."
* **Prohibited phrasing:** "I am sorry that Kartway lost your package," "We admit our courier made a mistake," or "It is our fault the product failed." 

Any statement accepting direct blame, fault, or legal responsibility for damages, delivery failures, or product defects without prior authorization from `legal_desk` constitutes a severe policy violation subject to internal disciplinary review.
