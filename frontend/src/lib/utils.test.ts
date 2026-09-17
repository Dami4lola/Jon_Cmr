import { describe, it, expect } from 'vitest';
import { nextAutoFilledAddress } from './utils';

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
