# Shipping, Delivery and Lost-Parcel Policy

# KARTWAY OPERATIONS POLICY HANDBOOK
## MODULE 400: SHIPPING, TRANSIT DISPUTES, AND FULFILMENT SERVICE LEVELS
**Owner:** Logistical Compliance & Customer Operations  
**Applies To:** All Tier-1, Tier-2, and Escalated Support Agents  

---

### 4.1 Delivery Service Level Agreements (SLAs)
4.1.1 The delivery promise is calculated from the exact calendar date of order placement (`order_date`). fulfilment tiers and destination classifications are governed by strict business day thresholds. Agents shall reference the matrix below for all delivery SLA determinations.

| Fulfillment Tier | Destination Type | Delivery SLA (from Order Date) |
| :--- | :--- | :--- |
| Express | Metro | 2 Days |
| Express | Non-Metro | 3 Days |
| Standard | Metro | 5 Days |
| Standard | Non-Metro | 7 Days |
| Economy | Metro | 10 Days |
| Economy | Non-Metro | 10 Days |

4.1.2 Destination classification (Metro versus Non-Metro) is hardcoded into the Kartway shipping engine based on the destination pincode database. Agents are prohibited from manually overriding metro classifications.

---

### 4.2 Delayed Shipments and Compensation Ladder
4.2.1 **Definition:** A shipment is officially classified as delayed when the actual carrier delivery timestamp occurs after the promised delivery date defined in Section 4.1.1.

4.2.2 **Compensation Structure:** When a customer experiences a delayed delivery and chooses to keep the item, agents shall apply goodwill credits to the Kartway wallet based strictly on the following lateness tiers:
*   **1 to 2 days late:** Standard operational apology issued via email; zero (0) rupee credit.
*   **3 to 5 days late:** One hundred (100) rupee credit issued to the Kartway wallet.
*   **6 or more days late:** Two hundred fifty (250) rupee credit issued to the Kartway wallet.

4.2.3 Wallet credits issued under Section 4.2.2 must be processed through the internal billing tool using code `WGH-DEL-DELAY` and are non-transferable.

---

### 4.3 Lost-in-Transit Declaration
4.3.1 A shipped order that remains undelivered exactly ten (10) calendar days after its promised delivery date shall be automatically declared lost in transit by the system.

4.3.2 Upon a lost-in-transit declaration, the customer is entitled to select one of two resolution paths:
1. A full refund to the original payment source.
2. A direct replacement order of identical items.

4.3.3 The chosen resolution (refund or replacement) must be authorized by the support agent in accordance with the standard financial authorization tier limits assigned to their agent profile.

---

### 4.4 Disputed Delivery Scans ("Delivered Not Received")
4.4.1 If a courier tracking scan marks an order as "Delivered" but the customer disputes receipt, the customer must report the discrepancy to Kartway support within exactly three (3) calendar days of the disputed delivery scan timestamp.

4.4.2 Automated assistants (chatbots) are strictly prohibited from resolving delivery dispute claims. 

4.4.3 Upon receiving a valid dispute within the 3-day window, a human support agent must manually open a formal carrier investigation. The investigation lifecycle and resolution must conclude within exactly five (5) business days from opening.

4.4.4 Carrier investigation SLAs for receiving a formal response to a claim are strictly bound by the partner SLA schedule below:
*   **Bluedart:** 2 business days
*   **Delhivery:** 3 business days
*   **Ecom Express:** 3 business days
*   **IndiaPost:** 5 business days
*   **XpressBees:** 4 business days

---

### 4.5 Address-Change Cutoffs
4.5.1 The delivery address for an existing order can be modified exclusively while the order status remains in the `placed` state.

4.5.2 Once an order transitions out of the `placed` state (i.e., enters `processing`, `picked`, or `shipped`), address modifications are permanently locked out. Agents shall not process address change requests for orders in transit under any circumstances.
