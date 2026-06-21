import React, { useState, useEffect } from 'react';
import { Plus, Save, Zap, AlertCircle, CheckCircle } from 'lucide-react';
import { api } from '../../services/api';

interface Action {
  id: string;
  name: string;
  trigger: string;
  is_active: boolean;
  code: string;
}

export const ActionsSettings: React.FC = () => {
  const [actions, setActions] = useState<Action[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  
  // Editor state
  const [editingId, setEditingId] = useState<string | null>(null);
  const [name, setName] = useState('');
  const [trigger, setTrigger] = useState('post-login');
  const [code, setCode] = useState('');
  const [isActive, setIsActive] = useState(true);

  const defaultCode = `/**
 * @param {Event} event - Details about the user and the context in which they are logging in.
 * @param {PostLoginAPI} api - Interface whose methods can be used to change the behavior of the login.
 */
function onExecutePostLogin(event, api) {
  // Example: Add a custom claim to the ID token
  // api.idToken.setCustomClaim("my_custom_claim", "hello world");
  
  // Example: Deny access if email doesn't end with @example.com
  // if (!event.user.email.endsWith('@example.com')) {
  //   api.access.deny("Only @example.com users are allowed.");
  // }
}
`;

  const fetchActions = async () => {
    try {
      const res = await api.get('/api/v1/auth/organizations/actions');
      if (res.success) {
        setActions(res.data);
      }
    } catch (err: unknown) {
      setError('Failed to fetch actions: ' + (err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchActions();
  }, []);

  const handleCreateNew = () => {
    setEditingId('new');
    setName('New Action');
    setTrigger('post-login');
    setCode(defaultCode);
    setIsActive(true);
    setError('');
    setSuccess('');
  };

  const handleEdit = (action: Action) => {
    setEditingId(action.id);
    setName(action.name);
    setTrigger(action.trigger);
    setCode(action.code);
    setIsActive(action.is_active);
    setError('');
    setSuccess('');
  };

  const handleSave = async () => {
    setError('');
    setSuccess('');
    try {
      if (editingId === 'new') {
        await api.post('/api/v1/auth/organizations/actions', {
          name, trigger, code
        });
        setSuccess('Action created successfully.');
      } else {
        await api.put(`/api/v1/auth/organizations/actions/${editingId}`, {
          name, trigger, code, is_active: isActive
        });
        setSuccess('Action updated successfully.');
      }
      setEditingId(null);
      fetchActions();
    } catch (err: unknown) {
      setError((err as Error).message || 'Failed to save action');
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this action?')) return;
    setError('');
    try {
      await api.delete(`/api/v1/auth/organizations/actions/${id}`);
      setSuccess('Action deleted.');
      fetchActions();
    } catch (err: unknown) {
      setError((err as Error).message || 'Failed to delete action');
    }
  };

  if (loading) return <div>Loading actions...</div>;

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-xl font-semibold mb-1 flex items-center gap-2">
            <Zap className="text-yellow-500" /> Serverless Actions
          </h2>
          <p className="text-sm text-gray-500">
            Write custom JavaScript to extend auth workflows.
          </p>
        </div>
        {!editingId && (
          <button onClick={handleCreateNew} className="btn btn-primary flex items-center gap-2">
            <Plus size={16} /> Create Action
          </button>
        )}
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 text-red-700 border border-red-200 rounded-md flex items-center gap-2">
          <AlertCircle size={18} /> {error}
        </div>
      )}
      
      {success && (
        <div className="mb-4 p-3 bg-green-50 text-green-700 border border-green-200 rounded-md flex items-center gap-2">
          <CheckCircle size={18} /> {success}
        </div>
      )}

      {editingId ? (
        <div className="bg-white border rounded-lg shadow-sm p-4">
          <div className="flex justify-between items-center mb-4">
            <h3 className="font-medium text-lg">{editingId === 'new' ? 'New Action' : 'Edit Action'}</h3>
            <div className="flex gap-2">
              <button onClick={() => setEditingId(null)} className="btn btn-secondary">Cancel</button>
              <button onClick={handleSave} className="btn btn-primary flex items-center gap-2">
                <Save size={16} /> Save
              </button>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <label htmlFor="actionName" className="block text-sm font-medium text-gray-700 mb-1">Action Name</label>
              <input 
                id="actionName"
                type="text" 
                className="w-full p-2 border rounded-md"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Trigger</label>
              <select 
                className="w-full p-2 border rounded-md bg-gray-50"
                value={trigger}
                disabled
              >
                <option value="post-login">Post Login (Execute after authentication)</option>
              </select>
            </div>
          </div>

          <fieldset className="mb-4">
            <legend className="block text-sm font-medium text-gray-700 mb-1">Status</legend>
            <label className="flex items-center gap-2 cursor-pointer">
              <input 
                type="checkbox" 
                checked={isActive}
                onChange={(e) => setIsActive(e.target.checked)}
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                aria-label="Active status"
              />
              <span className="text-sm">Active</span>
            </label>
          </fieldset>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1 flex justify-between">
              <span>JavaScript Code</span>
              <span className="text-xs text-gray-500">Node.js (V8 engine)</span>
            </label>
            <textarea 
              value={code}
              onChange={(e) => setCode(e.target.value)}
              className="w-full h-64 p-3 border rounded-md font-mono text-sm bg-gray-50"
              style={{ whiteSpace: 'pre', overflowWrap: 'normal', overflowX: 'scroll' }}
              spellCheck="false"
            />
          </div>
        </div>
      ) : (
        <div className="bg-white border rounded-lg shadow-sm overflow-hidden">
          {actions.length === 0 ? (
            <div className="p-8 text-center text-gray-500">
              No actions created yet. Create one to customize your login flow.
            </div>
          ) : (
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Trigger</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {actions.map((action) => (
                  <tr key={action.id}>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="font-medium text-gray-900">{action.name}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-blue-100 text-blue-800">
                        {action.trigger}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {action.is_active ? (
                        <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800">Active</span>
                      ) : (
                        <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-gray-100 text-gray-800">Inactive</span>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <button 
                        onClick={() => handleEdit(action)}
                        className="text-blue-600 hover:text-blue-900 mr-4"
                      >
                        Edit
                      </button>
                      <button 
                        onClick={() => handleDelete(action.id)}
                        className="text-red-600 hover:text-red-900"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
};
