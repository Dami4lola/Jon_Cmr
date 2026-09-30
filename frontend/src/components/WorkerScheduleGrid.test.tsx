import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { WorkerScheduleGrid } from './WorkerScheduleGrid';
import { timeOffApi } from '../api/timeOff';
import type { Worker, WorkerScheduleEntry } from '../types';

vi.mock('../api/timeOff', () => ({
  timeOffApi: { list: vi.fn() },
}));

const workers = [
  { id: 1, name: 'Sam' },
  { id: 2, name: 'Alex' },
] as Worker[];

function renderGrid(props: {
  startDate?: string;
  endDate?: string;
  schedule?: WorkerScheduleEntry[];
  assignedWorkerIds?: number[];
  onChange?: (s: WorkerScheduleEntry[], ids: number[]) => void;
}) {
  const onChange = props.onChange ?? vi.fn();
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  render(
    <QueryClientProvider client={queryClient}>
      <WorkerScheduleGrid
        workers={workers}
        startDate={props.startDate ?? null}
        endDate={props.endDate ?? null}
        schedule={props.schedule ?? []}
        assignedWorkerIds={props.assignedWorkerIds ?? []}
        onChange={onChange}
      />
    </QueryClientProvider>
  );

  return onChange;
}

describe('WorkerScheduleGrid', () => {
  beforeEach(() => {
    vi.mocked(timeOffApi.list).mockResolvedValue([]);
  });

  it('draws a column per day of the range', async () => {
    renderGrid({ startDate: '2026-03-02', endDate: '2026-03-04' });

    expect(await screen.findByText('Mon, Mar 2')).toBeInTheDocument();
    expect(screen.getByText('Tue, Mar 3')).toBeInTheDocument();
    expect(screen.getByText('Wed, Mar 4')).toBeInTheDocument();
    // Two workers over three days.
    expect(screen.getAllByRole('checkbox')).toHaveLength(6);
  });

  it('ticking a day assigns the worker to the job as well', async () => {
    const onChange = renderGrid({ startDate: '2026-03-02', endDate: '2026-03-03' });

    await userEvent.click(await screen.findByLabelText('Sam on 2026-03-02'));

    expect(onChange).toHaveBeenCalledWith([{ worker_id: 1, date: '2026-03-02' }], [1]);
  });

  it('unticking a worker last day drops only that worker from the job', async () => {
    const onChange = renderGrid({
      startDate: '2026-03-02',
      endDate: '2026-03-02',
      schedule: [{ worker_id: 1, date: '2026-03-02' }],
      assignedWorkerIds: [1, 2],
    });

    await userEvent.click(await screen.findByLabelText('Sam on 2026-03-02'));

    expect(onChange).toHaveBeenCalledWith([], [2]);
  });

  it('marks a day the worker has approved time off for', async () => {
    vi.mocked(timeOffApi.list).mockResolvedValue([
      { id: 1, worker_id: 1, dates: ['2026-03-03'], status: 'approved' },
    ] as never);

    renderGrid({ startDate: '2026-03-02', endDate: '2026-03-03' });

    expect(await screen.findByText('OFF')).toBeInTheDocument();
    expect(screen.queryByLabelText('Sam on 2026-03-03')).not.toBeInTheDocument();
  });

  it('leaves out a worker who is off for the whole job', async () => {
    vi.mocked(timeOffApi.list).mockResolvedValue([
      { id: 1, worker_id: 1, dates: ['2026-03-02', '2026-03-03'], status: 'approved' },
    ] as never);

    renderGrid({ startDate: '2026-03-02', endDate: '2026-03-03' });

    await waitFor(() => expect(screen.queryByText('Sam')).not.toBeInTheDocument());
    expect(screen.getByText('Alex')).toBeInTheDocument();
  });

  it('falls back to a flat worker list until the range is valid', async () => {
    renderGrid({ startDate: '2026-03-04', endDate: '2026-03-02' });

    expect(screen.queryByRole('table')).not.toBeInTheDocument();
    expect(screen.getByText('Sam')).toBeInTheDocument();
    expect(screen.getAllByRole('checkbox', { hidden: true })).toHaveLength(2);
  });

  it('the flat list assigns a worker without scheduling any day', async () => {
    const onChange = renderGrid({});

    await userEvent.click(screen.getByText('Alex'));

    expect(onChange).toHaveBeenCalledWith([], [2]);
  });
});
