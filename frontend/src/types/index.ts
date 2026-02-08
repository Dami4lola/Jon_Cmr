// User & Auth Types
export interface User {
  id: number;
  username: string;
  email: string;
  is_active: boolean;
  created_at: string;
  roles: string[];
  worker_id?: number;
  worker_name?: string;
}

export interface Role {
  id: number;
  name: string;
  description?: string;
}

export interface LoginCredentials {
  username: string;
  password: string;
}

export interface RegisterData {
  username: string;
  email: string;
  password: string;
  name: string;
  hourly_rate: number;
  charges_hst?: boolean;
  is_employee?: boolean;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface RegisterResponse {
  access_token: string;
  token_type: string;
  user: User;
}

// Worker Types
export interface Worker {
  id: number;
  user_id: number;
  name: string;
  hourly_rate: string;
  charges_hst: boolean;
  is_employee: boolean;
  user?: User;
}

// Client Types
export interface Client {
  id: number;
  name: string;
  phone_number?: string;
  email?: string;
  address: string;
}

export interface ClientBrief {
  id: number;
  name: string;
  phone_number?: string;
  address: string;
}

// Job Types
export interface Job {
  id: number;
  client_id: number;
  description: string;
  scheduled_date?: string;
  scheduled_time?: string;
  estimated_duration?: string;
  is_completed: boolean;
  estimate_amount?: string;
  calculated_distance_km?: string;
  address_override?: string;
  client?: ClientBrief;
  job_address?: string;
  workers?: Worker[];
}

export interface JobCreate {
  client_id: number;
  description: string;
  scheduled_date?: string;
  scheduled_time?: string;
  estimated_duration?: number;
  estimate_amount?: number;
  address_override?: string;
  assigned_worker_ids?: number[];
}

export interface CalendarEvent {
  id: number;
  title: string;
  start: string;
  time?: string;
  duration?: string;
  client: string;
  address: string;
  description: string;
}

// Timesheet Types
export interface Timesheet {
  id: number;
  worker_id: number;
  job_id: number;
  date: string;
  hours_worked: string;
  round_trip_kms: string;
  used_company_truck: boolean;
  worked_at_hq: boolean;
  company_materials: string;
  personal_materials: string;
  receipts_total: string;
  receipt_card_digits?: string;
  calculated_pay?: string;
  created_at: string;
  worker?: Worker;
  job?: Job;
}

export interface TimesheetCreate {
  job_id: number;
  date: string;
  hours_worked: number;
  round_trip_kms?: number;
  used_company_truck?: boolean;
  worked_at_hq?: boolean;
  company_materials?: number;
  personal_materials?: number;
  receipts_total?: number;
  receipt_card_digits?: string;
}

// Invoice Types
export interface Invoice {
  id: number;
  job_id: number;
  invoice_number: string;
  created_date: string;
  due_date?: string;
  subtotal: string;
  hst_amount: string;
  total: string;
  status: 'draft' | 'sent' | 'paid' | 'overdue';
  notes?: string;
  job?: Job;
}

export interface InvoiceCreate {
  due_date?: string;
  notes?: string;
  include_hst?: boolean;
}

// Receipt Types
export interface Receipt {
  id: number;
  timesheet_id: number;
  image_path: string;
  image_url?: string;
  description?: string;
  amount?: string;
  uploaded_at: string;
}

// Purchase List Types
export interface PurchaseItem {
  id: number;
  name: string;
  quantity?: string;
  priority: string;
  status: string;
  notes?: string;
  added_by_id?: number;
  added_by_name?: string;
  added_at: string;
  purchased_by_id?: number;
  purchased_by_name?: string;
  purchased_at?: string;
}

export interface PurchaseItemCreate {
  name: string;
  quantity?: string;
  priority?: string;
  notes?: string;
}

// Inspection Types
export interface JobInspection {
  id: number;
  job_id: number;
  type: 'pre' | 'post';
  date: string;

  // Common Fields
  customer_name: string;
  is_company_truck_required: boolean;

  // Pre-Job Specific Fields
  materials_needed?: string;
  special_tools_needed?: string;
  existing_damage_notes?: string;
  flooring_protection_needed?: string;

  // Post-Job Specific Fields
  dump_run_required?: boolean;
  customer_keeping_materials?: string;
  materials_to_return?: string;
  inventory_used?: string;
  pickup_required?: string;
  damages_or_quality_concerns?: string;
  scope_change_notes?: string;

  photos?: InspectionPhoto[];
  job?: Job;
}

export interface InspectionPhoto {
  id: number;
  inspection_id: number;
  image_path: string;
  caption?: string;
  uploaded_at: string;
}

export interface InspectionCreate {
  date: string;
  customer_name: string;
  is_company_truck_required: boolean;
  materials_needed?: string;
  special_tools_needed?: string;
  existing_damage_notes?: string;
  flooring_protection_needed?: string;
  dump_run_required?: boolean;
  customer_keeping_materials?: string;
  materials_to_return?: string;
  inventory_used?: string;
  pickup_required?: string;
  damages_or_quality_concerns?: string;
  scope_change_notes?: string;
}

// API Response Types
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface ApiError {
  detail: string;
}
