# WF005_unknown_order_then_email

_What this checks: Missing-order handling: asks for another identifier, then resumes with the email_

**Request:** Where is order ORD-9999?

**Selected Workflow:** WF005 - Customer Order Status
**Routing:** Claude tool calling (confidence: high) - User asks for the status/location of a specific order ID.
**Status:** ✅ Completed

**Conversation:**
> **User:** Where is order ORD-9999?
> **Assistant:** I couldn't find any order for **ORD-9999**. Could you share another order ID (e.g. ORD-1001) or the email address used for the order?
> **User:** Hmm, then please check jane.doe@example.com

### Steps Executed
1. ✅ **Validate identifier** [`validate_identifier`] - Valid email: jane.doe@example.com
2. ✅ **Search order data** [`search_orders`] - Found 2 order(s)
3. ✅ **Retrieve order status** [`get_order_status`] - ORD-1001: Shipped, ORD-1002: Processing
4. ✅ **Retrieve shipment information** [`track_shipments`] - ORD-1001: In transit, ORD-1002: Not shipped yet
5. ✅ **Summarize current status** [`summarize_order_status`] - Summarised 2 order(s)

### Result
I found **2 orders** for jane.doe@example.com.
- **ORD-1001** (placed 2026-10-09, total **$123.00**) has shipped and is in transit with UPS (tracking 1Z999AA10123456784). It includes a Wool Blend Sweater and 2 Baseball Caps. The estimated delivery is 2026-10-16, and the latest update (2026-10-14 07:05) says it arrived at the regional hub in Chicago, IL.
- **ORD-1002** (placed 2026-10-13, total **$95.00**) is still processing and hasn't shipped yet, so there's no tracking information. It contains a Merino Wool Turtleneck.

#### Order status

| order_id | customer | order_date | order_status | items | order_total | shipment_status | carrier | tracking_number | estimated_delivery | latest_update |
|---|---|---|---|---|---|---|---|---|---|---|
| ORD-1001 | Jane Doe | 2026-10-09 | Shipped | 1x Wool Blend Sweater (SKU-1004); 2x Baseball Cap (SKU-1013) | 123 | In transit | UPS | 1Z999AA10123456784 | 2026-10-16 | 2026-10-14 07:05 - Arrived at regional hub (Chicago, IL) |
| ORD-1002 | Jane Doe | 2026-10-13 | Processing | 1x Merino Wool Turtleneck (SKU-2001) | 95 | Not shipped yet |  |  |  |  |

_Run run-20261014-185047-59fd47 - 6.4s, LLM calls: 3, tokens: 6554 in / 376 out_
