# WF005_invalid_identifier

_What this checks: Identifier validation: '12345' is not a valid order ID/email_

**Request:** What's the status of my order 12345?

**Selected Workflow:** WF005 - Customer Order Status
**Routing:** Claude tool calling (confidence: high) - User is asking for the status of a specific order.
**Status:** ✅ Completed

**Conversation:**
> **User:** What's the status of my order 12345?
> **Assistant:** '12345' doesn't look like a valid order id or email. Please share your order ID (e.g. ORD-1001) or the email address used for the order.
> **User:** ORD-1005

### Steps Executed
1. ✅ **Validate identifier** [`validate_identifier`] - Valid order id: ORD-1005
2. ✅ **Search order data** [`search_orders`] - Found 1 order(s)
3. ✅ **Retrieve order status** [`get_order_status`] - ORD-1005: Shipped
4. ✅ **Retrieve shipment information** [`track_shipments`] - ORD-1005: Delayed
5. ✅ **Summarize current status** [`summarize_order_status`] - Summarised 1 order(s)

### Result
Order **ORD-1005** (placed 2026-10-06 by Sam Lee) has a status of **Shipped**, but its shipment is currently **Delayed**. The latest update (2026-10-11 16:45) reports a customs clearance delay in Cincinnati, OH. It's shipping via DHL (tracking number JD014600006281234567) with an estimated delivery of **2026-10-17**. The order contains 1x Hiking Boots and 3x Ankle Socks (3-Pack), with a total of **$165.00**.

#### Order status

| order_id | customer | order_date | order_status | items | order_total | shipment_status | carrier | tracking_number | estimated_delivery | latest_update |
|---|---|---|---|---|---|---|---|---|---|---|
| ORD-1005 | Sam Lee | 2026-10-06 | Shipped | 1x Hiking Boots (SKU-1008); 3x Ankle Socks (3-Pack) (SKU-1014) | 165 | Delayed | DHL | JD014600006281234567 | 2026-10-17 | 2026-10-11 16:45 - Customs clearance delay (Cincinnati, OH) |

_Run run-20261014-185053-fc6ad6 - 5.7s, LLM calls: 3, tokens: 6367 in / 314 out_
