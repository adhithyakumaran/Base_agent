# Endless Aisle UAT — Discovery + Recording Approval Checklist

Updated: `2026-09-01T18:10:28Z`

## Sources merged

| Source | Role |
|---|---|
| Automated Playwright crawl | Baseline page map / KB |
| Browser recording #1 (~5m) | Extra modules, reports, filters |
| Browser recording #2 (~35m) | Login + product browse/detail + find-price + stock + best deal |

- KB documents now: **64** (`discovery/uat_ea/kb/`)
- Candidate expectations: **22**
- Distinct pages from recordings: **43**

## New pages from your recordings (high signal)

- `ea/customer-wish-list1` — `/ords/r/tjdcom/ea/customer-wish-list1` (hits=3)
- `ea/dashboard-tile` — `/ords/r/tjdcom/ea/dashboard-tile` (hits=1)
- `ea/discount-product-details-all-store` — `/ords/r/tjdcom/ea/discount-product-details-all-store` (hits=3)
- `ea/estimation-slip` — `/ords/r/tjdcom/ea/estimation-slip` (hits=2)
- `ea/find-price` — `/ords/r/tjdcom/ea/find-price` (hits=2)
- `ea/gold-coin-stock-visibility` — `/ords/r/tjdcom/ea/gold-coin-stock-visibility` (hits=1)
- `ea/kvi-fmc-lcg` — `/ords/r/tjdcom/ea/kvi-fmc-lcg` (hits=1)
- `ea/product-detail` — `/ords/r/tjdcom/ea/product-detail` (hits=11)
- `ea/smart-image-search1` — `/ords/r/tjdcom/ea/smart-image-search1` (hits=1)
- `ea/solitaire-uin-search` — `/ords/r/tjdcom/ea/solitaire-uin-search` (hits=1)
- `ea/standard-product-search` — `/ords/r/tjdcom/ea/standard-product-search` (hits=12)
- `ea/wedding-trousseau` — `/ords/r/tjdcom/ea/wedding-trousseau` (hits=4)
- `ea/wedding-trousseau-details1` — `/ords/r/tjdcom/ea/wedding-trousseau-details1` (hits=6)
- `ea1/101` — `/ords/r/tjdcom/ea1/101` (hits=1)
- `ea1/102` — `/ords/r/tjdcom/ea1/102` (hits=1)
- `ea1/200` — `/ords/r/tjdcom/ea1/200` (hits=1)
- `ea1/22` — `/ords/r/tjdcom/ea1/22` (hits=2)
- `ea1/47` — `/ords/r/tjdcom/ea1/47` (hits=2)
- `ea1/51` — `/ords/r/tjdcom/ea1/51` (hits=6)
- `ea1/57` — `/ords/r/tjdcom/ea1/57` (hits=1)
- `ea1/61` — `/ords/r/tjdcom/ea1/61` (hits=1)
- `ea1/63` — `/ords/r/tjdcom/ea1/63` (hits=4)
- `ea1/estimation-slip` — `/ords/r/tjdcom/ea1/estimation-slip` (hits=2)
- `ea1/product-detail` — `/ords/r/tjdcom/ea1/product-detail` (hits=1)

## Candidate Ground Truth — mark each

Only **APPROVE** becomes authoritative GT.

### 1. `ce.auth.login`
- Subject: `auth.login`
- Expected: `true`
- Why: Valid UAT user BALA reached /ea/home.
- Question: Approve successful login with valid store-user credentials as GT for UAT?
- Decision: [ ] APPROVE  [ ] EDIT  [ ] REJECT

### 2. `ce.home.modules_visible`
- Subject: `home.modules`
- Expected: `["All Products", "Item Search", "Rivaah", "Customer Order", "Best Deal", "Smart Image Search", "Find Price"]`
- Why: These modules were visible as home headings for BALA.
- Question: Are these home modules required for this role/store? Edit list before approve if needed.
- Decision: [ ] APPROVE  [ ] EDIT  [ ] REJECT

### 3. `ce.page.select_category.reachable`
- Subject: `page.select-category.reachable`
- Expected: `true`
- Why: All Products navigates to select-category.
- Question: Must store users reach All Products / category selection?
- Decision: [ ] APPROVE  [ ] EDIT  [ ] REJECT

### 4. `ce.item_search.sku_field`
- Subject: `item_search.sku_or_qr`
- Expected: `{"item": "P6_SKU", "actions": ["Scan", "Search"]}`
- Why: Item Search exposes SKU/QR field with Scan and Search.
- Question: Is item-code/QR search required for sanity?
- Decision: [ ] APPROVE  [ ] EDIT  [ ] REJECT

### 5. `ce.item_search.nap_stock_message`
- Subject: `item_search.nap_stock_booking_notice`
- Expected: `"Booking of NAP Stock is available through the NAP System"`
- Why: Observed advisory text on Item Search; likely informational not a defect.
- Question: Is the NAP message expected informational text?
- Decision: [ ] APPROVE  [ ] EDIT  [ ] REJECT

### 6. `ce.store.context_visible`
- Subject: `session.store_context`
- Expected: `true`
- Why: Header showed Store: Chennai - Anna Nagar (ABO) - L2.
- Question: Must store context be visible after login?
- Decision: [ ] APPROVE  [ ] EDIT  [ ] REJECT

### 7. `ce.rivaah.reachable`
- Subject: `page.rivaah.reachable`
- Expected: `true`
- Why: Rivaah module reachable from home.
- Question: Is Rivaah in scope for sanity?
- Decision: [ ] APPROVE  [ ] EDIT  [ ] REJECT

### 8. `ce.product_catalogue.reachable`
- Subject: `page.product-catalogue.reachable`
- Expected: `true`
- Why: Product Catalogue page reached.
- Question: Is Product Catalogue required in sanity?
- Decision: [ ] APPROVE  [ ] EDIT  [ ] REJECT

### 9. `ce.best_deal.reachable`
- Subject: `page.product-discount.reachable`
- Expected: `true`
- Why: Best Deal / product-discount reached.
- Question: Is Best Deal required in sanity?
- Decision: [ ] APPROVE  [ ] EDIT  [ ] REJECT

### 10. `ce.admin.reachable_for_bala`
- Subject: `page.administration.reachable`
- Expected: `"UNKNOWN_NEEDS_POLICY"`
- Why: Administration was reachable for BALA. Confirm if intended.
- Question: Should BALA open Administration? If NO, approve inverse GT (forbidden) for Security.
- Decision: [ ] APPROVE  [ ] EDIT  [ ] REJECT

### 11. `ce.manual_invoice.reachable`
- Subject: `page.manual-bills-book.reachable`
- Expected: `true`
- Why: Manual Invoice / manual-bills-book reached.
- Question: Is Manual Invoice in QA scope for BALA?
- Decision: [ ] APPROVE  [ ] EDIT  [ ] REJECT

### 12. `ce.reports.reachable`
- Subject: `page.51.reachable`
- Expected: `true`
- Why: Reports page alias 51 reached.
- Question: Are Reports in sanity scope?
- Decision: [ ] APPROVE  [ ] EDIT  [ ] REJECT

### 13. `ce.flow.standard_product_browse`
- Subject: `flow.standard_product_browse`
- Expected: `true`
- Why: Recording shows Home→All Products→category→standard-product-search→product-detail→Back to Products.
- Question: Approve this as a sanity golden path?
- Decision: [ ] APPROVE  [ ] EDIT  [ ] REJECT

### 14. `ce.page.product_detail.reachable`
- Subject: `page.product-detail.reachable`
- Expected: `true`
- Why: product-detail visited repeatedly from gallery clicks.
- Question: Must product detail open from product cards?
- Decision: [ ] APPROVE  [ ] EDIT  [ ] REJECT

### 15. `ce.page.standard_product_search.reachable`
- Subject: `page.standard-product-search.reachable`
- Expected: `true`
- Why: Core browse page after category selection.
- Question: Is standard-product-search required in sanity?
- Decision: [ ] APPROVE  [ ] EDIT  [ ] REJECT

### 16. `ce.product_detail.size_variants`
- Subject: `product_detail.size_variants`
- Expected: `true`
- Why: Size Variants dialog used with values like 12.8 / 44 / WOMEN.
- Question: Should size-variant selection be part of product detail GT when variants exist?
- Decision: [ ] APPROVE  [ ] EDIT  [ ] REJECT

### 17. `ce.find_price.fields`
- Subject: `find_price.fields_present`
- Expected: `["P31_ITEM", "P31_LOTNO"]`
- Why: Find Price page used item + lot fields in recording.
- Question: Approve Find Price field contract as GT?
- Decision: [ ] APPROVE  [ ] EDIT  [ ] REJECT

### 18. `ce.stock_visibility.p47_sku`
- Subject: `stock_visibility.sku_search`
- Expected: `{"item": "P47_SKU"}`
- Why: Stock Visibility (ea1/47) used P47_SKU search.
- Question: Is Stock Visibility SKU search in scope?
- Decision: [ ] APPROVE  [ ] EDIT  [ ] REJECT

### 19. `ce.message.gold_rate_may_change`
- Subject: `best_deal.gold_rate_disclaimer`
- Expected: `"The Gold rate may change depending on the actual rate during the time of booking"`
- Why: Observed on discount product details; likely informational.
- Question: Is this disclaimer expected (PASS if present), not an error?
- Decision: [ ] APPROVE  [ ] EDIT  [ ] REJECT

### 20. `ce.flow.rivaah_trousseau`
- Subject: `flow.rivaah_trousseau`
- Expected: `true`
- Why: Rivaah→wedding-trousseau→details observed in both recordings.
- Question: Include Rivaah trousseau path in sanity?
- Decision: [ ] APPROVE  [ ] EDIT  [ ] REJECT

### 21. `ce.reports.order_status`
- Subject: `reports.order_status.reachable`
- Expected: `true`
- Why: Reports→Order Status navigated to ea1/200.
- Question: Are report submenus in QA scope for BALA?
- Decision: [ ] APPROVE  [ ] EDIT  [ ] REJECT

### 22. `ce.cross_app.ea1_linked`
- Subject: `nav.ea_to_ea1`
- Expected: `true`
- Why: Many modules open under app alias ea1 (reports, stock, manual bills, collections).
- Question: Treat ea1 as in-scope companion app for Endless Aisle QA?
- Decision: [ ] APPROVE  [ ] EDIT  [ ] REJECT

## What you should still record (optional)

- **Customer Order** happy path (open order / add customer) — still thin
- One **failed SKU search** (bad code → expected message)
- One **HAR** for standard-product-search if possible

## Not waste

Your recordings added product-detail, size variants, find-price fields, stock visibility, discount details, and ea1 report links that crawl alone did not fully cover.
