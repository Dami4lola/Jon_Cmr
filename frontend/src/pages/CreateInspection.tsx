import { useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { jobsApi } from '../api/jobs';
import { inspectionsApi } from '../api/inspections';

export function CreateInspection() {
  const { jobId, type } = useParams<{ jobId: string; type: 'pre' | 'post' }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [notes, setNotes] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [previews, setPreviews] = useState<string[]>([]);

  // Fetch job details
  const { data: job, isLoading: loadingJob } = useQuery({
    queryKey: ['jobs', jobId],
    queryFn: () => jobsApi.get(Number(jobId)),
    enabled: !!jobId,
  });

  // Create inspection mutation
  const createMutation = useMutation({
    mutationFn: async () => {
      // First create the inspection
      const inspection = await inspectionsApi.create(
        Number(jobId),
        type as 'pre' | 'post',
        { notes: notes || undefined }
      );

      // Then upload photos if any
      if (files.length > 0) {
        await inspectionsApi.uploadPhotos(inspection.id, files);
      }

      return inspection;
    },
    onSuccess: (inspection) => {
      queryClient.invalidateQueries({ queryKey: ['inspections'] });
      navigate(`/inspections/${inspection.id}`);
    },
  });

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(e.target.files || []);
    if (selectedFiles.length === 0) return;

    // Add to existing files
    setFiles((prev) => [...prev, ...selectedFiles]);

    // Create previews
    selectedFiles.forEach((file) => {
      const reader = new FileReader();
      reader.onloadend = () => {
        setPreviews((prev) => [...prev, reader.result as string]);
      };
      reader.readAsDataURL(file);
    });
  };

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
    setPreviews((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    createMutation.mutate();
  };

  if (loadingJob) {
    return (
      <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
        Loading...
      </div>
    );
  }

  if (!job) {
    return (
      <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
        Job not found.
      </div>
    );
  }

  const inspectionType = type === 'pre' ? 'Pre-Inspection' : 'Post-Inspection';

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">{inspectionType}</h1>
        <p className="text-gray-600">
          {job.client?.name} - {job.description}
        </p>
      </div>

      <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-6 space-y-6">
        {createMutation.isError && (
          <div className="bg-red-50 text-red-600 p-3 rounded-lg text-sm">
            Failed to create inspection. Please try again.
          </div>
        )}

        {/* Notes */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Notes (optional)
          </label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={4}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none resize-none"
            placeholder="Add any notes about the inspection..."
          />
        </div>

        {/* Photo Upload */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Photos
          </label>

          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            multiple
            onChange={handleFileSelect}
            className="hidden"
          />

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            {previews.map((preview, index) => (
              <div key={index} className="relative group">
                <img
                  src={preview}
                  alt={`Preview ${index + 1}`}
                  className="w-full h-32 object-cover rounded-lg"
                />
                <button
                  type="button"
                  onClick={() => removeFile(index)}
                  className="absolute top-2 right-2 bg-red-500 text-white w-6 h-6 rounded-full opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            ))}

            {/* Add Photo Button */}
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="w-full h-32 border-2 border-dashed border-gray-300 rounded-lg flex flex-col items-center justify-center text-gray-500 hover:border-obatek hover:text-obatek transition-colors"
            >
              <svg className="w-8 h-8 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              <span className="text-sm">Add Photo</span>
            </button>
          </div>

          <p className="text-sm text-gray-500">
            {files.length} photo{files.length !== 1 ? 's' : ''} selected
          </p>
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={() => navigate('/inspections')}
            className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={createMutation.isPending}
            className="bg-obatek text-white px-6 py-2 rounded-lg font-medium hover:bg-obatek-dark transition-colors disabled:opacity-50"
          >
            {createMutation.isPending ? 'Creating...' : 'Create Inspection'}
          </button>
        </div>
      </form>
    </div>
  );
}
