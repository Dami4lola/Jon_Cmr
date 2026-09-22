import { describe, it, expect } from 'vitest';
import {
  blankIfZero,
  groupPrepItemsBySection,
  nextAutoFilledAddress,
  shouldLookupDistance,
} from './utils';

describe('nextAutoFilledAddress', () => {
  it('fills an empty field from the selected client', () => {
    expect(nextAutoFilledAddress('', '1 Bay St', '')).toBe('1 Bay St');
  });

  it('follows the client when the address is still what was auto-filled', () => {
    expect(nextAutoFilledAddress('1 Bay St', '99 Queen St', '1 Bay St')).toBe('99 Queen St');
  });

  it('keeps an address the user typed', () => {
    expect(nextAutoFilledAddress('Site B, rear entrance', '99 Queen St', '1 Bay St')).toBe(
      'Site B, rear entrance'
    );
  });

  it('keeps a typed address even when nothing was auto-filled before', () => {
    expect(nextAutoFilledAddress('Site B', '1 Bay St', '')).toBe('Site B');
  });

  it('leaves the field alone when the client has no address', () => {
    expect(nextAutoFilledAddress('1 Bay St', '', '1 Bay St')).toBe('1 Bay St');
  });

  it('does not wipe a typed address when the client selection is cleared', () => {
    expect(nextAutoFilledAddress('Site B', '', '')).toBe('Site B');
  });

  it('is a no-op when the same client is re-selected', () => {
    expect(nextAutoFilledAddress('1 Bay St', '1 Bay St', '1 Bay St')).toBe('1 Bay St');
  });

  it('refills after the user clears the field', () => {
    expect(nextAutoFilledAddress('', '99 Queen St', '1 Bay St')).toBe('99 Queen St');
  });
});

describe('shouldLookupDistance', () => {
  it('looks up an address that has not been queried yet', () => {
    expect(shouldLookupDistance({ address: '1 Bay St', lastLookedUp: '', kmPinned: false })).toBe(
      true
    );
  });

  it('looks up again once the address changes', () => {
    expect(
      shouldLookupDistance({ address: '99 Queen St', lastLookedUp: '1 Bay St', kmPinned: false })
    ).toBe(true);
  });

  it('does not re-query the address it already resolved', () => {
    expect(
      shouldLookupDistance({ address: '1 Bay St', lastLookedUp: '1 Bay St', kmPinned: false })
    ).toBe(false);
  });

  it('ignores surrounding whitespace when comparing', () => {
    expect(
      shouldLookupDistance({ address: '  1 Bay St ', lastLookedUp: '1 Bay St', kmPinned: false })
    ).toBe(false);
  });

  it('leaves a hand-entered distance alone', () => {
    expect(
      shouldLookupDistance({ address: '99 Queen St', lastLookedUp: '1 Bay St', kmPinned: true })
    ).toBe(false);
  });

  it('skips an address too short for the endpoint to accept', () => {
    expect(shouldLookupDistance({ address: '1 ', lastLookedUp: '', kmPinned: false })).toBe(false);
  });

  it('skips an empty address', () => {
    expect(shouldLookupDistance({ address: '   ', lastLookedUp: '', kmPinned: false })).toBe(false);
  });
});

describe('blankIfZero', () => {
  it('shows an unfilled box instead of a zero', () => {
    expect(blankIfZero(0)).toBe('');
  });

  it('keeps a real quantity', () => {
    expect(blankIfZero(40)).toBe(40);
  });

  it('keeps a fractional rate', () => {
    expect(blankIfZero(1.5)).toBe(1.5);
  });

  it('keeps a negative value rather than hiding it', () => {
    expect(blankIfZero(-5)).toBe(-5);
  });
});

describe('groupPrepItemsBySection', () => {
  const item = (section: string, description: string) => ({ section, description });

  it('gathers items under their section', () => {
    const grouped = groupPrepItemsBySection([
      item('Materials', '2x6 cedar'),
      item('Materials', 'Screws'),
    ]);

    expect(grouped).toHaveLength(1);
    expect(grouped[0].section).toBe('Materials');
    expect(grouped[0].items.map((i) => i.description)).toEqual(['2x6 cedar', 'Screws']);
  });

  it('keeps sections in the order the backend sent them', () => {
    const grouped = groupPrepItemsBySection([
      item('Equipment & rentals', 'Jackhammer'),
      item('Materials', 'Concrete'),
      item('Scaffolding', 'Planks'),
    ]);

    expect(grouped.map((g) => g.section)).toEqual([
      'Equipment & rentals',
      'Materials',
      'Scaffolding',
    ]);
  });

  it('regroups a section that appears again later', () => {
    const grouped = groupPrepItemsBySection([
      item('Materials', 'Concrete'),
      item('Scaffolding', 'Planks'),
      item('Materials', 'Rebar'),
    ]);

    expect(grouped.map((g) => g.section)).toEqual(['Materials', 'Scaffolding']);
    expect(grouped[0].items.map((i) => i.description)).toEqual(['Concrete', 'Rebar']);
  });

  it('has nothing to group when the job has no estimate', () => {
    expect(groupPrepItemsBySection([])).toEqual([]);
  });
});
