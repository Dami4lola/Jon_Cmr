import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { clientsApi, ClientCreate } from '../api/clients';
import { Client } from '../types';

const EMPTY_FORM: ClientCreate = {
  name: '',
  phone_number: '',
  email: '',
  address: '',
};

export function Clients() {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [editingClient, setEditingClient] = useState<Client | null>(null);
  const [formData, setFormData] = useState<ClientCreate>(EMPTY_FORM);
  const [editFormData, setEditFormData] = useState<ClientCreate>(EMPTY_FORM);

  const { data: clients = [], isLoading } = useQuery({
    queryKey: ['clients'],
    queryFn: clientsApi.list,
  });

  const createMutation = useMutation({
    mutationFn: clientsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['clients'] });
      resetCreateForm();
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<ClientCreate> }) =>
      clientsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['clients'] });
      setEditingClient(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: clientsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['clients'] });
    },
    onError: (error: any) => {
      alert(error?.response?.data?.detail || 'Failed to delete client. Please try again.');
    },
  });

  const resetCreateForm = () => {
    setShowCreate(false);
    setFormData(EMPTY_FORM);
  };

  const handleCreateSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name.trim() || !formData.address.trim()) {
      return;
    }
    createMutation.mutate({
      ...formData,
      phone_number: formData.phone_number?.trim() || undefined,
      email: formData.email?.trim() || undefined,
    });
  };

  const handleEditClient = (client: Client) => {
    setEditingClient(client);
    setEditFormData({
      name: client.name,
      phone_number: client.phone_number || '',
      email: client.email || '',
      address: client.address,
    });
  };

  const handleSaveClient = () => {
    if (!editingClient) return;
    if (!editFormData.name.trim() || !editFormData.address.trim()) {
      return;
    }
    updateMutation.mutate({
      id: editingClient.id,
      data: {
        ...editFormData,
        phone_number: editFormData.phone_number?.trim() || undefined,
        email: editFormData.email?.trim() || undefined,
      },
    });
  };

  const handleDeleteClient = (client: Client) => {
    if (window.confirm(`Permanently delete ${client.name}? This cannot be undone.`)) {
      deleteMutation.mutate(client.id);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Clients</h1>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="bg-obatek text-white px-4 py-2 rounded-lg font-medium hover:bg-obatek-dark transition-colors"
        >
          {showCreate ? 'Cancel' : 'Create Client'}
        </button>
      </div>

      {/* Create Client Form */}
      {showCreate && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold mb-4">Create New Client</h2>
          <form onSubmit={handleCreateSubmit} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Name *
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                  placeholder="Client name"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Phone Number
                </label>
                <input
                  type="text"
                  value={formData.phone_number}
                  onChange={(e) => setFormData({ ...formData, phone_number: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                  placeholder="Phone number"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Email
                </label>
                <input
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                  placeholder="email@example.com"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Address *
                </label>
                <input
                  type="text"
                  value={formData.address}
                  onChange={(e) => setFormData({ ...formData, address: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                  placeholder="Job location address"
                  required
                />
              </div>
            </div>

            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={resetCreateForm}
                className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={createMutation.isPending}
                className="bg-obatek text-white px-6 py-2 rounded-lg font-medium hover:bg-obatek-dark transition-colors disabled:opacity-50"
              >
                {createMutation.isPending ? 'Creating...' : 'Create Client'}
              </button>
            </div>

            {createMutation.isError && (
              <p className="text-red-500 text-sm">
                Error: {(createMutation.error as any)?.response?.data?.detail || 'Failed to create client'}
              </p>
            )}
          </form>
        </div>
      )}

      {/* Edit Client Modal */}
      {editingClient && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-lg mx-4">
            <h2 className="text-lg font-semibold mb-4">Edit Client: {editingClient.name}</h2>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Name *
                </label>
                <input
                  type="text"
                  value={editFormData.name}
                  onChange={(e) => setEditFormData({ ...editFormData, name: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Phone Number
                </label>
                <input
                  type="text"
                  value={editFormData.phone_number}
                  onChange={(e) => setEditFormData({ ...editFormData, phone_number: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Email
                </label>
                <input
                  type="email"
                  value={editFormData.email}
                  onChange={(e) => setEditFormData({ ...editFormData, email: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Address *
                </label>
                <input
                  type="text"
                  value={editFormData.address}
                  onChange={(e) => setEditFormData({ ...editFormData, address: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                  required
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 mt-6">
              <button
                onClick={() => setEditingClient(null)}
                className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveClient}
                disabled={updateMutation.isPending}
                className="bg-obatek text-white px-6 py-2 rounded-lg font-medium hover:bg-obatek-dark transition-colors disabled:opacity-50"
              >
                {updateMutation.isPending ? 'Saving...' : 'Save Changes'}
              </button>
            </div>

            {updateMutation.isError && (
              <p className="text-red-500 text-sm mt-2">
                Error: {(updateMutation.error as any)?.response?.data?.detail || 'Failed to update client'}
              </p>
            )}
          </div>
        </div>
      )}

      {/* Clients Table */}
      <div className="bg-white rounded-lg shadow">
        <div className="p-4 border-b">
          <h2 className="text-lg font-semibold">All Clients</h2>
        </div>
        {isLoading ? (
          <div className="p-8 text-center text-gray-500">Loading...</div>
        ) : clients.length === 0 ? (
          <div className="p-8 text-center text-gray-500">No clients found.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Name
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Phone
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Email
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Address
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {clients.map((client) => (
                  <tr key={client.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">{client.name}</td>
                    <td className="px-4 py-3 text-sm text-gray-600">{client.phone_number || '-'}</td>
                    <td className="px-4 py-3 text-sm text-gray-600">{client.email || '-'}</td>
                    <td className="px-4 py-3 text-sm text-gray-600">{client.address}</td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex justify-end gap-3">
                        <button
                          onClick={() => handleEditClient(client)}
                          className="text-sm text-obatek hover:underline"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => handleDeleteClient(client)}
                          disabled={deleteMutation.isPending}
                          className="text-sm text-red-700 hover:underline"
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
