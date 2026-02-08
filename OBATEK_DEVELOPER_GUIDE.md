# OBATEK Worker Portal - Developer Guide

**Version:** 1.0
**Date:** February 2026
**Stack:** FastAPI + React + TypeScript + PostgreSQL

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Tech Stack](#2-tech-stack)
3. [Project Structure](#3-project-structure)
4. [Environment Variables](#4-environment-variables)
5. [Database Models](#5-database-models)
6. [Authentication & Authorization](#6-authentication--authorization)
7. [Backend API Endpoints](#7-backend-api-endpoints)
8. [Payout Calculation Logic](#8-payout-calculation-logic)
9. [Frontend Architecture](#9-frontend-architecture)
10. [Frontend Pages & Routes](#10-frontend-pages--routes)
11. [State Management](#11-state-management)
12. [API Client Layer](#12-api-client-layer)
13. [TypeScript Types](#13-typescript-types)
14. [Middleware & Error Handling](#14-middleware--error-handling)
15. [Deployment](#15-deployment)
16. [Setup Instructions](#16-setup-instructions)

---

## 1. Architecture Overview

```
┌─────────────────────┐     ┌─────────────────────┐     ┌──────────────┐
│   React Frontend    │────▶│   FastAPI Backend    │────▶│  PostgreSQL  │
│   (Vite + TS)       │     │   (Python 3.11)      │     │  Database    │
│   Port: 5173 (dev)  │     │   Port: 8000         │     │  Port: 5432  │
└─────────────────────┘     └─────────────────────┘     └──────────────┘
        │                           │
        │                           ├── /uploads (file storage)
        │                           └── Google Maps API (distance calc)
        │
        ├── Zustand (auth state)
        ├── React Query (server state + offline cache)
        └── Axios (HTTP client with interceptors)
```

**User Roles:**
- **Worker** - Submit timesheets, view assigned jobs, create inspections, manage purchase list
- **Manager** - All worker abilities + create/edit jobs, view all timesheets, generate invoices
- **Admin** - All manager abilities + user management, role assignment

---

## 2. Tech Stack

### Backend
| Technology | Version | Purpose |
|---|---|---|
| FastAPI | 0.109.2 | REST API framework |
| SQLModel | 0.0.14 | ORM (SQLAlchemy + Pydantic) |
| PostgreSQL | 15+ | Production database |
| SQLite | - | Development database |
| Alembic | 1.13.1 | Database migrations |
| python-jose | 3.3.0 | JWT token handling |
| passlib + bcrypt | 1.7.4 / 4.0.1 | Password hashing |
| reportlab | 4.1.0 | PDF invoice generation |
| python-json-logger | 2.0.7 | Structured logging |
| Pillow | 10.2.0 | Image processing |

### Frontend
| Technology | Version | Purpose |
|---|---|---|
| React | 18.2+ | UI framework |
| TypeScript | 5.3+ | Type safety |
| Vite | 5.0+ | Build tool |
| Tailwind CSS | 3.4+ | Styling |
| React Router | 6.x | Client-side routing |
| TanStack React Query | 5.x | Server state management + offline |
| Zustand | 4.x | Client state management |
| Axios | 1.6+ | HTTP client |

---

## 3. Project Structure

```
newjon/
├── docker-compose.yml
├── backend/
│   ├── Dockerfile
│   ├── Procfile                    # Heroku/Railway deployment
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   │       └── 0001_create_inspection_tables.py
│   └── app/
│       ├── main.py                 # FastAPI app entry point
│       ├── config.py               # Settings from env vars
│       ├── database.py             # SQLModel engine & session
│       ├── seed.py                 # Initial role seeding
│       ├── models/
│       │   ├── __init__.py         # Exports all models
│       │   ├── role.py             # Role, UserRoleLink
│       │   ├── user.py             # User
│       │   ├── worker.py           # Worker
│       │   ├── client.py           # Client
│       │   ├── job.py              # Job, JobWorkerLink
│       │   ├── timesheet.py        # Timesheet
│       │   ├── invoice.py          # Invoice
│       │   ├── receipt.py          # Receipt
│       │   ├── purchase_item.py    # PurchaseListItem
│       │   └── inspection.py       # JobInspection, InspectionPhoto
│       ├── schemas/
│       │   ├── auth.py             # Login, Register, Token schemas
│       │   ├── worker.py           # Worker CRUD schemas
│       │   ├── client.py           # Client CRUD schemas
│       │   ├── job.py              # Job CRUD schemas
│       │   ├── timesheet.py        # Timesheet + Payout schemas
│       │   ├── invoice.py          # Invoice schemas
│       │   ├── inspection.py       # Inspection schemas
│       │   └── purchase.py         # Purchase item schemas
│       ├── api/
│       │   ├── deps.py             # Auth dependencies & role checks
│       │   ├── auth.py             # /api/auth/*
│       │   ├── workers.py          # /api/workers/*
│       │   ├── clients.py          # /api/clients/*
│       │   ├── jobs.py             # /api/jobs/*
│       │   ├── timesheets.py       # /api/timesheets/*
│       │   ├── invoices.py         # /api/invoices/*
│       │   ├── inspections.py      # /api/inspections/*
│       │   ├── purchases.py        # /api/purchases/*
│       │   └── users.py            # /api/users/* (admin)
│       ├── services/
│       │   ├── auth.py             # JWT + password hashing
│       │   └── payout.py           # Timesheet payout calculation
│       └── middleware/
│           ├── __init__.py
│           ├── logging_middleware.py
│           └── error_handlers.py
│
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── vite.config.ts
    ├── tsconfig.json
    ├── tailwind.config.js
    ├── postcss.config.js
    ├── index.html
    └── src/
        ├── main.tsx                # App bootstrap
        ├── App.tsx                 # Routes
        ├── index.css               # Tailwind + custom styles
        ├── types/
        │   └── index.ts            # All TypeScript interfaces
        ├── stores/
        │   └── authStore.ts        # Zustand auth store
        ├── api/
        │   ├── client.ts           # Axios instance + interceptors
        │   ├── auth.ts
        │   ├── jobs.ts
        │   ├── timesheets.ts
        │   ├── invoices.ts
        │   ├── inspections.ts
        │   ├── purchases.ts
        │   ├── clients.ts
        │   ├── workers.ts
        │   └── users.ts
        ├── lib/
        │   ├── utils.ts            # formatCurrency, formatDate, etc.
        │   └── queryClient.ts      # React Query + offline sync
        ├── components/
        │   ├── AuthInitializer.tsx  # Token validation on load
        │   ├── ErrorBoundary.tsx    # React error boundary
        │   ├── layout/
        │   │   ├── AppShell.tsx     # Main layout with nav
        │   │   ├── Navbar.tsx       # Navigation bar
        │   │   └── ProtectedRoute.tsx # Auth + role guard
        │   └── shared/
        │       └── OfflineBanner.tsx # Offline status indicator
        └── pages/
            ├── Welcome.tsx          # Landing page
            ├── Login.tsx            # Login form
            ├── Register.tsx         # Registration form
            ├── Dashboard.tsx        # Worker dashboard
            ├── ManagerDashboard.tsx  # Manager dashboard
            ├── AdminDashboard.tsx   # Admin user management
            ├── Calendar.tsx         # Job calendar view
            ├── PurchaseList.tsx     # Purchase item management
            ├── Inspections.tsx      # Inspection listing
            ├── CreateInspection.tsx # Inspection form
            ├── ViewInspection.tsx   # Inspection details
            ├── Invoices.tsx         # Invoice management
            └── ViewTimesheet.tsx    # Timesheet detail (PDF-like)
```

---

## 4. Environment Variables

### Backend (.env)

```env
# Database (PostgreSQL for production, SQLite for dev)
DATABASE_URL=postgresql://user:password@localhost:5432/obatek

# JWT Authentication
SECRET_KEY=your-secret-key-min-32-chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
REFRESH_TOKEN_EXPIRE_DAYS=7

# CORS - comma-separated allowed origins
CORS_ORIGINS=http://localhost:5173,https://yourdomain.com

# Google Maps API (for distance calculations between office and job site)
GOOGLE_MAPS_API_KEY=your-google-maps-api-key

# File uploads
UPLOAD_DIR=uploads
MAX_FILE_SIZE_MB=10

# Office address (used as origin for distance calculations)
OFFICE_ADDRESS=244 Bell Street North, K1R 5T7, Ottawa, Ontario, Canada

# Company card last-4-digits (comma-separated)
# Receipts paid with these cards are NOT reimbursed to workers
COMPANY_CARD_DIGITS=5564
```

### Frontend (.env)

```env
VITE_API_URL=http://localhost:8000/api
```

---

## 5. Database Models

### Entity Relationship Diagram

```
Role ──── UserRoleLink ──── User ──── Worker
                                        │
                                        ├── Timesheet ──── Receipt
                                        │       │
Client ──── Job ──── JobWorkerLink ─────┘       │
             │                                   │
             ├── Invoice                         │
             ├── JobInspection ── InspectionPhoto │
             └── (job_id FK on Timesheet) ───────┘

PurchaseListItem (standalone, references user IDs)
```

### Role & User

```python
class Role(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True, max_length=50)     # "worker", "manager", "admin"
    description: str | None = None

class UserRoleLink(SQLModel, table=True):
    user_id: int = Field(foreign_key="user.id", primary_key=True)
    role_id: int = Field(foreign_key="role.id", primary_key=True)

class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True, max_length=50)
    email: str = Field(unique=True, max_length=100)
    hashed_password: str
    is_active: bool = True
    created_at: datetime
    roles: List[Role] = Relationship(link_model=UserRoleLink)
    worker: Optional[Worker] = Relationship(back_populates="user")

    # Helper properties
    @property
    def is_manager(self) -> bool:
        return any(r.name in ("manager", "admin") for r in self.roles)

    @property
    def is_admin(self) -> bool:
        return any(r.name == "admin" for r in self.roles)
```

### Worker

```python
class Worker(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", unique=True)
    name: str = Field(max_length=100)
    hourly_rate: Decimal = Field(default=Decimal("0"), max_digits=6, decimal_places=2)
    charges_hst: bool = False       # If true, labor × 1.13
    is_employee: bool = False       # Employee vs contractor

    user: Optional[User] = Relationship(back_populates="worker")
    timesheets: List[Timesheet] = Relationship(back_populates="worker")
```

### Client

```python
class Client(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=100)
    phone_number: str | None = Field(default=None, max_length=20)
    email: str | None = None
    address: str
    jobs: List[Job] = Relationship(back_populates="client")
```

### Job

```python
class JobWorkerLink(SQLModel, table=True):
    job_id: int = Field(foreign_key="job.id", primary_key=True)
    worker_id: int = Field(foreign_key="worker.id", primary_key=True)

class Job(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    client_id: int = Field(foreign_key="client.id", index=True)
    description: str
    scheduled_date: date | None = None
    scheduled_time: time | None = None
    estimated_duration: Decimal | None = None
    is_completed: bool = False
    estimate_amount: Decimal | None = None
    calculated_distance_km: Decimal | None = None
    address_override: str | None = None

    client: Optional[Client] = Relationship(back_populates="jobs")
    assigned_workers: List[Worker] = Relationship(link_model=JobWorkerLink)
    timesheets: List[Timesheet] = Relationship(back_populates="job")
    invoices: List[Invoice] = Relationship(back_populates="job")
    inspections: List[JobInspection] = Relationship(back_populates="job")

    @property
    def job_address(self) -> str:
        return self.address_override or (self.client.address if self.client else "")
```

### Timesheet

```python
class Timesheet(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    worker_id: int = Field(foreign_key="worker.id", index=True)
    job_id: int = Field(foreign_key="job.id", index=True)
    date: date = Field(index=True)

    hours_worked: Decimal = Field(max_digits=4, decimal_places=2)
    round_trip_kms: Decimal = Field(default=Decimal("0"), max_digits=6, decimal_places=2)

    used_company_truck: bool = False
    worked_at_hq: bool = False

    company_materials: Decimal = Field(default=Decimal("0"), max_digits=8, decimal_places=2)
    personal_materials: Decimal = Field(default=Decimal("0"), max_digits=8, decimal_places=2)
    receipts_total: Decimal = Field(default=Decimal("0"), max_digits=8, decimal_places=2)
    receipt_card_digits: str | None = Field(default=None, max_length=4)

    calculated_pay: Decimal | None = Field(default=None, max_digits=10, decimal_places=2)
    created_at: datetime
    updated_at: datetime

    worker: Optional[Worker] = Relationship(back_populates="timesheets")
    job: Optional[Job] = Relationship(back_populates="timesheets")
    receipts: List[Receipt] = Relationship(back_populates="timesheet")
```

### Invoice

```python
class Invoice(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="job.id")
    invoice_number: str = Field(unique=True)
    created_date: date
    due_date: date | None = None
    subtotal: Decimal
    hst_amount: Decimal
    total: Decimal
    status: str = "draft"           # draft, sent, paid, overdue
    notes: str | None = None
    job: Optional[Job] = Relationship(back_populates="invoices")
```

### Receipt

```python
class Receipt(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    timesheet_id: int = Field(foreign_key="timesheet.id")
    image_path: str
    description: str | None = None
    amount: Decimal | None = None
    uploaded_at: datetime
    timesheet: Optional[Timesheet] = Relationship(back_populates="receipts")
```

### JobInspection & InspectionPhoto

```python
class JobInspection(SQLModel, table=True):
    __tablename__ = "job_inspection"
    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="job.id", index=True)
    type: str = Field(max_length=4)     # "pre" or "post"
    date: date

    # Common
    customer_name: str
    is_company_truck_required: bool

    # Pre-job fields
    materials_needed: str | None = None
    special_tools_needed: str | None = None
    existing_damage_notes: str | None = None
    flooring_protection_needed: str | None = None

    # Post-job fields
    dump_run_required: bool | None = None
    customer_keeping_materials: str | None = None
    materials_to_return: str | None = None
    inventory_used: str | None = None
    pickup_required: str | None = None
    damages_or_quality_concerns: str | None = None
    scope_change_notes: str | None = None

    job: Optional[Job] = Relationship(back_populates="inspections")
    photos: List[InspectionPhoto] = Relationship(back_populates="inspection")

class InspectionPhoto(SQLModel, table=True):
    __tablename__ = "inspection_photo"
    id: int | None = Field(default=None, primary_key=True)
    inspection_id: int = Field(foreign_key="job_inspection.id", index=True)
    image_path: str
    caption: str | None = Field(default=None, max_length=200)
    uploaded_at: datetime
    inspection: Optional[JobInspection] = Relationship(back_populates="photos")
```

### PurchaseListItem

```python
class PurchaseListItem(SQLModel, table=True):
    __tablename__ = "purchase_list_item"
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=200)
    quantity: str | None = Field(default=None, max_length=50)
    priority: str = Field(default="2_medium")   # 1_high, 2_medium, 3_low
    status: str = Field(default="needed")        # needed, purchased
    notes: str | None = None
    added_by_id: int | None = Field(default=None, foreign_key="user.id")
    added_at: datetime
    purchased_by_id: int | None = Field(default=None, foreign_key="user.id")
    purchased_at: datetime | None = None
```

---

## 6. Authentication & Authorization

### Flow

1. User registers via `POST /api/auth/register` (creates User + Worker + assigns "worker" role)
2. User logs in via `POST /api/auth/login` (OAuth2 password flow, returns JWT access + refresh tokens)
3. Frontend stores token in `localStorage` and Zustand persist store
4. Every API request includes `Authorization: Bearer <token>` header (via Axios interceptor)
5. Backend validates token via `get_current_user` dependency
6. Role checks via `require_manager` / `require_admin` dependencies

### JWT Token Structure

```json
{
  "sub": "1",                    // user ID as string
  "type": "access",             // "access" or "refresh"
  "exp": 1707379200             // expiry timestamp
}
```

### Password Hashing

- Algorithm: bcrypt via passlib
- `get_password_hash(password)` to hash
- `verify_password(plain, hashed)` to verify

### Dependency Injection (deps.py)

```python
# Type aliases used in route signatures:
CurrentUser = Annotated[User, Depends(get_current_user)]      # Any authenticated user
CurrentWorker = Annotated[Worker, Depends(get_current_worker)]  # Must have worker profile
ManagerUser = Annotated[User, Depends(require_manager)]         # Manager or admin only
AdminUser = Annotated[User, Depends(require_admin)]             # Admin only
DBSession = Annotated[Session, Depends(get_session)]            # Database session
```

### Frontend Auth (AuthInitializer)

On app load, `AuthInitializer` component:
1. Checks if there's a persisted token in Zustand store
2. Calls `GET /api/auth/me` to validate the token
3. If valid: refreshes user data
4. If invalid (401): clears auth state, redirects to login

---

## 7. Backend API Endpoints

### Authentication (`/api/auth`)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/login` | None | Login (OAuth2 form data) |
| POST | `/register` | None | Register new user + worker |
| GET | `/me` | User | Get current user info |
| POST | `/refresh` | None | Refresh access token |

### Workers (`/api/workers`)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | Manager | List all workers |
| GET | `/me` | User | Get own worker profile |
| GET | `/{id}` | Manager | Get worker by ID |
| PUT | `/{id}` | Manager | Update worker (rate, HST, etc.) |

### Clients (`/api/clients`)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | Manager | List all clients |
| GET | `/{id}` | Manager | Get client by ID |
| POST | `/` | Manager | Create client |
| PUT | `/{id}` | Manager | Update client |
| DELETE | `/{id}` | Manager | Delete client |

### Jobs (`/api/jobs`)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | User | List jobs (workers see assigned only) |
| GET | `/{id}` | User | Get job details |
| POST | `/` | Manager | Create job |
| PUT | `/{id}` | Manager | Update job |
| DELETE | `/{id}` | Manager | Delete job |
| GET | `/calendar` | User | Get calendar events |
| GET | `/{id}/distance` | User | Calculate distance via Google Maps |
| POST | `/{id}/assign` | Manager | Assign workers to job |

### Timesheets (`/api/timesheets`)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | User | List timesheets (workers see own only) |
| GET | `/summary` | Manager | Payroll summary totals |
| GET | `/{id}` | User | Get timesheet detail |
| POST | `/` | User | Submit timesheet (auto-calculates pay) |
| PUT | `/{id}` | User | Update timesheet |
| DELETE | `/{id}` | User | Delete timesheet |
| POST | `/{id}/receipts` | User | Upload receipt images |
| GET | `/{id}/receipts` | User | Get receipts for timesheet |
| DELETE | `/receipts/{id}` | User | Delete receipt |
| POST | `/calculate` | User | Preview payout calculation |

### Invoices (`/api/invoices`)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | Manager | List invoices |
| GET | `/{id}` | Manager | Get invoice |
| POST | `/job/{job_id}` | Manager | Generate invoice for job |
| PUT | `/{id}/status` | Manager | Update invoice status |
| DELETE | `/{id}` | Manager | Delete invoice |
| GET | `/{id}/pdf` | Manager | Download invoice PDF |

### Inspections (`/api/inspections`)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/job/{job_id}` | User | List inspections for job |
| POST | `/job/{job_id}/{type}` | User | Create pre/post inspection |
| GET | `/{id}` | User | Get inspection detail |
| PUT | `/{id}` | User | Update inspection |
| POST | `/{id}/photos` | User | Upload inspection photos |
| PUT | `/photos/{id}` | User | Update photo caption |
| DELETE | `/photos/{id}` | User | Delete photo |

### Purchases (`/api/purchases`)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | User | List purchase items |
| POST | `/` | User | Add item to purchase list |
| PUT | `/{id}` | User | Update item |
| PUT | `/{id}/purchased` | User | Mark as purchased |
| PUT | `/{id}/needed` | User | Mark as needed |
| DELETE | `/{id}` | User | Delete item |

### Users (`/api/users`) - Admin Only
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | Admin | List all users with roles |
| GET | `/{id}` | Admin | Get user details |
| POST | `/` | Admin | Create user with roles |
| PUT | `/{id}/roles` | Admin | Update user roles |
| PUT | `/{id}/toggle-active` | Admin | Enable/disable user |

---

## 8. Payout Calculation Logic

Located in `backend/app/services/payout.py`.

### Constants
- `MINIMUM_HOURS = 4.0` (minimum billable hours)
- `KM_RATE = $0.50/km`
- `HST_RATE = 1.13` (Ontario HST)

### Calculation Steps

```
1. Round hours to nearest 0.25
   e.g., 3.7 → 3.75

2. Apply minimum hours
   billable_hours = max(rounded_hours, 4.0)

3. Labor cost
   labor = billable_hours × worker.hourly_rate
   if worker.charges_hst: labor × 1.13

4. KM reimbursement (skip if company truck OR worked at HQ)
   km_reimburse = round_trip_kms × $0.50

5. Personal materials (direct reimbursement)
   + personal_materials

6. Receipts reimbursement (skip if company card used)
   if NOT company_card: + receipts_total

7. Total = labor + km_reimburse + personal_materials + receipts_reimburse

Note: company_materials is NOT added (company already paid)
```

### Company Card Detection

Card last-4-digits are checked against `COMPANY_CARD_DIGITS` env var (default: "5564"). If match, receipts are NOT reimbursed to the worker.

---

## 9. Frontend Architecture

### App Bootstrap (`main.tsx`)

```
<React.StrictMode>
  <ErrorBoundary>                      ← Catches React render errors
    <PersistQueryClientProvider>        ← React Query + localStorage cache
      <BrowserRouter>
        <AuthInitializer>              ← Validates JWT on load
          <App />                      ← Routes
        </AuthInitializer>
      </BrowserRouter>
    </PersistQueryClientProvider>
  </ErrorBoundary>
</React.StrictMode>
```

### Key Patterns

- **Data fetching**: React Query (`useQuery` / `useMutation`) with 5-min stale time
- **Auth state**: Zustand with `persist` middleware (localStorage)
- **API calls**: Centralized in `src/api/*.ts` files, all using shared Axios instance
- **Protected routes**: `<ProtectedRoute>` component checks auth + role
- **Offline support**: Mutation queue in localStorage, processes on reconnect
- **Error handling**: ErrorBoundary (React errors) + Axios interceptor (API errors)
- **Styling**: Tailwind CSS with custom `obatek` color theme

### Custom Tailwind Color

The app uses a custom brand color `obatek` defined in `tailwind.config.js`:
```js
theme: {
  extend: {
    colors: {
      obatek: {
        DEFAULT: '#2563eb',  // blue-600
        dark: '#1d4ed8',     // blue-700
      }
    }
  }
}
```

---

## 10. Frontend Pages & Routes

| Route | Component | Access | Description |
|-------|-----------|--------|-------------|
| `/` | Welcome | Public | Landing page |
| `/login` | Login | Public | Login form |
| `/register` | Register | Public | Registration form |
| `/dashboard` | Dashboard | Worker+ | Worker dashboard: assigned jobs, timesheet submission |
| `/calendar` | Calendar | Worker+ | Job calendar view |
| `/purchases` | PurchaseList | Worker+ | Shared purchase list |
| `/inspections` | Inspections | Worker+ | Job inspection listing |
| `/inspections/create/:jobId/:type` | CreateInspection | Worker+ | Pre/post inspection form |
| `/inspections/:id` | ViewInspection | Worker+ | Inspection detail view |
| `/manager` | ManagerDashboard | Manager+ | Job management, timesheet overview |
| `/timesheets/:id` | ViewTimesheet | Manager+ | PDF-like timesheet detail |
| `/invoices` | Invoices | Manager+ | Invoice management |
| `/admin` | AdminDashboard | Admin | User management, role assignment |

---

## 11. State Management

### Zustand Auth Store (`stores/authStore.ts`)

```typescript
interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;

  isManager: () => boolean;
  isAdmin: () => boolean;
  hasRole: (role: string) => boolean;

  login: (token: string, user: User) => void;
  logout: () => void;
  updateUser: (user: User) => void;
}
```

Persisted to localStorage under key `auth-storage`. Token also stored separately under `access_token` for the Axios interceptor.

### React Query Configuration

```typescript
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,       // 5 minutes
      gcTime: 24 * 60 * 60 * 1000,    // 24 hours cache
      retry: 1,
      networkMode: 'offlineFirst',
      refetchOnWindowFocus: false,
    },
    mutations: {
      networkMode: 'offlineFirst',
      retry: 1,
    },
  },
});
```

Cache is persisted to localStorage via `createSyncStoragePersister`.

### Offline Mutation Queue

When offline, mutations are queued in localStorage under `obatek-mutation-queue`. When back online, they're processed automatically with max 3 retries per mutation.

---

## 12. API Client Layer

### Axios Instance (`api/client.ts`)

- Base URL from `VITE_API_URL` env var
- 30-second timeout
- Request interceptor: adds `Authorization: Bearer <token>` header
- Response interceptor:
  - Logs errors with structured data
  - On 401: clears auth, redirects to `/login`
  - Attaches `userMessage` with human-readable error text

### Error Message Mapping

| Status | Message |
|--------|---------|
| Network Error | "Unable to connect to server" |
| Timeout | "Request timeout" |
| 400 | "Invalid request" |
| 401 | "Your session has expired" |
| 403 | "You do not have permission" |
| 404 | "Resource not found" |
| 409 | "Conflicts with existing data" |
| 422 | Shows field-level validation error |
| 500 | "Server error occurred" |

---

## 13. TypeScript Types

All types are in `frontend/src/types/index.ts`. Key interfaces:

- `User`, `LoginCredentials`, `LoginResponse`, `RegisterData`
- `Worker`, `Client`, `ClientBrief`
- `Job`, `JobCreate`, `CalendarEvent`
- `Timesheet`, `TimesheetCreate`
- `Invoice`, `InvoiceCreate`
- `Receipt`
- `PurchaseItem`, `PurchaseItemCreate`
- `JobInspection`, `InspectionPhoto`, `InspectionCreate`

---

## 14. Middleware & Error Handling

### Backend Middleware

**LoggingMiddleware** - Logs every request with:
- Method, path, query params, client IP
- Response status code and duration (ms)
- Skips health checks and static files
- Uses `python-json-logger` for structured JSON output

**Global Exception Handlers:**
- `RequestValidationError` → 422 with field-level errors
- `ValidationError` (Pydantic) → 422 with detail
- `IntegrityError` (DB) → 409 with human-readable message
- `SQLAlchemyError` → 500 "Database error"
- `ValueError` → 400 with message
- `Exception` (catch-all) → 500 "Unexpected error"

### Frontend Error Handling

**ErrorBoundary** - Wraps entire app tree. Shows:
- Error message with "Try Again" and "Go to Home" buttons
- In dev mode: full error details and component stack trace

**API Error Interceptor** - Attaches user-friendly messages to all Axios errors.

---

## 15. Deployment

### Docker Compose (Recommended)

```bash
# Build and start all services
docker-compose up -d

# Environment variables
cp .env.example .env
# Edit .env with your values
```

### Railway / Heroku

Backend includes a `Procfile`:
```
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Frontend builds as static files, deploy to any static host (Vercel, Netlify, etc.):
```bash
cd frontend
npm run build
# Deploy dist/ folder
```

### Database

- **Development**: SQLite (automatic, no setup needed)
- **Production**: PostgreSQL 15+
- Tables are auto-created on startup via `SQLModel.metadata.create_all()`
- Roles (`worker`, `manager`, `admin`) are auto-seeded on startup

---

## 16. Setup Instructions

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ (production) or SQLite (development)

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit DATABASE_URL, SECRET_KEY, etc.

# Start server (tables and roles auto-created)
uvicorn app.main:app --reload --port 8000
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Create .env file
echo "VITE_API_URL=http://localhost:8000/api" > .env

# Start dev server
npm run dev
```

### First User Setup

1. Register via the app at `/register`
2. Connect to database and manually promote to admin:
```sql
-- Find the user and admin role IDs
SELECT id FROM "user" WHERE username = 'yourusername';
SELECT id FROM role WHERE name = 'admin';

-- Add admin role
INSERT INTO userrolelink (user_id, role_id) VALUES (1, 3);
-- Also add manager role
INSERT INTO userrolelink (user_id, role_id) VALUES (1, 2);
```
3. Refresh the app - you now have full admin access
4. Use the Admin Dashboard to manage other users and roles

---

*This document contains the complete architecture and implementation details needed to replicate the OBATEK Worker Portal application.*
