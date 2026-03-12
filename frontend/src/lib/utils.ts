import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

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
