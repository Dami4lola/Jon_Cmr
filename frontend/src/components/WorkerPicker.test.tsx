import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { WorkerPicker } from './WorkerPicker';
import type { Worker } from '../types';

const workers = [
  { id: 1, name: 'Sam' },
  { id: 2, name: 'Alex' },
] as Worker[];

describe('WorkerPicker', () => {
  it('renders one entry per worker', () => {
    render(<WorkerPicker workers={workers} assignedWorkerIds={[]} onToggle={vi.fn()} />);

    expect(screen.getByText('Sam')).toBeInTheDocument();
    expect(screen.getByText('Alex')).toBeInTheDocument();
    expect(screen.getAllByRole('checkbox', { hidden: true })).toHaveLength(2);
  });

  it('reports the worker that was clicked', async () => {
    const onToggle = vi.fn();
    render(<WorkerPicker workers={workers} assignedWorkerIds={[]} onToggle={onToggle} />);

    await userEvent.click(screen.getByText('Alex'));

    expect(onToggle).toHaveBeenCalledWith(2);
  });

  it('shows which workers are already on the job', () => {
    render(<WorkerPicker workers={workers} assignedWorkerIds={[1]} onToggle={vi.fn()} />);

    expect(screen.getByText('Sam').closest('label')).toHaveClass('border-obatek');
    expect(screen.getByText('Alex').closest('label')).not.toHaveClass('border-obatek');
  });
});
