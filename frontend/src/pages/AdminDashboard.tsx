import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { usersApi, AdminCreateUserData, UserWithWorker } from '../api/users';
import { workersApi, WorkerUpdate } from '../api/workers';

const AVAILABLE_ROLES = ['worker', 'manager', 'admin'] as const;

interface EditUserFormData {
  roles: string[];
  hourly_rate: number;
  charges_hst: boolean;
  is_employee: boolean;
}

export function AdminDashboard() {
  const queryClient = useQueryClient();
  const [showCreateUser, setShowCreateUser] = useState(false);
  const [editingUser, setEditingUser] = useState<UserWithWorker | null>(null);
  const [resetPasswordUser, setResetPasswordUser] = useState<UserWithWorker | null>(null);
  const [newPassword, setNewPassword] = useState('');
  const [resetSuccess, setResetSuccess] = useState('');
  const [editFormData, setEditFormData] = useState<EditUserFormData>({
    roles: ['worker'],
    hourly_rate: 0,
    charges_hst: false,
    is_employee: false,
  });
  const [formData, setFormData] = useState<AdminCreateUserData>({
    username: '',
    email: '',
    password: '',
    name: '',
    hourly_rate: 0,
    charges_hst: false,
    is_employee: false,
    roles: ['worker'],
  });

  // Fetch all users
  const { data: users = [], isLoading } = useQuery({
    queryKey: ['users'],
    queryFn: usersApi.list,
  });

  // Create user mutation
  const createUserMutation = useMutation({
    mutationFn: usersApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      resetForm();
    },
  });

  // Update roles mutation
  const updateRolesMutation = useMutation({
    mutationFn: ({ id, roles }: { id: number; roles: string[] }) =>
      usersApi.updateRoles(id, { roles }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
    },
  });

  // Toggle active mutation
  const toggleActiveMutation = useMutation({
    mutationFn: usersApi.toggleActive,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
    },
  });

  // Reset password mutation
  const resetPasswordMutation = useMutation({
    mutationFn: ({ id, newPassword }: { id: number; newPassword: string }) =>
      usersApi.resetPassword(id, newPassword),
    onSuccess: (data) => {
      setResetSuccess(data.message);
      setNewPassword('');
    },
  });

  // Update worker mutation
  const updateWorkerMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: WorkerUpdate }) =>
      workersApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
    },
  });

  const resetForm = () => {
    setShowCreateUser(false);
    setFormData({
      username: '',
      email: '',
      password: '',
      name: '',
      hourly_rate: 0,
      charges_hst: false,
      is_employee: false,
      roles: ['worker'],
    });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.username.trim() || !formData.email.trim() || !formData.password || !formData.name.trim()) {
      return;
    }
    createUserMutation.mutate(formData);
  };

  const handleRoleToggle = (role: string, isForCreate: boolean = true) => {
    if (isForCreate) {
      setFormData((prev) => {
        const currentRoles = prev.roles;
        if (currentRoles.includes(role)) {
          const newRoles = currentRoles.filter((r) => r !== role);
          return { ...prev, roles: newRoles.length ? newRoles : ['worker'] };
        } else {
          return { ...prev, roles: [...currentRoles, role] };
        }
      });
    } else {
      setEditFormData((prev) => {
        const currentRoles = prev.roles;
        if (currentRoles.includes(role)) {
          const newRoles = currentRoles.filter((r) => r !== role);
          return { ...prev, roles: newRoles.length ? newRoles : ['worker'] };
        } else {
          return { ...prev, roles: [...currentRoles, role] };
        }
      });
    }
  };

  const handleEditUser = (user: UserWithWorker) => {
    setEditingUser(user);
    setEditFormData({
      roles: [...user.roles],
      hourly_rate: user.hourly_rate || 0,
      charges_hst: user.charges_hst || false,
      is_employee: user.is_employee || false,
    });
  };

  const handleSaveUser = async () => {
    if (!editingUser) return;

    try {
      // Update roles if changed
      const rolesChanged = JSON.stringify([...editingUser.roles].sort()) !== JSON.stringify([...editFormData.roles].sort());
      if (rolesChanged) {
        await updateRolesMutation.mutateAsync({ id: editingUser.id, roles: editFormData.roles });
      }

      // Update worker details if user has a worker profile
      if (editingUser.worker_id) {
        const workerChanged =
          editFormData.hourly_rate !== (editingUser.hourly_rate || 0) ||
          editFormData.charges_hst !== (editingUser.charges_hst || false) ||
          editFormData.is_employee !== (editingUser.is_employee || false);

        if (workerChanged) {
          await updateWorkerMutation.mutateAsync({
            id: editingUser.worker_id,
            data: {
              hourly_rate: editFormData.hourly_rate,
              charges_hst: editFormData.charges_hst,
              is_employee: editFormData.is_employee,
            },
          });
        }
      }

      setEditingUser(null);
    } catch {
      // Errors handled by mutations
    }
  };

  const isSaving = updateRolesMutation.isPending || updateWorkerMutation.isPending;

  const getRoleBadgeColor = (role: string) => {
    switch (role) {
      case 'admin':
        return 'bg-red-100 text-red-800';
      case 'manager':
        return 'bg-blue-100 text-blue-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Admin Dashboard</h1>
        <button
          onClick={() => setShowCreateUser(!showCreateUser)}
          className="bg-obatek text-white px-4 py-2 rounded-lg font-medium hover:bg-obatek-dark transition-colors"
        >
          {showCreateUser ? 'Cancel' : 'Create User'}
        </button>
      </div>

      {/* Create User Form */}
      {showCreateUser && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold mb-4">Create New User</h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Username *
                </label>
                <input
                  type="text"
                  value={formData.username}
                  onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                  placeholder="Username"
                  autoComplete="off"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Email *
                </label>
                <input
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                  placeholder="email@example.com"
                  required
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Full Name *
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                  placeholder="Full Name"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Password *
                </label>
                <input
                  type="password"
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                  placeholder="Minimum 6 characters"
                  autoComplete="new-password"
                  minLength={6}
                  required
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Hourly Rate ($)
                </label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={formData.hourly_rate || ''}
                  onChange={(e) => setFormData({ ...formData, hourly_rate: parseFloat(e.target.value) || 0 })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                  placeholder="e.g. 25.00"
                />
              </div>
              <div className="flex items-center pt-6">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.charges_hst}
                    onChange={(e) => setFormData({ ...formData, charges_hst: e.target.checked })}
                    className="w-4 h-4 text-obatek rounded focus:ring-obatek"
                  />
                  <span className="text-sm text-gray-700">Charges HST</span>
                </label>
              </div>
              <div className="flex items-center pt-6">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.is_employee}
                    onChange={(e) => setFormData({ ...formData, is_employee: e.target.checked })}
                    className="w-4 h-4 text-obatek rounded focus:ring-obatek"
                  />
                  <span className="text-sm text-gray-700">Is Employee</span>
                </label>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Assign Roles *
              </label>
              <div className="flex flex-wrap gap-2">
                {AVAILABLE_ROLES.map((role) => (
                  <label
                    key={role}
                    className={`flex items-center gap-2 px-3 py-2 border rounded-lg cursor-pointer transition-colors ${
                      formData.roles.includes(role)
                        ? 'bg-obatek/10 border-obatek text-obatek'
                        : 'border-gray-300 hover:border-gray-400'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={formData.roles.includes(role)}
                      onChange={() => handleRoleToggle(role, true)}
                      className="sr-only"
                    />
                    <span className="text-sm capitalize">{role}</span>
                  </label>
                ))}
              </div>
            </div>

            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={resetForm}
                className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={createUserMutation.isPending}
                className="bg-obatek text-white px-6 py-2 rounded-lg font-medium hover:bg-obatek-dark transition-colors disabled:opacity-50"
              >
                {createUserMutation.isPending ? 'Creating...' : 'Create User'}
              </button>
            </div>

            {createUserMutation.isError && (
              <p className="text-red-500 text-sm">
                Error: {(createUserMutation.error as Error)?.message || 'Failed to create user'}
              </p>
            )}
          </form>
        </div>
      )}

      {/* Edit User Modal */}
      {editingUser && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-lg mx-4">
            <h2 className="text-lg font-semibold mb-4">
              Edit User: {editingUser.worker_name || editingUser.username}
            </h2>

            <div className="space-y-6">
              {/* Roles Section */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Roles
                </label>
                <div className="flex flex-wrap gap-2">
                  {AVAILABLE_ROLES.map((role) => (
                    <label
                      key={role}
                      className={`flex items-center gap-2 px-4 py-2 border rounded-lg cursor-pointer transition-colors ${
                        editFormData.roles.includes(role)
                          ? 'bg-obatek/10 border-obatek text-obatek'
                          : 'border-gray-300 hover:border-gray-400'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={editFormData.roles.includes(role)}
                        onChange={() => handleRoleToggle(role, false)}
                        className="sr-only"
                      />
                      <span className="text-sm capitalize">{role}</span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Worker Details Section */}
              {editingUser.worker_id && (
                <>
                  <div className="border-t pt-4">
                    <h3 className="text-sm font-medium text-gray-700 mb-3">Worker Details</h3>
                    <div className="space-y-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Hourly Rate ($)
                        </label>
                        <input
                          type="number"
                          step="0.01"
                          min="0"
                          value={editFormData.hourly_rate || ''}
                          onChange={(e) => setEditFormData({ ...editFormData, hourly_rate: parseFloat(e.target.value) || 0 })}
                          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                          placeholder="e.g. 25.00"
                        />
                      </div>
                      <div className="flex items-center gap-6">
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={editFormData.charges_hst}
                            onChange={(e) => setEditFormData({ ...editFormData, charges_hst: e.target.checked })}
                            className="w-4 h-4 text-obatek rounded focus:ring-obatek"
                          />
                          <span className="text-sm text-gray-700">Charges HST</span>
                        </label>
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={editFormData.is_employee}
                            onChange={(e) => setEditFormData({ ...editFormData, is_employee: e.target.checked })}
                            className="w-4 h-4 text-obatek rounded focus:ring-obatek"
                          />
                          <span className="text-sm text-gray-700">Is Employee</span>
                        </label>
                      </div>
                    </div>
                  </div>
                </>
              )}
            </div>

            <div className="flex justify-end gap-2 mt-6">
              <button
                onClick={() => setEditingUser(null)}
                className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveUser}
                disabled={isSaving}
                className="bg-obatek text-white px-6 py-2 rounded-lg font-medium hover:bg-obatek-dark transition-colors disabled:opacity-50"
              >
                {isSaving ? 'Saving...' : 'Save Changes'}
              </button>
            </div>

            {(updateRolesMutation.isError || updateWorkerMutation.isError) && (
              <p className="text-red-500 text-sm mt-2">
                Error: Failed to update user
              </p>
            )}
          </div>
        </div>
      )}

      {/* Reset Password Modal */}
      {resetPasswordUser && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-md mx-4">
            <h2 className="text-lg font-semibold mb-1">Reset Password</h2>
            <p className="text-sm text-gray-500 mb-4">
              Setting a new password for <span className="font-medium text-gray-700">{resetPasswordUser.worker_name || resetPasswordUser.username}</span>
            </p>

            {resetSuccess ? (
              <div className="bg-green-50 text-green-700 p-3 rounded-lg text-sm mb-4">
                {resetSuccess}
              </div>
            ) : (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">New Password</label>
                  <input
                    type="password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    autoComplete="new-password"
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                    placeholder="Minimum 6 characters"
                    minLength={6}
                  />
                </div>
                {resetPasswordMutation.isError && (
                  <p className="text-red-500 text-sm">Failed to reset password. Please try again.</p>
                )}
              </div>
            )}

            <div className="flex justify-end gap-2 mt-6">
              <button
                onClick={() => { setResetPasswordUser(null); setNewPassword(''); setResetSuccess(''); resetPasswordMutation.reset(); }}
                className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
              >
                {resetSuccess ? 'Close' : 'Cancel'}
              </button>
              {!resetSuccess && (
                <button
                  onClick={() => {
                    if (newPassword.length >= 6) {
                      resetPasswordMutation.mutate({ id: resetPasswordUser.id, newPassword });
                    }
                  }}
                  disabled={resetPasswordMutation.isPending || newPassword.length < 6}
                  className="bg-yellow-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-yellow-700 transition-colors disabled:opacity-50"
                >
                  {resetPasswordMutation.isPending ? 'Resetting...' : 'Reset Password'}
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-600">Total Users</p>
          <p className="text-2xl font-bold text-gray-900">{users.length}</p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-600">Admins</p>
          <p className="text-2xl font-bold text-red-600">
            {users.filter((u) => u.roles.includes('admin')).length}
          </p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-600">Managers</p>
          <p className="text-2xl font-bold text-blue-600">
            {users.filter((u) => u.roles.includes('manager') && !u.roles.includes('admin')).length}
          </p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-600">Active Users</p>
          <p className="text-2xl font-bold text-green-600">
            {users.filter((u) => u.is_active).length}
          </p>
        </div>
      </div>

      {/* Users Table */}
      <div className="bg-white rounded-lg shadow">
        <div className="p-4 border-b">
          <h2 className="text-lg font-semibold">All Users</h2>
        </div>
        {isLoading ? (
          <div className="p-8 text-center text-gray-500">Loading...</div>
        ) : users.length === 0 ? (
          <div className="p-8 text-center text-gray-500">No users found.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Name
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Username
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Email
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Roles
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    Hourly Rate
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">
                    Status
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {users.map((user) => (
                  <tr key={user.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">
                      {user.worker_name || '-'}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">{user.username}</td>
                    <td className="px-4 py-3 text-sm text-gray-600">{user.email}</td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1">
                        {user.roles.map((role) => (
                          <span
                            key={role}
                            className={`px-2 py-0.5 text-xs font-medium rounded-full capitalize ${getRoleBadgeColor(role)}`}
                          >
                            {role}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right text-sm text-gray-600">
                      {user.hourly_rate != null ? `$${user.hourly_rate.toFixed(2)}` : '-'}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span
                        className={`px-2 py-0.5 text-xs font-medium rounded-full ${
                          user.is_active
                            ? 'bg-green-100 text-green-800'
                            : 'bg-gray-100 text-gray-800'
                        }`}
                      >
                        {user.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex flex-col items-end gap-1">
                        <button
                          onClick={() => handleEditUser(user)}
                          className="text-sm text-obatek hover:underline"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => { setResetPasswordUser(user); setNewPassword(''); setResetSuccess(''); }}
                          className="text-sm text-yellow-600 hover:underline"
                        >
                          Reset Password
                        </button>
                        <button
                          onClick={() => toggleActiveMutation.mutate(user.id)}
                          disabled={toggleActiveMutation.isPending}
                          className={`text-sm hover:underline ${
                            user.is_active ? 'text-red-600' : 'text-green-600'
                          }`}
                        >
                          {user.is_active ? 'Deactivate' : 'Activate'}
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
