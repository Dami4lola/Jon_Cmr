import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import type { Job, WorkerBrief } from '../types';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatCurrency(amount: number | string): string {
  const num = typeof amount === 'string' ? parseFloat(amount) : amount;
  return new Intl.NumberFormat('en-CA', {
    style: 'currency',
    currency: 'CAD',
  }).format(num);
}

export function formatDate(date: string | Date): string {
  let d: Date;
  if (typeof date === 'string') {
    // Date-only strings (YYYY-MM-DD) are parsed as UTC midnight by JS,
    // which shifts to the previous day in negative UTC offsets (e.g. EST).
    // Append T12:00:00 so it's treated as local noon instead.
    d = /^\d{4}-\d{2}-\d{2}$/.test(date) ? new Date(date + 'T12:00:00') : new Date(date);
  } else {
    d = date;
  }
  return new Intl.DateTimeFormat('en-CA', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  }).format(d);
}

/**
 * The billing period an invoice covers.
 *
 * A null bound is unbounded, so an invoice with neither covers the whole job - the shape
 * every invoice issued before progress billing still carries.
 */
export function formatBillingPeriod(period: {
  period_start?: string | null;
  period_end?: string | null;
}): string {
  const { period_start: start, period_end: end } = period;
  if (start && end) return `${formatDate(start)} - ${formatDate(end)}`;
  if (start) return `From ${formatDate(start)}`;
  if (end) return `Up to ${formatDate(end)}`;
  return 'Whole job';
}

export function formatTime(time: string): string {
  const [hours, minutes] = time.split(':');
  const h = parseInt(hours, 10);
  const ampm = h >= 12 ? 'PM' : 'AM';
  const hour12 = h % 12 || 12;
  return `${hour12}:${minutes} ${ampm}`;
}

export function roundToQuarter(hours: number): number {
  return Math.round(hours * 4) / 4;
}

export function calculateMinimumHours(hours: number, minimumHours: number = 4): number {
  const rounded = roundToQuarter(hours);
  return Math.max(rounded, minimumHours);
}

export function getCoworkersForDate(
  job: Job,
  currentWorkerId: number,
  date: string
): WorkerBrief[] {
  const allWorkers = job.assigned_workers ?? [];
  const schedule = job.worker_schedule ?? [];

  const scheduledForDate = schedule.filter((entry) => entry.date === date);

  let coworkers: WorkerBrief[];

  if (scheduledForDate.length > 0) {
    const scheduledWorkerIds = new Set(scheduledForDate.map((e) => e.worker_id));
    coworkers = allWorkers.filter((w) => scheduledWorkerIds.has(w.id));
  } else {
    coworkers = allWorkers;
  }

  return coworkers.filter((w) => w.id !== currentWorkerId);
}

function getDateRange(start: string, end: string): string[] {
  const dates: string[] = [];
  const current = new Date(start + 'T12:00:00');
  const last = new Date(end + 'T12:00:00');
  while (current <= last) {
    dates.push(current.toLocaleDateString('en-CA'));
    current.setDate(current.getDate() + 1);
  }
  return dates;
}

export function getCoworkerSchedule(
  job: Job,
  currentWorkerId: number
): { date: string; coworkers: WorkerBrief[] }[] {
  const myDates = job.my_scheduled_dates ?? [];
  const today = new Date().toLocaleDateString('en-CA');

  let datesToCheck: string[];

  if (myDates.length > 0) {
    datesToCheck = myDates;
  } else if (job.start_date && job.end_date) {
    datesToCheck = getDateRange(job.start_date, job.end_date);
  } else {
    datesToCheck = [];
  }

  const upcoming = datesToCheck.filter((d) => d >= today);

  if (upcoming.length > 0) {
    return upcoming
      .map((d) => ({ date: d, coworkers: getCoworkersForDate(job, currentWorkerId, d) }))
      .filter((entry) => entry.coworkers.length > 0);
  }

  return [];
}

export function formatShortDate(dateStr: string): string {
  const d = new Date(dateStr + 'T12:00:00');
  return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
}

/**
 * The job address to show after a client selection changes.
 *
 * Replaces the field only while it is untouched - empty, or still exactly what was
 * auto-filled last time - so switching clients follows along but a manually typed
 * address is never clobbered. A job often happens somewhere other than the client's
 * registered address, which is what address_override exists for.
 *
 * A blank incoming address leaves the field alone, so clearing a client selection
 * cannot wipe what is already there.
 */
export function nextAutoFilledAddress(
  current: string,
  incoming: string,
  lastAutoFilled: string
): string {
  if (!incoming) return current;
  const untouched = current === '' || current === lastAutoFilled;
  return untouched ? incoming : current;
}

/**
 * Whether a settled address is worth spending a distance lookup on.
 *
 * Every lookup is a billed Google Distance Matrix call, so the same address is never
 * queried twice, and anything under the endpoint's 3-character minimum is rejected
 * here rather than round-tripped for a 422.
 *
 * kmPinned means someone typed a distance by hand - a staging yard or a ferry leg the
 * map cannot know about - and that number outranks anything Google would return.
 */
export function shouldLookupDistance(params: {
  address: string;
  lastLookedUp: string;
  kmPinned: boolean;
}): boolean {
  const address = params.address.trim();
  if (address.length < 3) return false;
  if (params.kmPinned) return false;
  return address !== params.lastLookedUp.trim();
}

/**
 * What a money input shows for a value of zero.
 *
 * Every one of these fields reads back as `parseFloat(value) || 0`, so zero and empty
 * already price the same. Rendering the zero means clearing it before a real number can
 * be typed, on every untouched box of a fresh estimate - so it renders as empty instead.
 *
 * Counts with a genuine floor stay numeric: crew size, techs traveling, and the Red Seal
 * tech count, where zero is a state the estimate warns about rather than an unfilled box.
 */
export function blankIfZero(value: number): number | '' {
  return value || '';
}

/**
 * The crew's gear list, grouped under its section headings.
 *
 * Section order follows first appearance rather than a fixed list, so the backend
 * stays the single authority on what order the crew packs in.
 */
export function groupPrepItemsBySection<T extends { section: string }>(
  items: T[]
): { section: string; items: T[] }[] {
  const grouped: { section: string; items: T[] }[] = [];
  for (const item of items) {
    const existing = grouped.find((g) => g.section === item.section);
    if (existing) {
      existing.items.push(item);
    } else {
      grouped.push({ section: item.section, items: [item] });
    }
  }
  return grouped;
}
