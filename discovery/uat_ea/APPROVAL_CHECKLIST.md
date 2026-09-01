# Endless Aisle UAT — Discovery Results & Approval Checklist

Generated: `2026-09-01T15:45:18Z`

## Who does what

| Task | Who |
|---|---|
| Login, crawl, extract pages/components/flows into **KB candidates** | **Agent (done this pass)** |
| Propose **candidate expectations** | **Agent (done)** |
| Approve / edit / reject candidates → real **Ground Truth** | **You / teammate (required, ~15–30 min)** |
| Write full client test cases / continuous SME | **Not required** |

## What was extracted

- App: **Endless Aisle** (APEX **1002**, workspace **tjdcom**, alias **ea**)
- User **BALA** logs in → `/ords/r/tjdcom/ea/home`
- Store context: **Chennai - Anna Nagar (ABO) - L2**
- KB documents: **14** → `discovery/uat_ea/kb/`
- Candidate expectations: **12** → `discovery/uat_ea/candidate_gt/candidates.json`

### Home modules observed

- All Products
- Item Search
- Rivaah
- Customer Order
- Best Deal
- Smart Image Search
- Find Price
- Estimation Slip
- Solitaire UIN
- Crown Eye
- Gold Coin Stock Visibility
- Stock Visibility
- My Store Stock
- Open IBT Action - Urgent
- Store Orders
- Report
- Customer Wishlist
- Solitaire Products
- New Collections
- High Value Studded

### Pages reached

- `administration` — Administration — `https://dev-ea.titanrts.com/ords/r/tjdcom/ea/administration`
- `home` — Endless Aisle — `https://dev-ea.titanrts.com/ords/r/tjdcom/ea/home`
- `product-catalogue` — Product Catalogue — `https://dev-ea.titanrts.com/ords/r/tjdcom/ea/product-catalogue`
- `product-detail-item-search` — Product Search — `https://dev-ea.titanrts.com/ords/r/tjdcom/ea/product-detail-item-search`
- `product-discount` — Product Discount — `https://dev-ea.titanrts.com/ords/r/tjdcom/ea/product-discount`
- `rivaah` — Rivaah — `https://dev-ea.titanrts.com/ords/r/tjdcom/ea/rivaah`
- `select-category` — Select Category — `https://dev-ea.titanrts.com/ords/r/tjdcom/ea/select-category`

## Candidate Ground Truth — mark each

Only **APPROVE** items become authoritative GT for PASS/FAIL.

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

## Limits of this pass

- URL + credentials discovery only (no APEX metadata DB).
- Customer Order / cart checkout not deeply exercised yet.
- Some dialogs (Customer select / ORSO) need a careful second pass.
- Administration reachable for BALA — confirm before security GT.

## After you approve

1. I convert APPROVED rows into `ground_truth/*.yaml`.
2. I run a deeper Customer Order / product-detail pass.
3. Sanity checks against approved GT can run with **0 LLM** on those subjects.
