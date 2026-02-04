import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { purchasesApi } from '../api/purchases';
import { formatDate } from '../lib/utils';
import type { PurchaseItem, PurchaseItemCreate } from '../types';

export function PurchaseList() {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState<PurchaseItemCreate>({
    item_name: '',
    quantity: 1,
    notes: '',
  });

  // Fetch items
  const { data: items = [], isLoading } = useQuery({
    queryKey: ['purchases'],
    queryFn: () => purchasesApi.list(),
  });

  // Create mutation
  const createMutation = useMutation({
    mutationFn: purchasesApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['purchases'] });
      setShowForm(false);
      setFormData({ item_name: '', quantity: 1, notes: '' });
    },
  });

  // Mark purchased mutation
  const markPurchasedMutation = useMutation({
    mutationFn: purchasesApi.markPurchased,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['purchases'] });
    },
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: purchasesApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['purchases'] });
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.item_name.trim()) return;
    createMutation.mutate(formData);
  };

  const neededItems = items.filter((item: PurchaseItem) => !item.is_purchased);
  const purchasedItems = items.filter((item: PurchaseItem) => item.is_purchased);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Purchase List</h1>
        <button
          onClick={() => setShowForm(!showForm)}
          className="bg-obatek text-white px-4 py-2 rounded-lg font-medium hover:bg-obatek-dark transition-colors"
        >
          {showForm ? 'Cancel' : 'Add Item'}
        </button>
      </div>

      {/* Add Item Form */}
      {showForm && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold mb-4">Add Item to List</h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="md:col-span-2">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Item Name
                </label>
                <input
                  type="text"
                  value={formData.item_name}
                  onChange={(e) => setFormData({ ...formData, item_name: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                  placeholder="Enter item name"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Quantity
                </label>
                <input
                  type="number"
                  min="1"
                  value={formData.quantity || ''}
                  onChange={(e) => setFormData({ ...formData, quantity: parseInt(e.target.value) || 1 })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Notes (optional)
              </label>
              <input
                type="text"
                value={formData.notes || ''}
                onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                placeholder="Any additional notes..."
              />
            </div>
            <div className="flex justify-end">
              <button
                type="submit"
                disabled={createMutation.isPending}
                className="bg-obatek text-white px-6 py-2 rounded-lg font-medium hover:bg-obatek-dark transition-colors disabled:opacity-50"
              >
                {createMutation.isPending ? 'Adding...' : 'Add Item'}
              </button>
            </div>
          </form>
        </div>
      )}

      {isLoading ? (
        <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
          Loading...
        </div>
      ) : (
        <>
          {/* Items Needed */}
          <div className="bg-white rounded-lg shadow">
            <div className="p-4 border-b">
              <h2 className="text-lg font-semibold">Items Needed ({neededItems.length})</h2>
            </div>
            {neededItems.length === 0 ? (
              <div className="p-8 text-center text-gray-500">
                No items needed. Add something to the list!
              </div>
            ) : (
              <div className="divide-y">
                {neededItems.map((item: PurchaseItem) => (
                  <div key={item.id} className="p-4 hover:bg-gray-50 flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <button
                        onClick={() => markPurchasedMutation.mutate(item.id)}
                        disabled={markPurchasedMutation.isPending}
                        className="w-6 h-6 border-2 border-gray-300 rounded hover:border-obatek transition-colors flex items-center justify-center"
                        title="Mark as purchased"
                      >
                        {markPurchasedMutation.isPending && (
                          <span className="w-3 h-3 bg-obatek/30 rounded-full"></span>
                        )}
                      </button>
                      <div>
                        <p className="font-medium text-gray-900">
                          {item.item_name}
                          {item.quantity && item.quantity > 1 && (
                            <span className="text-gray-500 ml-2">x{item.quantity}</span>
                          )}
                        </p>
                        {item.notes && (
                          <p className="text-sm text-gray-500">{item.notes}</p>
                        )}
                        <p className="text-xs text-gray-400">
                          Added {formatDate(item.added_at)}
                        </p>
                      </div>
                    </div>
                    <button
                      onClick={() => {
                        if (confirm('Delete this item?')) {
                          deleteMutation.mutate(item.id);
                        }
                      }}
                      className="text-gray-400 hover:text-red-500 transition-colors"
                    >
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Recently Purchased */}
          {purchasedItems.length > 0 && (
            <div className="bg-white rounded-lg shadow">
              <div className="p-4 border-b">
                <h2 className="text-lg font-semibold text-gray-500">
                  Recently Purchased ({purchasedItems.length})
                </h2>
              </div>
              <div className="divide-y">
                {purchasedItems.slice(0, 10).map((item: PurchaseItem) => (
                  <div key={item.id} className="p-4 hover:bg-gray-50 flex items-center justify-between opacity-60">
                    <div className="flex items-center gap-4">
                      <div className="w-6 h-6 border-2 border-green-500 rounded bg-green-50 flex items-center justify-center">
                        <svg className="w-4 h-4 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                      </div>
                      <div>
                        <p className="font-medium text-gray-700 line-through">
                          {item.item_name}
                          {item.quantity && item.quantity > 1 && (
                            <span className="text-gray-400 ml-2">x{item.quantity}</span>
                          )}
                        </p>
                        {item.purchased_at && (
                          <p className="text-xs text-gray-400">
                            Purchased {formatDate(item.purchased_at)}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
