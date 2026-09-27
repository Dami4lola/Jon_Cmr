import { useQuery } from '@tanstack/react-query';
import { timeOffApi } from '../api/timeOff';
import { formatShortDate, getDateRange } from '../lib/utils';
import { WorkerPicker } from './WorkerPicker';
import type { TimeOffRequest, Worker, WorkerScheduleEntry } from '../types';

interface WorkerScheduleGridProps {
  workers: Worker[];
  startDate: string | null | undefined;
  endDate: string | null | undefined;
  schedule: WorkerScheduleEntry[];
  assignedWorkerIds: number[];
  onChange: (schedule: WorkerScheduleEntry[], workerIds: number[]) => void;
}

/**
 * Who works which day, one column per day of the job.
 *
 * Falls back to a flat worker list until a valid range exists, because there are no
 * columns to draw before then - and a job scheduled that way is exactly what leaves the
 * crew's dashboard showing a bare date range instead of their own days.
 */
export function WorkerScheduleGrid({
  workers,
  startDate,
  endDate,
  schedule,
  assignedWorkerIds,
  onChange,
}: WorkerScheduleGridProps) {
  const { data: timeOffRequests = [] } = useQuery({
    queryKey: ['time-off', 'all'],
    queryFn: () => timeOffApi.list(),
  });

  const approvedTimeOff = timeOffRequests.filter((r: TimeOffRequest) => r.status === 'approved');

  const isWorkerOffOnDate = (workerId: number, date: string): boolean =>
    approvedTimeOff.some(
      (r: TimeOffRequest) => r.worker_id === workerId && r.dates.includes(date)
    );

  const isWorkerOffAllDates = (workerId: number, dates: string[]): boolean =>
    dates.length > 0 && dates.every((d) => isWorkerOffOnDate(workerId, d));

  const toggleDay = (workerId: number, date: string) => {
    const next = [...schedule];
    const index = next.findIndex((ws) => ws.worker_id === workerId && ws.date === date);
    if (index >= 0) {
      next.splice(index, 1);
    } else {
      next.push({ worker_id: workerId, date });
    }

    // Only this worker's assignment moves. Rebuilding the whole list from the schedule
    // would drop anyone assigned without a day yet - which is every worker on a job
    // converted before the grid existed.
    const stillScheduled = next.some((ws) => ws.worker_id === workerId);
    const workerIds = stillScheduled
      ? assignedWorkerIds.includes(workerId)
        ? assignedWorkerIds
        : [...assignedWorkerIds, workerId]
      : assignedWorkerIds.filter((id) => id !== workerId);

    onChange(next, workerIds);
  };

  const toggleWorker = (workerId: number) => {
    const isAssigned = assignedWorkerIds.includes(workerId);
    onChange(
      schedule.filter((ws) => ws.worker_id !== workerId),
      isAssigned
        ? assignedWorkerIds.filter((id) => id !== workerId)
        : [...assignedWorkerIds, workerId]
    );
  };

  if (!startDate || !endDate || startDate > endDate) {
    return (
      <WorkerPicker
        workers={workers}
        assignedWorkerIds={assignedWorkerIds}
        onToggle={toggleWorker}
      />
    );
  }

  const dates = getDateRange(startDate, endDate);

  return (
    <div className="overflow-x-auto border rounded-lg">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-gray-50">
            <th className="px-3 py-2 text-left font-medium text-gray-600 sticky left-0 bg-gray-50">
              Worker
            </th>
            {dates.map((d) => (
              <th key={d} className="px-2 py-2 text-center font-medium text-gray-600 whitespace-nowrap">
                {formatShortDate(d)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y">
          {workers
            .filter((worker) => !isWorkerOffAllDates(worker.id, dates))
            .map((worker) => (
              <tr key={worker.id} className="hover:bg-gray-50">
                <td className="px-3 py-2 font-medium sticky left-0 bg-white">{worker.name}</td>
                {dates.map((d) => {
                  const offOnDate = isWorkerOffOnDate(worker.id, d);
                  const isChecked = schedule.some(
                    (ws) => ws.worker_id === worker.id && ws.date === d
                  );
                  return (
                    <td key={d} className={`px-2 py-2 text-center ${offOnDate ? 'bg-red-50' : ''}`}>
                      {offOnDate ? (
                        <span className="text-xs text-red-400" title="On approved time off">OFF</span>
                      ) : (
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => toggleDay(worker.id, d)}
                          aria-label={`${worker.name} on ${d}`}
                          className="w-4 h-4 text-obatek rounded border-gray-300 focus:ring-obatek"
                        />
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
        </tbody>
      </table>
    </div>
  );
}
