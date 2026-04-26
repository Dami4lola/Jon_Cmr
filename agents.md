# agents.md

## Context
The OBATEK Worker Portal is a fullstack workforce management web application. It is designed to track timesheets, jobs, invoices, inspections, and purchases. The app features a progressive web app (PWA) layer for offline support and operates on a strict Role-Based Access Control (RBAC) system for Workers, Managers, and Admins.

## Development Tasks
* Frontend Install: `npm install`
* Frontend Dev: `npm run dev`
* Backend Install: `pip install -r requirements.txt`
* Backend Dev: `uvicorn main:app --reload`
* Database Migrations: `alembic upgrade head` (Auto-runs on deployment).

## MCP Servers
* Playwright: Use this to test complex UI tables (like Timesheets and Jobs), verify Role-Based Access layout shifts, and ensure the Workbox PWA offline capabilities function correctly in the browser.

## Project Structure & Patterns
* Frontend Stack: React 18 + TypeScript + Vite.
* UI/Styling: Tailwind CSS + Radix UI.
* State & Data: Zustand (Auth) + TanStack Query (Server state/caching).
* Backend Stack: FastAPI (Python 3.11) + SQLModel (SQLAlchemy + Pydantic).
* Database & Auth: PostgreSQL (Railway deployment) + JWT with bcrypt.
* External APIs: AWS S3 (Receipt/Photo storage), Resend API (Emails), Google Maps Distance Matrix.
* PDF Generation: ReportLab for automated invoices.

## Core Features & Role Access
* Admin: Full access. Manages users and assigns roles.
* Manager: Manages jobs, creates invoices, views all timesheets, and manages client records.
* Worker: Submits timesheets, views assigned jobs, uploads receipts to S3.
* Jobs & Inspections: Multi-worker assignment, pre/post-job inspections with photo attachments.
* PWA Offline Support: Implemented via Workbox service worker for field reliability.

## Debugging
* API Issues: Always check the auto-generated FastAPI Swagger UI at `/docs` before modifying route logic.
* Database State: Verify SQLModel schemas match Alembic migration files if column errors occur.
* State Management: Use React Query Devtools to debug stale timesheet or job data.
* Permissions: If image uploads fail, verify AWS S3 bucket CORS and IAM policies.

## Business Logic & Cornerstones
* `backend/api/routes/payouts.py`: Payout calculations strictly enforce: Hourly rate × hours (4-hour minimum rule), plus distance allowances and material expenses.
* `backend/api/routes/invoices.py`: Invoice generation logic. Must auto-number as `INV-YYYY-NNNN`, apply exactly 13% Ontario HST, and trigger ReportLab PDF export.
* `frontend/src/features/jobs/`: Job management UI, integrating Google Maps distance calculations.
* `frontend/src/features/inspections/`: Inspection system handling type-specific fields and S3 photo links.
* `backend/models/`: Contains the 13 core SQLModel schemas (User, Role, Worker, Client, Job, Timesheet, Receipt, Invoice, etc.).

## Preferences
* Hallucination Prevention: Never provide information, package names, or code solutions you are not completely sure about. Instead, explicitly state "I don't know" or ask for clarification.
* Adaptive Learning: Continuously analyze error fixes and manual style corrections made during the project. Update your internal approach to avoid repeating the same architectural, logic, or stylistic mistakes.
* Clean Code: No comments explaining what the code does; only why if it's a complex distance calculation or specific PDF rendering workaround.
remove variables that get replaced to prevent clutter
* Strict Formatting: Never put emojis in code blocks under any circumstances.
* Naming: Use precise domain terminology (`timesheet` instead of `log`, `worker` instead of `employee`, `inspection` instead of `check`). Keep variable names highly descriptive.
* function Structure: A function should only ever need to do one thing and work on one level of abstraction unless absolutely needed.  
