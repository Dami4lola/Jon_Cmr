import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { inspectionsApi } from '../api/inspections';
import { formatDate } from '../lib/utils';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export function ViewInspection() {
  const { id } = useParams<{ id: string }>();

  const { data: inspection, isLoading, error } = useQuery({
    queryKey: ['inspections', id],
    queryFn: () => inspectionsApi.get(Number(id)),
    enabled: !!id,
  });

  if (isLoading) {
    return (
      <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
        Loading...
      </div>
    );
  }

  if (error || !inspection) {
    return (
      <div className="bg-white rounded-lg shadow p-8 text-center">
        <p className="text-gray-500 mb-4">Inspection not found.</p>
        <Link to="/inspections" className="text-obatek hover:underline">
          Back to Inspections
        </Link>
      </div>
    );
  }

  const inspectionType = inspection.inspection_type === 'pre' ? 'Pre-Inspection' : 'Post-Inspection';

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{inspectionType}</h1>
          {inspection.job && (
            <p className="text-gray-600">
              {inspection.job.client?.name} - {inspection.job.description}
            </p>
          )}
        </div>
        <Link
          to="/inspections"
          className="text-obatek hover:underline flex items-center gap-1"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Back
        </Link>
      </div>

      <div className="bg-white rounded-lg shadow">
        {/* Info */}
        <div className="p-4 border-b">
          <div className="flex items-center justify-between">
            <span
              className={`px-3 py-1 rounded-full text-sm font-medium ${
                inspection.inspection_type === 'pre'
                  ? 'bg-blue-100 text-blue-700'
                  : 'bg-green-100 text-green-700'
              }`}
            >
              {inspectionType}
            </span>
            <span className="text-sm text-gray-500">
              Created {formatDate(inspection.created_at)}
            </span>
          </div>
        </div>

        {/* Notes */}
        {inspection.notes && (
          <div className="p-4 border-b">
            <h3 className="text-sm font-medium text-gray-700 mb-2">Notes</h3>
            <p className="text-gray-600 whitespace-pre-wrap">{inspection.notes}</p>
          </div>
        )}

        {/* Photos */}
        <div className="p-4">
          <h3 className="text-sm font-medium text-gray-700 mb-3">
            Photos ({inspection.photos?.length || 0})
          </h3>

          {(!inspection.photos || inspection.photos.length === 0) ? (
            <p className="text-gray-500 text-sm">No photos attached.</p>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {inspection.photos.map((photo) => (
                <a
                  key={photo.id}
                  href={`${API_URL}${photo.image_path}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block group"
                >
                  <div className="relative aspect-square rounded-lg overflow-hidden bg-gray-100">
                    <img
                      src={`${API_URL}${photo.image_path}`}
                      alt={photo.caption || 'Inspection photo'}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform"
                    />
                    <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors flex items-center justify-center">
                      <svg
                        className="w-8 h-8 text-white opacity-0 group-hover:opacity-100 transition-opacity"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7"
                        />
                      </svg>
                    </div>
                  </div>
                  {photo.caption && (
                    <p className="mt-1 text-sm text-gray-600 truncate">
                      {photo.caption}
                    </p>
                  )}
                </a>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
