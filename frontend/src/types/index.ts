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
export interface JobPhoto {
  id: number;
  public_url: string;
  caption?: string;
  uploaded_at: string;
}

export interface Job {
  id: number;
  client_id: number;
  title: string;
  details?: string;
  start_date?: string;
  end_date?: string;
  scheduled_time?: string;
  estimated_duration?: string;
  is_completed: boolean;
  is_redseal_trade: boolean;
  estimate_amount?: string;
  calculated_distance_km?: string;
  address_override?: string;
  client?: ClientBrief;
  job_address?: string;
  workers?: Worker[];
  assigned_workers?: WorkerBrief[];
  photos?: JobPhoto[];
  worker_schedule?: WorkerScheduleEntry[];
  my_scheduled_dates?: string[];
}

export interface JobCreate {
  client_id: number;
  title: string;
  details?: string;
  start_date?: string;
  end_date?: string;
  scheduled_time?: string;
  estimated_duration?: number;
  estimate_amount?: number;
  address_override?: string;
  is_redseal_trade?: boolean;
  assigned_worker_ids?: number[];
  worker_schedule?: WorkerScheduleEntry[];
}

export interface WorkerScheduleEntry {
  worker_id: number;
  date: string;
}

export interface CalendarEvent {
  id: number;
  title: string;
  start: string;
  end?: string;
  time?: string;
  duration?: string;
  client: string;
  address: string;
  description: string;
}

// Brief types for nested responses
export interface JobBrief {
  id: number;
  title: string;
  client_name: string;
  start_date?: string;
  end_date?: string;
}

export interface WorkerBrief {
  id: number;
  name: string;
}

// Timesheet Types
export interface Timesheet {
  id: number;
  worker_id: number;
  job_id: number;
  date: string;
  hours_worked: string;
  break_duration: string;
  used_company_truck: boolean;
  worked_at_hq: boolean;
  company_materials: string;
  personal_materials: string;
  calculated_pay?: string;
  minimum_hours_override?: string | null;
  notes?: string | null;
  is_paid: boolean;
  receipt_count: number;
  created_at: string;
  worker?: WorkerBrief;
  job?: JobBrief;
}

export interface TimesheetCreate {
  job_id: number;
  date: string;
  hours_worked: number;
  break_duration?: number;
  used_company_truck?: boolean;
  worked_at_hq?: boolean;
  company_materials?: number;
  personal_materials?: number;
  notes?: string;
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
  scope_of_work?: string;
  labour_amount: string;
  travel_amount: string;
  materials_amount: string;
  inventory_materials: string;
  dump_fee: string;
  admin_fee: string;
  total_labour_hours: string;
  total_distance_km: string;
  job?: Job;
  client?: ClientBrief;
}

export interface InvoiceCreate {
  invoice_number?: string;
  scope_of_work?: string;
  labour_amount?: number;
  travel_amount?: number;
  materials_amount?: number;
  inventory_materials?: number;
  dump_fee?: number;
  admin_fee?: number;
  total_labour_hours?: number;
  total_distance_km?: number;
  include_hst?: boolean;
  notes?: string;
}

export interface InvoicePreview {
  invoice_number: string;
  labour_hours: string;
  labour_amount: string;
  travel_km: string;
  travel_amount: string;
  materials_amount: string;
  inventory_materials: string;
  admin_fee: string;
  subtotal: string;
  hst_amount: string;
  total: string;
}

// Receipt Types
export interface Receipt {
  id: number;
  timesheet_id: number;
  image_url: string;  // Public S3 URL
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

// Payroll Types
export interface PayrollProcessRequest {
  start_date: string;
  end_date: string;
}

export interface PayrollEntryDetail {
  timesheet_id: number;
  date: string;
  customer_name: string;
  job_description: string;
  hours_worked: string;
  break_duration: string;
  billable_hours: string;
  labour_rate: string;
  labour_cost: string;
  km_distance: string;
  km_rate: string;
  km_cost: string;
  personal_materials: string;
  minimum_hours_override: string | null;
}

export interface PayrollWorkerSummary {
  worker_id: number;
  worker_name: string;
  entries: PayrollEntryDetail[];
  total_hours: string;
  total_labour: string;
  total_km: string;
  total_km_cost: string;
  total_personal_materials: string;
  labour_hst: string;
  km_hst: string;
  materials_hst: string;
  grand_total: string;
  charges_hst: boolean;
}

// API Response Types
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface SmsLog {
  id: number;
  job_id: number;
  client_id: number;
  phone_number: string;
  message_body: string;
  status: string;
  twilio_sid?: string;
  error_message?: string;
  sent_at?: string;
  created_at: string;
}

// Time-Off Request Types
export interface TimeOffRequest {
  id: number;
  worker_id: number;
  dates: string[];
  reason: string;
  status: 'pending' | 'approved' | 'denied';
  manager_note?: string | null;
  reviewed_by_id?: number | null;
  reviewed_at?: string | null;
  created_at: string;
  updated_at: string;
  worker?: WorkerBrief;
}

export interface TimeOffRequestCreate {
  dates: string[];
  reason: string;
}

export interface TimeOffRequestReview {
  status: 'approved' | 'denied';
  manager_note?: string;
}

export interface ApiError {
  detail: string;
}
