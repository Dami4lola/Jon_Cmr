# Handyman Job Estimator — Rebuild Specification

**Purpose of this document:** a complete, implementation-level description of the job estimator system built in this project, written so another developer could reproduce it from scratch without access to the original source. It covers two related but independent deliverables:

1. **Standalone Estimator Tool** — a single-file HTML/JS app for internal use, not tied to any backend.
2. **OBATEK Integration** — the same pricing logic wired into the existing OBATEK Worker Portal (FastAPI + React/TypeScript), adding a public customer-facing quick-quote page and a manager-facing detailed calculator.

Both implementations share the same underlying business pricing rules but are built with different goals: the standalone tool is a zero-dependency offline calculator; the OBATEK integration is a multi-user web feature backed by a real database, live Google Maps distance lookups, and role-based access control.

---

## 1. Business Pricing Rules (source of truth for both builds)

These rules were supplied by the business owner and drive every calculation in both systems.

| Rule | Value |
|---|---|
| Standard labour rate | $80.00 / hour / technician |
| Red Seal trade rate (plumbing, electrical) | $100.00 / hour / technician |
| Minimum billable time per job | 4 hours |
| Travel rate | $1.50 / km / technician, round trip, measured from the business's fixed location to the customer address |
| Admin fee | $50.00, charged once per invoice (invoices are batched weekly) |
| Standard working day | 7 hours (reference value; not used directly in any formula) |
| Materials | Costed before tax; tax is applied once, to the full invoice total, at the very end — not per line item |
| Fuel for tools/equipment | Billed out as its own line item |
| Heavy equipment (mini excavator, tractor, skid steer) | $120.00 / hour |
| Owned rental equipment (e.g. wood chipper) | $150.00 / day |
| Scaffolding | Rate set per job, taken from whatever the work estimate specifies (no fixed default) |
| Outside/rented equipment | Priced at whatever the rental company ("rental village") charges — a pass-through cost, with an optional markup percentage |
| Tax | 13% (Ontario HST) by default, editable |

A later requirement added a **customer-facing "quick quote"** mode: given only a job type, an address, and the square footage of the work area, produce an instant rough estimate without any human intervention. This required inventing area-based heuristics (hours per square foot, materials cost per square foot) per job type, since the rules above only cover hourly/itemized billing. Those heuristics are placeholders — see §5.

---

## 2. Standalone Estimator Tool

**File:** a single self-contained `.html` file (`handyman_estimator.html`), opened directly in a browser. No build step, no server, no external runtime dependency except the browser itself.

### 2.1 Tech approach

Plain HTML + CSS + vanilla JavaScript (ES6+), no frameworks, no bundler. Chosen deliberately so the business owner can open the file locally, edit it if needed, and never depend on hosting or a build pipeline. All state is kept in in-memory JS objects/arrays and mirrored to `localStorage` for persistence between sessions (this is a real standalone webpage opened in a real browser, not a sandboxed "artifact" — `localStorage` is fully appropriate here).

### 2.2 Data model

```js
settings = {
  bizName, bizAddr,                 // business identity, shown on the printable header
  stdRate: 80, redRate: 100,
  minHours: 4, workDay: 7,
  kmRate: 1.50, adminFee: 50,
  heavyRate: 120, ownedRentalRate: 150,
  taxRate: 13,
  hdProvider: "none" | "bigbox" | "serpapi",   // material-pricing plug-in, see §2.5
  hdKey: ""
}
// persisted to localStorage["hd_estimator_settings"]

priceList = [ { name, unit, cost, source } ]
// editable materials price list, persisted to localStorage["hd_estimator_pricelist"]
// seeded with ~24 common handyman materials at placeholder prices (drywall, studs,
// paint, PVC/copper pipe, wire nuts, outlets, deck boards, concrete mix, etc.)

laborRows    = [ { id, trade: "standard"|"redseal"|"custom", customRate, techs, hours, applyMin } ]
travelRows   = [ { id, desc, techs, km, rate } ]
equipRows    = [ { id, category: "heavy"|"ownedRental"|"scaffolding"|"rentalVillage"|"fuel",
                    desc, rate, unit, qty, markup } ]
materialRows = [ { id, name, source, qty, unitCost } ]

// Saved estimates keyed by "CustomerName - Date", persisted to
// localStorage["hd_estimator_saved"]
```

### 2.3 Calculation formulas

```
laborLineTotal(row)   = rate(row) * techs * (applyMin ? max(hours, minHours) : hours)
                         where rate(row) = stdRate if trade=="standard"
                                          redRate if trade=="redseal"
                                          customRate if trade=="custom"

travelLineTotal(row)  = techs * km * rate

equipLineTotal(row)   = rate * qty * (1 + markup/100)

materialLineTotal(row)= qty * unitCost

laborTotal     = sum(laborLineTotal)
travelTotal    = sum(travelLineTotal)
equipTotal     = sum(equipLineTotal)
materialsTotal = sum(materialLineTotal)
adminAmt       = includeAdmin ? adminFee : 0

subtotal   = laborTotal + travelTotal + equipTotal + materialsTotal + adminAmt
tax        = subtotal * (taxRate / 100)
grandTotal = subtotal + tax
```

The 4-hour minimum is applied **per labor line**, individually toggleable via a checkbox on each row (a design choice — the business rule doesn't specify whether it's per-tech-line or per-whole-job, so this was implemented as the more flexible per-line option and flagged to the business owner).

### 2.4 UI sections

Job Information (customer name/address/description/date) → Labor (add/remove rows, trade dropdown with live rate display) → Travel (round-trip km entered manually, since there's no mapping API key in this standalone context) → Equipment & Fuel (five quick-add buttons pre-filling the category defaults: Heavy Equipment $120/hr, Owned Rental $150/day, Scaffolding — blank/custom, Outside Rental — blank/custom with markup%, Fuel — flat charge) → Materials (dropdown sourced from the editable price list, or "Custom" free-entry) → Admin Fee (checkbox + editable amount) → Summary (live-updating breakdown table) → Save/Load estimate (dropdown of saved estimates by customer+date) → Print/Export (browser print stylesheet that hides all interactive controls and renders a clean invoice-style layout).

### 2.5 Materials pricing / Home Depot integration

Important finding to carry over: **Home Depot has no free public API.** Live pricing is only available through paid third-party scraper services (e.g. BigBox API, SerpApi), roughly $15+/month. The tool was built around this constraint:

- Default, zero-cost path: a fully editable local price list (seeded with placeholder prices) that works entirely offline.
- Optional "plug-in slot": a settings panel where the user can select a provider (BigBox API / SerpApi) and paste an API key. A "Search Home Depot" button attempts a `fetch()` call against the provider's REST endpoint. This is explicitly documented in the UI as likely to hit CORS restrictions when called directly from a browser (these are typically server-side APIs); a small backend proxy would be needed for a production version of this live-lookup path.

---

## 3. OBATEK Integration

This half of the project takes the identical pricing rules and threads them into an existing production application — the **OBATEK Worker Portal** — rather than building a second standalone tool.

### 3.1 Existing app context (must exist before this feature can be added)

Stack: FastAPI 0.109.2 + SQLModel 0.0.14 (SQLAlchemy + Pydantic) + PostgreSQL/SQLite backend; React 18 + TypeScript 5.3 + Vite 5 + Tailwind 3.4 + TanStack React Query 5 + Zustand + Axios frontend. JWT auth with `worker` / `manager` / `admin` roles.

Critically, **the core pricing constants already existed** in `backend/app/api/invoices.py`, used for generating real invoices from logged timesheets:

```python
DEFAULT_KM_RATE = Decimal("1.50")
MINIMUM_HOURS   = Decimal("4.0")
LABOUR_RATE     = Decimal("80.00")
REDSEAL_RATE    = Decimal("100.00")
HST_RATE        = Decimal("0.13")
```

The `Job` model already had a single `estimate_amount: Decimal | None` field that a manager filled in by hand when creating a job — there was no calculator behind it. The app also already had a working Google Maps Distance Matrix integration (`backend/app/services/distance.py`, function `calculate_distance(destination) -> Decimal | None`, round-trip km from a configured `OFFICE_ADDRESS` env var, ceiling-rounded), used for the existing internal job/invoice distance features.

**Design decision:** reuse `LABOUR_RATE`, `REDSEAL_RATE`, `MINIMUM_HOURS`, `DEFAULT_KM_RATE`, `HST_RATE` and `calculate_distance()` directly by importing them into the new module, rather than redefining them — avoids drift between existing invoicing and the new estimator, and required zero changes to the existing, already-tested `invoices.py` file.

There's also a pre-existing generic key/value settings table used for one existing tunable (`invoice_start_number`):

```python
class AppSettings(SQLModel, table=True):
    __tablename__ = "app_settings"
    key: str = Field(primary_key=True, max_length=100)
    value: str = Field(max_length=500)
```

This was reused as the storage mechanism for the new estimator's tunable heuristics (see §3.3), rather than adding new dedicated columns/tables — no migration required.

### 3.2 New backend files

**`backend/app/schemas/estimate.py`** — new Pydantic schemas:

```python
class JobTypeOption(BaseModel):           # value/label pair for the public dropdown
    value: str
    label: str

class QuickQuoteRequest(BaseModel):
    job_type: str = Field(default="general", max_length=50)
    address: str = Field(..., min_length=3, max_length=300)
    area_sqft: Decimal = Field(..., gt=0, le=100000)

class QuickQuoteResponse(BaseModel):
    job_type: str
    job_type_label: str
    address: str
    area_sqft: Decimal
    distance_km: Decimal | None
    estimated_hours: Decimal
    labour_amount: Decimal
    travel_amount: Decimal
    materials_amount: Decimal
    admin_fee: Decimal
    subtotal: Decimal
    hst_amount: Decimal
    total: Decimal
    disclaimer: str

class JobTypeRate(BaseModel):             # one job type's tunable heuristic
    job_type: str
    label: str
    hours_per_sqft: Decimal
    materials_per_sqft: Decimal

class QuickQuoteRatesResponse(BaseModel): # manager view of everything driving the quote
    labour_rate: Decimal
    redseal_rate: Decimal
    minimum_hours: Decimal
    km_rate: Decimal
    hst_rate: Decimal
    admin_fee: Decimal
    job_types: list[JobTypeRate]

class JobTypeRateUpdate(BaseModel):
    hours_per_sqft: Decimal = Field(..., gt=0, le=10)
    materials_per_sqft: Decimal = Field(..., ge=0, le=1000)

class AdminFeeUpdate(BaseModel):
    admin_fee: Decimal = Field(..., ge=0, le=10000)

class DistancePreviewRequest(BaseModel):
    address: str = Field(..., min_length=3, max_length=300)

class DistancePreviewResponse(BaseModel):
    distance_km: Decimal | None
    address: str
```

**`backend/app/api/estimates.py`** — new router, mounted at `/api/estimates` in `main.py`:

```python
app.include_router(estimates.router, prefix="/api/estimates", tags=["Estimates"])
```

Job type defaults (the area-based heuristics — see §5 for why these numbers are placeholders):

```python
JOB_TYPE_DEFAULTS: dict[str, dict] = {
    "general":  {"label": "General / Other",              "hours_per_sqft": Decimal("0.02"),  "materials_per_sqft": Decimal("3.00")},
    "painting": {"label": "Painting (Interior/Exterior)",  "hours_per_sqft": Decimal("0.008"), "materials_per_sqft": Decimal("0.75")},
    "drywall":  {"label": "Drywall Install/Repair",        "hours_per_sqft": Decimal("0.03"),  "materials_per_sqft": Decimal("1.50")},
    "flooring": {"label": "Flooring Install",              "hours_per_sqft": Decimal("0.04"),  "materials_per_sqft": Decimal("4.00")},
}
DEFAULT_ADMIN_FEE = Decimal("50.00")
```

Red Seal trades (plumbing, electrical) are **deliberately excluded** from the quick-quote job type list — their scope varies too much job-to-job for a square-footage formula to produce an honest number, so those still require a manual estimate via the calculator described in §3.4.

Each job type's `hours_per_sqft` / `materials_per_sqft` are stored per-type in `AppSettings` using composite keys, falling back to the hardcoded defaults above when unset:

```python
def _setting_keys(job_type: str) -> tuple[str, str]:
    return f"quick_quote_hours_per_sqft__{job_type}", f"quick_quote_materials_per_sqft__{job_type}"
```

The admin fee is a single shared value stored under key `quick_quote_admin_fee`.

The dollar-amount math lives in a **pure function with no DB or HTTP dependency**, so it's independently unit-testable — mirrors the pattern already used in `invoices.py` for `_round_hours`:

```python
def calculate_quick_estimate(
    area_sqft, distance_km, hours_per_sqft, materials_per_sqft, admin_fee,
    labour_rate=LABOUR_RATE, km_rate=DEFAULT_KM_RATE, hst_rate=HST_RATE, minimum_hours=MINIMUM_HOURS,
) -> dict:
    raw_hours = float(area_sqft) * float(hours_per_sqft)
    rounded_hours = round to nearest 0.25              # same rounding approach as real timesheets
    estimated_hours = max(rounded_hours, minimum_hours)

    labour_amount = estimated_hours * labour_rate
    travel_amount = distance_km * km_rate  if distance_km is not None  else 0.00
    materials_amount = area_sqft * materials_per_sqft
    # admin_fee passed through as-is

    subtotal = labour_amount + travel_amount + materials_amount + admin_fee
    hst_amount = subtotal * hst_rate
    total = subtotal + hst_amount
    # every dollar amount is Decimal-quantized to 0.01 with ROUND_HALF_UP
```

Endpoints:

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/job-types` | none (public) | Returns `[{value, label}]` for every entry in `JOB_TYPE_DEFAULTS` — powers the public dropdown |
| POST | `/quick-quote` | none (public) | Body: `QuickQuoteRequest`. Looks up the job type's rates, calls `calculate_distance(address)`, runs `calculate_quick_estimate`, returns `QuickQuoteResponse` with a fixed disclaimer string. Unknown `job_type` values silently fall back to `"general"` rather than erroring. |
| GET | `/quick-quote-rates` | manager | Returns the full `QuickQuoteRatesResponse` — core invoicing rates plus every job type's current (possibly overridden) heuristic |
| PUT | `/quick-quote-rates/{job_type}` | manager | Body: `JobTypeRateUpdate`. 404s on an unknown job type. Persists to `AppSettings`. |
| PUT | `/quick-quote-admin-fee` | manager | Body: `AdminFeeUpdate`. Updates the shared admin fee. |
| POST | `/distance-preview` | manager | Body: `{address}`. Wraps `calculate_distance()` so a manager can check round-trip km for an address before a `Job` row exists (the existing `/api/jobs/{id}/distance` endpoint requires an already-created job). |

**`backend/tests/test_estimate_calculations.py`** — pure-function tests mirroring the existing `test_invoice_calculations.py` style (no DB/HTTP client): verifies the 4-hour floor, that a missing distance produces a $0 travel line rather than an error, that HST is applied once to the full subtotal, and that every job type in `JOB_TYPE_DEFAULTS` has a distinct, positive rate.

> **Sandbox caveat carried over from the build:** this environment had no network access to install `fastapi`/`sqlmodel`/`pytest`, so these tests were written but only verified indirectly — the exact same arithmetic was re-implemented in a disposable standalone script and run with plain `python3` to confirm the formulas, and every new/edited `.py` file was checked with `python3 -m py_compile` for syntax correctness. **Run the real `pytest` suite before deploying.**

### 3.3 New/changed frontend files

**`frontend/src/types/index.ts`** — added `JobTypeOption`, `QuickQuoteRequest`, `QuickQuoteResponse`, `JobTypeRate`, `QuickQuoteRates`, `JobTypeRateUpdate`, `DistancePreviewResponse` interfaces (all Decimal fields typed as `string` on the frontend, matching this codebase's existing convention for every other money field — see `Invoice`/`InvoicePreview` types).

**`frontend/src/api/estimates.ts`** — thin Axios wrapper, one function per endpoint (`listJobTypes`, `quickQuote`, `getRates`, `updateJobTypeRate`, `updateAdminFee`, `distancePreview`), following the exact pattern of the existing `api/invoices.ts`.

**`frontend/src/pages/GetEstimate.tsx`** — new **public** page (added to the "Public routes" block in `App.tsx` at path `/quote`, outside the `<ProtectedRoute>` wrapper, no login required). Linked from `Welcome.tsx` via a "Get a Free Estimate" button. Behavior:
1. On mount, fetches job types from `GET /estimates/job-types` via React Query (falls back to a hardcoded `[{value:"general", label:"General / Other"}]` if that request hasn't resolved/fails).
2. Form: job-type `<select>`, address text input, area-sqft number input.
3. On submit, calls `POST /estimates/quick-quote` via a `useMutation`.
4. Renders a breakdown card: estimated hours, labour/travel/materials/admin lines, subtotal, HST, bold total, and the disclaimer string returned by the API. If `distance_km` came back `null` (no Google Maps key configured, or the address didn't resolve), the travel line shows "Confirmed at booking" instead of a dollar figure.
5. "Start Over" resets the form.

**`frontend/src/components/EstimateCalculator.tsx`** — new **manager-only** reusable component: a compact, inline version of the standalone tool's line-item calculator (§2), built for use inside the existing Job create/edit forms rather than as its own page. Props: `{ initialAddress?: string; onApply: (total: number) => void; onClose: () => void }`.

- Fetches live core rates via `GET /estimates/quick-quote-rates` (React Query, `retry: false`) so the labour/Red Seal/km/HST rates shown always match the backend truth rather than being hardcoded twice; falls back to the known constants (80/100/4/1.5/0.13/50) while loading.
- Local component state for labor rows, a single travel section (address + techs + a "Look up km" button hitting `POST /estimates/distance-preview`, plus a manual km override field), equipment rows (same five categories as the standalone tool, same default rate pre-fills), material rows, and admin-fee/HST toggles.
- All the same pure formulas as §2.3, computed inline on every render (no memoization needed at this scale).
- "Use This Estimate" calls `onApply(roundedTotal)`; the parent (`ManagerDashboard.tsx`) uses this to set `formData.estimate_amount` / `editFormData.estimate_amount` and closes the panel.

**`frontend/src/pages/ManagerDashboard.tsx`** — minimally modified (this file is ~1900 lines and pre-existing; only additive changes were made): a "Calculate" toggle link was added next to the "Estimate Amount ($)" label in both the Create Job form and the Edit Job form, each controlling its own boolean (`showEstimateCalc` / `showEditEstimateCalc`) and rendering `<EstimateCalculator>` directly below the existing grid of fields, seeded with `initialAddress` from the selected client's address.

**`frontend/src/App.tsx`** — one new route added to the existing public-routes block:
```tsx
<Route path="/quote" element={<GetEstimate />} />
```

### 3.4 Data flow summary

```
Customer (no login)
  → GetEstimate.tsx
    → GET /api/estimates/job-types           (populate dropdown)
    → POST /api/estimates/quick-quote        (address, area_sqft, job_type)
      → calculate_distance(address)          [Google Maps Distance Matrix, existing service]
      → look up AppSettings for that job type, fall back to JOB_TYPE_DEFAULTS
      → calculate_quick_estimate(...)        [pure function]
    ← QuickQuoteResponse (full breakdown + disclaimer)

Manager (logged in, creating/editing a Job)
  → ManagerDashboard.tsx "Calculate" toggle
    → EstimateCalculator.tsx
      → GET /api/estimates/quick-quote-rates (live core rates, for display only)
      → POST /api/estimates/distance-preview (optional, per travel line)
      → all math computed client-side from user-entered rows
    → onApply(total) → formData.estimate_amount → normal Job create/update flow
      (POST /api/jobs/ or PUT /api/jobs/{id}, unchanged, pre-existing endpoints)
```

---

## 4. File Manifest

**Standalone tool**
- `handyman_estimator.html` — everything in one file.

**OBATEK integration — new files**
- `backend/app/schemas/estimate.py`
- `backend/app/api/estimates.py`
- `backend/tests/test_estimate_calculations.py`
- `frontend/src/api/estimates.ts`
- `frontend/src/pages/GetEstimate.tsx`
- `frontend/src/components/EstimateCalculator.tsx`

**OBATEK integration — modified files**
- `backend/app/main.py` (router registration, one import line + one `include_router` line)
- `frontend/src/types/index.ts` (new interfaces appended)
- `frontend/src/App.tsx` (one new public route)
- `frontend/src/pages/Welcome.tsx` (one new link)
- `frontend/src/pages/ManagerDashboard.tsx` (two toggle states, two "Calculate" buttons, two inline `<EstimateCalculator>` renders — no existing logic altered)

No changes were made to `backend/app/api/invoices.py`, `backend/app/models/*`, or any database migration — the feature is purely additive and required no schema changes, reusing the existing generic `AppSettings` key/value table for its tunable values.

---

## 5. Known Limitations & Placeholder Values (read before "remaking" this for real use)

- **`hours_per_sqft` and `materials_per_sqft` for every job type are invented placeholders**, derived from generic industry rules of thumb (e.g. "a painter covers roughly 125 sqft/hour," "drywall runs roughly 35 sqft/hour"), not from this business's actual job history. They are safe as a starting point and are structured to be tunable without a redeploy, but should be recalibrated against real completed jobs before the public quick-quote number is trusted.
- **No settings UI exists yet** for `PUT /quick-quote-rates/{job_type}` or `PUT /quick-quote-admin-fee` — the endpoints work, but a manager currently has to call them directly (e.g. via the FastAPI `/docs` Swagger UI) rather than through a dedicated panel in the app.
- **The public `/quick-quote` endpoint has no rate limiting.** Since it triggers a live Google Maps Distance Matrix API call (a billed API) on every request, it's a potential cost/abuse vector if the site gets scraped or spammed. Add rate limiting (e.g. per-IP) before relying on this in production with a paid Maps key.
- **Travel gracefully degrades to $0**, not an error, if `GOOGLE_MAPS_API_KEY` is unset or the address lookup fails — this was a deliberate choice so a misconfigured key doesn't break the whole quote, but it means a customer could see an unrealistically low number for a far-away address if the key is ever removed or rate-limited.
- **The standalone tool's Home Depot "live lookup" is a stub**, not a working integration — see §2.5. No free official Home Depot API exists as of this writing; a real implementation needs a paid third-party product-data API and, likely, a small server-side proxy to avoid CORS issues calling from the browser.
- **Automated tests were written but not executed** against the real dependency set in the build environment (no network access to install `fastapi`/`pytest`/`node_modules`). Formulas were verified by hand-porting the exact arithmetic into disposable scripts and running them with a bare `python3`/Node interpreter, and every changed file was checked for syntax validity. Run the real backend `pytest` suite and `npm run build` / `tsc --noEmit` before shipping.
