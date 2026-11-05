import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { EstimateCalculator } from './EstimateCalculator';
import { estimatesApi } from '../api/estimates';
import type { Estimate, QuickQuoteRates } from '../types';

vi.mock('../api/estimates', () => ({
  estimatesApi: {
    getRates: vi.fn(),
    distancePreview: vi.fn(),
    searchMaterials: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    downloadPdfToFile: vi.fn(),
  },
}));
vi.mock('../api/clients', () => ({
  clientsApi: { create: vi.fn() },
}));

const FRAMES = 'Frames (incl. crossers)';
const JACKS = 'Jacks';
const PLANKS = 'Planks';

const savedScaffoldingRow = (component: string, ratePerDay: string, quantity: string, sortOrder = 0) => ({
  component, rate_per_day: ratePerDay, quantity, sort_order: sortOrder,
});

function makeEstimate(scaffoldingRows: unknown[]): Estimate {
  return {
    id: 7,
    estimate_number: 'EST-0007',
    client: null,
    client_name_override: null,
    address_override: null,
    scope_of_work: 'Repoint the chimney',
    crew_size: 1,
    techs_traveling: 1,
    distance_km: null,
    redseal_techs: 0,
    redseal_rate: '100.00',
    dump_fee: '0.00',
    permits_fee: '0.00',
    engineering_fee: '0.00',
    admin_fee: '50.00',
    heavy_equipment_rate: '120.00',
    include_admin_fee: true,
    include_hst: true,
    tasks: [
      {
        phase: 'build', description: 'Repoint', hours: '21', uses_heavy_equipment: false, uses_redseal: false, sort_order: 0,
      },
    ],
    equipment_rows: [],
    material_rows: [],
    scaffolding_rows: scaffoldingRows,
    tooling_rows: [],
  } as unknown as Estimate;
}

function renderCalculator(initialEstimate?: Estimate) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <EstimateCalculator initialEstimate={initialEstimate} clientId={1} onClose={vi.fn()} />
    </QueryClientProvider>
  );
}

function scaffoldingRow(label: string) {
  const row = screen.getByText(label).parentElement as HTMLElement;
  return {
    rate: within(row).getByTitle('Rate per unit per day') as HTMLInputElement,
    quantity: within(row).getByTitle('Quantity') as HTMLInputElement,
    element: row,
  };
}

const renderedScaffoldingLabels = () =>
  screen.getAllByTitle('Rate per unit per day').map((input) => input.parentElement?.firstChild?.textContent);

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(estimatesApi.getRates).mockResolvedValue({} as QuickQuoteRates);
  vi.mocked(estimatesApi.create).mockResolvedValue(makeEstimate([]));
});

describe('EstimateCalculator scaffolding on a new estimate', () => {
  it('fills in the standing rates and leaves the quantities to be typed', () => {
    renderCalculator();

    expect(scaffoldingRow(FRAMES).rate).toHaveValue(1);
    expect(scaffoldingRow(JACKS).rate).toHaveValue(2);
    expect(scaffoldingRow(PLANKS).rate).toHaveValue(3);

    expect(scaffoldingRow(FRAMES).quantity).toHaveValue(null);
    expect(scaffoldingRow(FRAMES).quantity).toHaveAttribute('placeholder', '40');
  });

  it('shows no figure in a cleared rate box, because a cleared box bills nothing', async () => {
    const user = userEvent.setup();
    renderCalculator();

    await user.clear(scaffoldingRow(FRAMES).rate);

    expect(scaffoldingRow(FRAMES).rate).toHaveValue(null);
    expect(scaffoldingRow(FRAMES).rate).not.toHaveAttribute('placeholder');
  });

  it('saves no scaffolding when no quantity was typed', async () => {
    const user = userEvent.setup();
    renderCalculator();

    await user.click(screen.getByRole('button', { name: 'Save Estimate' }));

    await waitFor(() => expect(estimatesApi.create).toHaveBeenCalled());
    expect(vi.mocked(estimatesApi.create).mock.calls[0][0].scaffolding_rows).toEqual([]);
  });

  it('saves the filled-in rate once a quantity is typed', async () => {
    const user = userEvent.setup();
    renderCalculator();

    await user.type(scaffoldingRow(PLANKS).quantity, '35');
    await user.click(screen.getByRole('button', { name: 'Save Estimate' }));

    await waitFor(() => expect(estimatesApi.create).toHaveBeenCalled());
    expect(vi.mocked(estimatesApi.create).mock.calls[0][0].scaffolding_rows).toEqual([
      { component: 'plank', rate_per_day: 3, quantity: 35, sort_order: 0 },
    ]);
  });
});

describe('EstimateCalculator scaffolding pricing', () => {
  it('prices a row from its quantity alone, for every travel day', async () => {
    const user = userEvent.setup();
    renderCalculator(makeEstimate([]));

    await user.type(scaffoldingRow(FRAMES).quantity, '40');

    expect(within(scaffoldingRow(FRAMES).element).getByText('$120.00')).toBeInTheDocument();
  });
});

describe('EstimateCalculator scaffolding on a reopened estimate', () => {
  it('brings back the components that were not saved, at their standing rates', () => {
    renderCalculator(makeEstimate([savedScaffoldingRow('frame', '1.50', '40')]));

    expect(scaffoldingRow(FRAMES).rate).toHaveValue(1.5);
    expect(scaffoldingRow(FRAMES).quantity).toHaveValue(40);
    expect(scaffoldingRow(JACKS).rate).toHaveValue(2);
    expect(scaffoldingRow(JACKS).quantity).toHaveValue(null);
    expect(scaffoldingRow(PLANKS).rate).toHaveValue(3);
  });

  it('keeps the components in their usual order when one in the middle was not saved', () => {
    renderCalculator(makeEstimate([
      savedScaffoldingRow('frame', '1.00', '40'),
      savedScaffoldingRow('plank', '3.00', '35', 1),
    ]));

    expect(renderedScaffoldingLabels()).toEqual([FRAMES, JACKS, PLANKS]);
  });

  it('gives the zero rows older estimates saved the standing rates', () => {
    renderCalculator(makeEstimate([
      savedScaffoldingRow('frame', '0.00', '0.00'),
      savedScaffoldingRow('jack', '0.00', '0.00', 1),
      savedScaffoldingRow('plank', '0.00', '0.00', 2),
    ]));

    expect(scaffoldingRow(FRAMES).rate).toHaveValue(1);
    expect(scaffoldingRow(JACKS).rate).toHaveValue(2);
    expect(scaffoldingRow(PLANKS).rate).toHaveValue(3);
  });

  it('leaves a saved no-charge row at no charge rather than re-pricing it', () => {
    renderCalculator(makeEstimate([savedScaffoldingRow('plank', '0.00', '35')]));

    expect(scaffoldingRow(PLANKS).rate).toHaveValue(null);
    expect(scaffoldingRow(PLANKS).quantity).toHaveValue(35);
    expect(within(scaffoldingRow(PLANKS).element).getByText('$0.00')).toBeInTheDocument();
  });

  it('keeps a standalone crosser row from an older estimate', () => {
    renderCalculator(makeEstimate([savedScaffoldingRow('crosser', '0.00', '56')]));

    expect(renderedScaffoldingLabels()).toEqual([FRAMES, 'Crossers', JACKS, PLANKS]);
    expect(scaffoldingRow('Crossers').quantity).toHaveValue(56);
  });
});
