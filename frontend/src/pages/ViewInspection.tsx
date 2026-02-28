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

  const inspectionType = inspection.type === 'pre' ? 'Pre-Inspection' : 'Post-Inspection';

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{inspectionType}</h1>
          {inspection.job && (
            <p className="text-gray-600">
              {inspection.job.client?.name} - {inspection.job.title}
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
                inspection.type === 'pre'
                  ? 'bg-blue-100 text-blue-700'
                  : 'bg-green-100 text-green-700'
              }`}
            >
              {inspectionType}
            </span>
            <span className="text-sm text-gray-500">
              {formatDate(inspection.date)}
            </span>
          </div>
        </div>

        {/* Common Fields */}
        <div className="p-4 border-b">
          <h3 className="text-lg font-semibold text-gray-900 mb-3">General Information</h3>
          <div className="space-y-2">
            <div>
              <span className="text-sm font-medium text-gray-700">Customer Name: </span>
              <span className="text-gray-600">{inspection.customer_name}</span>
            </div>
            <div>
              <span className="text-sm font-medium text-gray-700">Company Truck Required: </span>
              <span className="text-gray-600">
                {inspection.is_company_truck_required ? 'Yes' : 'No'}
              </span>
            </div>
          </div>
        </div>

        {/* Pre-Job Specific Fields */}
        {inspection.type === 'pre' && (
          <div className="p-4 border-b">
            <h3 className="text-lg font-semibold text-gray-900 mb-3">Pre-Job Details</h3>
            <div className="space-y-2">
              <div>
                <span className="text-sm font-medium text-gray-700">Materials Needed: </span>
                <span className="text-gray-600">{inspection.materials_needed ? 'Yes' : 'No'}</span>
              </div>
              {inspection.special_tools_needed && (
                <div>
                  <span className="text-sm font-medium text-gray-700">Special Tools Needed: </span>
                  <p className="text-gray-600 mt-1 whitespace-pre-wrap">{inspection.special_tools_needed}</p>
                </div>
              )}
              {inspection.existing_damage_notes && (
                <div>
                  <span className="text-sm font-medium text-gray-700">Existing Damage Notes: </span>
                  <p className="text-gray-600 mt-1 whitespace-pre-wrap">{inspection.existing_damage_notes}</p>
                </div>
              )}
              {inspection.flooring_protection_needed && (
                <div>
                  <span className="text-sm font-medium text-gray-700">Flooring Protection Needed: </span>
                  <p className="text-gray-600 mt-1 whitespace-pre-wrap">{inspection.flooring_protection_needed}</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Post-Job Specific Fields */}
        {inspection.type === 'post' && (
          <div className="p-4 border-b">
            <h3 className="text-lg font-semibold text-gray-900 mb-3">Post-Job Details</h3>
            <div className="space-y-2">
              <div>
                <span className="text-sm font-medium text-gray-700">Dump Run Required: </span>
                <span className="text-gray-600">{inspection.dump_run_required ? 'Yes' : 'No'}</span>
              </div>
              {inspection.customer_keeping_materials && (
                <div>
                  <span className="text-sm font-medium text-gray-700">Customer Keeping Materials: </span>
                  <p className="text-gray-600 mt-1 whitespace-pre-wrap">{inspection.customer_keeping_materials}</p>
                </div>
              )}
              {inspection.materials_to_return && (
                <div>
                  <span className="text-sm font-medium text-gray-700">Materials to Return: </span>
                  <p className="text-gray-600 mt-1 whitespace-pre-wrap">{inspection.materials_to_return}</p>
                </div>
              )}
              {inspection.inventory_used && (
                <div>
                  <span className="text-sm font-medium text-gray-700">Inventory Used: </span>
                  <p className="text-gray-600 mt-1 whitespace-pre-wrap">{inspection.inventory_used}</p>
                </div>
              )}
              {inspection.pickup_required && (
                <div>
                  <span className="text-sm font-medium text-gray-700">Pickup Required: </span>
                  <p className="text-gray-600 mt-1 whitespace-pre-wrap">{inspection.pickup_required}</p>
                </div>
              )}
              {inspection.damages_or_quality_concerns && (
                <div>
                  <span className="text-sm font-medium text-gray-700">Damages or Quality Concerns: </span>
                  <p className="text-gray-600 mt-1 whitespace-pre-wrap">{inspection.damages_or_quality_concerns}</p>
                </div>
              )}
              {inspection.scope_change_notes && (
                <div>
                  <span className="text-sm font-medium text-gray-700">Scope Change Notes: </span>
                  <p className="text-gray-600 mt-1 whitespace-pre-wrap">{inspection.scope_change_notes}</p>
                </div>
              )}
            </div>
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
