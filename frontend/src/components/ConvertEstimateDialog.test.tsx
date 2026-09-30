import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ConvertEstimateDialog } from './ConvertEstimateDialog';
import { estimatesApi } from '../api/estimates';
import { workersApi } from '../api/workers';
import { timeOffApi } from '../api/timeOff';
import type { Estimate, Job, Worker } from '../types';

vi.mock('../api/estimates', () => ({
  estimatesApi: { get: vi.fn(), convertToJob: vi.fn() },
}));
vi.mock('../api/workers', () => ({
  workersApi: { list: vi.fn() },
}));
vi.mock('../api/timeOff', () => ({
  timeOffApi: { list: vi.fn() },
}));

const estimate = {
  id: 7,
  estimate_number: 'EST-0007',
  client: { id: 1, name: 'Acme Industrial', address: '1 Bay St', phone_number: '613-555-0142' },
  scope_of_work: 'Rebuild the rear deck.',
  job_details: 'Rebuild the rear deck.\n\nWhat to bring\n\nMaterials\n- 24 x 2x6 cedar',
  total: '1130.00',
  total_hours: '20.00',
  travel_days: 3,
} as unknown as Estimate;

const workers = [
  { id: 1, name: 'Sam' },
  { id: 2, name: 'Alex' },
] as Worker[];

function renderDialog() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <ConvertEstimateDialog estimateId={7} onClose={vi.fn()} onConverted={vi.fn()} />
    </QueryClientProvider>
  );
}

async function setRange(start: string, end: string) {
  const startInput = await screen.findByLabelText('Start date');
  const endInput = screen.getByLabelText('End date');
  await userEvent.clear(startInput);
  await userEvent.type(startInput, start);
  await userEvent.clear(endInput);
  await userEvent.type(endInput, end);
}

describe('ConvertEstimateDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(estimatesApi.get).mockResolvedValue(estimate);
    vi.mocked(workersApi.list).mockResolvedValue(workers);
    vi.mocked(timeOffApi.list).mockResolvedValue([]);
    vi.mocked(estimatesApi.convertToJob).mockResolvedValue({ id: 99 } as Job);
  });

  it('offers the second screen once the job runs more than a day with a crew on it', async () => {
    renderDialog();
    await setRange('2026-03-02', '2026-03-04');
    await userEvent.click(screen.getByText('Sam'));

    expect(screen.getByRole('button', { name: 'Next: confirm days' })).toBeInTheDocument();
  });

  it('the second screen shows a column per day and only the chosen workers', async () => {
    renderDialog();
    await setRange('2026-03-02', '2026-03-04');
    await userEvent.click(screen.getByText('Sam'));
    await userEvent.click(screen.getByRole('button', { name: 'Next: confirm days' }));

    expect(await screen.findByText('Mon, Mar 2')).toBeInTheDocument();
    expect(screen.getByText('Wed, Mar 4')).toBeInTheDocument();
    expect(screen.getByText('Sam')).toBeInTheDocument();
    expect(screen.queryByText('Alex')).not.toBeInTheDocument();
    // One row of three days, all blank.
    expect(screen.getAllByRole('checkbox')).toHaveLength(3);
  });

  it('Back returns to the job with the form still filled in', async () => {
    renderDialog();
    await setRange('2026-03-02', '2026-03-04');
    await userEvent.click(screen.getByText('Sam'));
    await userEvent.click(screen.getByRole('button', { name: 'Next: confirm days' }));
    await userEvent.click(await screen.findByRole('button', { name: 'Back' }));

    expect(screen.getByLabelText('Start date')).toHaveValue('2026-03-02');
    expect(screen.getByDisplayValue('Rebuild the rear deck.')).toBeInTheDocument();
    expect(screen.getByDisplayValue(/What to bring/)).toBeInTheDocument();
  });

  it('a single-day job never offers the second screen', async () => {
    renderDialog();
    await setRange('2026-03-02', '2026-03-02');
    await userEvent.click(screen.getByText('Sam'));

    expect(screen.queryByRole('button', { name: 'Next: confirm days' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Convert to Job' })).toBeInTheDocument();
  });

  it('a multi-day job with nobody on it converts straight from the first screen', async () => {
    renderDialog();
    await setRange('2026-03-02', '2026-03-04');

    expect(screen.queryByRole('button', { name: 'Next: confirm days' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Convert to Job' })).toBeInTheDocument();
  });

  it('a single-day job still gets a schedule row per worker', async () => {
    renderDialog();
    await setRange('2026-03-02', '2026-03-02');
    await userEvent.click(screen.getByText('Sam'));
    await userEvent.click(screen.getByText('Alex'));
    await userEvent.click(screen.getByRole('button', { name: 'Convert to Job' }));

    await waitFor(() => expect(estimatesApi.convertToJob).toHaveBeenCalled());
    expect(vi.mocked(estimatesApi.convertToJob).mock.calls[0][1].worker_schedule).toEqual([
      { worker_id: 1, date: '2026-03-02' },
      { worker_id: 2, date: '2026-03-02' },
    ]);
  });

  it('sends the days ticked on the second screen', async () => {
    renderDialog();
    await setRange('2026-03-02', '2026-03-04');
    await userEvent.click(screen.getByText('Sam'));
    await userEvent.click(screen.getByRole('button', { name: 'Next: confirm days' }));
    await userEvent.click(await screen.findByLabelText('Sam on 2026-03-04'));
    await userEvent.click(screen.getByRole('button', { name: 'Convert to Job' }));

    await waitFor(() => expect(estimatesApi.convertToJob).toHaveBeenCalled());
    expect(vi.mocked(estimatesApi.convertToJob).mock.calls[0][1].worker_schedule).toEqual([
      { worker_id: 1, date: '2026-03-04' },
    ]);
  });

  it('unticking a worker last day keeps their row so they can be ticked again', async () => {
    renderDialog();
    await setRange('2026-03-02', '2026-03-04');
    await userEvent.click(screen.getByText('Sam'));
    await userEvent.click(screen.getByRole('button', { name: 'Next: confirm days' }));

    await userEvent.click(await screen.findByLabelText('Sam on 2026-03-02'));
    // Unticking their only day takes Sam off the job, but the row has to stay put.
    await userEvent.click(screen.getByLabelText('Sam on 2026-03-02'));
    expect(screen.getByText('Sam')).toBeInTheDocument();

    await userEvent.click(screen.getByLabelText('Sam on 2026-03-02'));
    expect(screen.getByLabelText('Sam on 2026-03-02')).toBeChecked();
  });
});
