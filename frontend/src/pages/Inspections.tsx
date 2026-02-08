import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { jobsApi } from '../api/jobs';
import { inspectionsApi } from '../api/inspections';
import { formatDate } from '../lib/utils';
import type { Job, JobInspection } from '../types';

export function Inspections() {
  // Fetch jobs for creating inspections
  const { data: jobs = [], isLoading: loadingJobs } = useQuery({
    queryKey: ['jobs', 'all'],
    queryFn: () => jobsApi.list(),
  });

  // We'll show jobs that have inspections or need them
  const jobsWithInspections = jobs.filter((job: Job) => !job.is_completed);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Job Inspections</h1>
      </div>

      {loadingJobs ? (
        <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
          Loading...
        </div>
      ) : jobs.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
          No jobs available for inspection.
        </div>
      ) : (
        <div className="space-y-4">
          {jobsWithInspections.map((job: Job) => (
            <JobInspectionCard key={job.id} job={job} />
          ))}
        </div>
      )}

      {/* Completed jobs section */}
      {jobs.filter((j: Job) => j.is_completed).length > 0 && (
        <div className="mt-8">
          <h2 className="text-lg font-semibold text-gray-700 mb-4">Completed Jobs</h2>
          <div className="space-y-4">
            {jobs
              .filter((j: Job) => j.is_completed)
              .slice(0, 5)
              .map((job: Job) => (
                <JobInspectionCard key={job.id} job={job} />
              ))}
          </div>
        </div>
      )}
    </div>
  );
}

function JobInspectionCard({ job }: { job: Job }) {
  // Fetch inspections for this job
  const { data: inspections = [], isLoading } = useQuery({
    queryKey: ['inspections', 'job', job.id],
    queryFn: () => inspectionsApi.listForJob(job.id),
  });

  const preInspection = inspections.find((i: JobInspection) => i.type === 'pre');
  const postInspection = inspections.find((i: JobInspection) => i.type === 'post');

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="font-semibold text-gray-900">{job.description}</h3>
          <p className="text-sm text-gray-600">
            {job.client?.name} | {job.job_address}
          </p>
          {job.scheduled_date && (
            <p className="text-sm text-obatek">
              {formatDate(job.scheduled_date)}
            </p>
          )}
        </div>
        {job.is_completed && (
          <span className="bg-green-100 text-green-700 text-xs font-medium px-2 py-1 rounded">
            Completed
          </span>
        )}
      </div>

      {isLoading ? (
        <div className="text-gray-400 text-sm">Loading inspections...</div>
      ) : (
        <div className="grid grid-cols-2 gap-4">
          {/* Pre-Inspection */}
          <div className="border rounded-lg p-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-gray-700">Pre-Inspection</span>
              {preInspection ? (
                <span className="text-xs text-green-600">Done</span>
              ) : (
                <span className="text-xs text-gray-400">Not done</span>
              )}
            </div>
            {preInspection ? (
              <Link
                to={`/inspections/${preInspection.id}`}
                className="text-sm text-obatek hover:underline"
              >
                View ({preInspection.photos?.length || 0} photos)
              </Link>
            ) : (
              <Link
                to={`/inspections/create/${job.id}/pre`}
                className="inline-block text-sm bg-obatek/10 text-obatek px-3 py-1 rounded hover:bg-obatek/20 transition-colors"
              >
                Create
              </Link>
            )}
          </div>

          {/* Post-Inspection */}
          <div className="border rounded-lg p-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-gray-700">Post-Inspection</span>
              {postInspection ? (
                <span className="text-xs text-green-600">Done</span>
              ) : (
                <span className="text-xs text-gray-400">Not done</span>
              )}
            </div>
            {postInspection ? (
              <Link
                to={`/inspections/${postInspection.id}`}
                className="text-sm text-obatek hover:underline"
              >
                View ({postInspection.photos?.length || 0} photos)
              </Link>
            ) : (
              <Link
                to={`/inspections/create/${job.id}/post`}
                className="inline-block text-sm bg-obatek/10 text-obatek px-3 py-1 rounded hover:bg-obatek/20 transition-colors"
              >
                Create
              </Link>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
