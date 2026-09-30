import { describe, it, expect, vi } from 'vitest';
import { estimateToPayload } from './estimates';
import type { Estimate } from '../types';

vi.mock('./client', () => ({ default: {} }));

function makeEstimate(scaffoldingRows: unknown[]): Estimate {
  return {
    job: null,
    client: null,
    client_name_override: null,
    address_override: null,
    scope_of_work: 'Recert the boiler',
    crew_size: 2,
    techs_traveling: 2,
    distance_km: null,
    km_rate: '1.50',
    redseal_techs: 0,
    redseal_rate: '100.00',
    dump_fee: '0.00',
    permits_fee: '0.00',
    engineering_fee: '0.00',
    admin_fee: '50.00',
    heavy_equipment_rate: '0.00',
    include_admin_fee: true,
    include_hst: true,
    status: 'draft',
    tasks: [],
    equipment_rows: [],
    material_rows: [],
    scaffolding_rows: scaffoldingRows,
    tooling_rows: [],
  } as unknown as Estimate;
}

const row = (component: string, rate: string, quantity: string, sort_order = 0) => ({
  component, rate_per_day: rate, quantity, sort_order,
});

describe('estimateToPayload scaffolding', () => {
  it('drops the components a new estimate seeds but nobody filled in', () => {
    const payload = estimateToPayload(
      makeEstimate([row('frame', '0', '0'), row('jack', '0', '0', 1), row('plank', '0', '0', 2)])
    );

    expect(payload.scaffolding_rows).toEqual([]);
  });

  it('keeps the components that are actually on the job', () => {
    const payload = estimateToPayload(
      makeEstimate([row('frame', '1.00', '40'), row('jack', '0', '0', 1), row('plank', '3.00', '35', 2)])
    );

    expect(payload.scaffolding_rows).toEqual([
      { component: 'frame', rate_per_day: 1, quantity: 40, sort_order: 0 },
      { component: 'plank', rate_per_day: 3, quantity: 35, sort_order: 2 },
    ]);
  });

  it('keeps a component that is on site at no daily rate', () => {
    const payload = estimateToPayload(makeEstimate([row('plank', '0', '35')]));

    expect(payload.scaffolding_rows).toHaveLength(1);
    expect(payload.scaffolding_rows[0].quantity).toBe(35);
  });
});
