import type { Worker } from '../types';

interface WorkerPickerProps {
  workers: Worker[];
  assignedWorkerIds: number[];
  onToggle: (workerId: number) => void;
}

/** Who is on the job at all, before any question of which day. */
export function WorkerPicker({ workers, assignedWorkerIds, onToggle }: WorkerPickerProps) {
  return (
    <div className="flex flex-wrap gap-2">
      {workers.map((worker) => (
        <label
          key={worker.id}
          className={`flex items-center gap-2 px-3 py-2 border rounded-lg cursor-pointer transition-colors ${
            assignedWorkerIds.includes(worker.id)
              ? 'bg-obatek/10 border-obatek text-obatek'
              : 'border-gray-300 hover:border-gray-400'
          }`}
        >
          <input
            type="checkbox"
            checked={assignedWorkerIds.includes(worker.id)}
            onChange={() => onToggle(worker.id)}
            className="sr-only"
          />
          <span className="text-sm">{worker.name}</span>
        </label>
      ))}
    </div>
  );
}
