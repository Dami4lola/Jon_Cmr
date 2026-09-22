import { useState } from 'react';
import { groupPrepItemsBySection } from '../lib/utils';
import type { JobPrepItem } from '../types';

interface JobPrepListProps {
  items: JobPrepItem[];
}

// Read on a phone in a truck, so it opens collapsed to one tappable line and the
// count is on the button - enough to know whether anything has to be picked up.
export function JobPrepList({ items }: JobPrepListProps) {
  const [open, setOpen] = useState(false);

  if (items.length === 0) return null;

  const sections = groupPrepItemsBySection(items);

  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="text-sm font-medium text-obatek hover:underline"
      >
        {open ? 'Hide' : 'What to bring'} ({items.length})
      </button>
      {open && (
        <div className="mt-2 space-y-2 border-l-2 border-obatek/30 pl-3">
          {sections.map((section) => (
            <div key={section.section}>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                {section.section}
              </p>
              <ul className="mt-1 space-y-0.5">
                {section.items.map((item, index) => (
                  <li key={`${item.description}-${index}`} className="text-sm text-gray-700">
                    <span className="font-medium">{item.quantity}</span>
                    {item.unit ? ` ${item.unit}` : ''} &times; {item.description}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
