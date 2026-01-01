import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useCriteria, useDeleteCriteria, useMoveCriteria, type CriteriaEntry } from '../hooks/useCriteria';

type CriteriaType = 'delete' | 'delete1d' | 'keep';

const tabs: { type: CriteriaType; label: string; color: string }[] = [
  { type: 'delete', label: 'Delete', color: 'red' },
  { type: 'delete1d', label: 'Delete 1-Day', color: 'orange' },
  { type: 'keep', label: 'Keep', color: 'green' }
];

export default function CriteriaManager() {
  const { type = 'delete' } = useParams<{ type: CriteriaType }>();
  const navigate = useNavigate();
  const [search, setSearch] = useState('');

  const { data, isLoading } = useCriteria();
  const deleteMutation = useDeleteCriteria();
  const moveMutation = useMoveCriteria();

  const activeType = type as CriteriaType;

  const getCriteriaList = (): CriteriaEntry[] => {
    if (!data) return [];
    switch (activeType) {
      case 'delete': return data.delete;
      case 'delete1d': return data.delete1d;
      case 'keep': return data.keep;
      default: return [];
    }
  };

  const criteria = getCriteriaList();
  const filtered = search
    ? criteria.filter(c =>
        c.primaryDomain.toLowerCase().includes(search.toLowerCase()) ||
        c.subject.toLowerCase().includes(search.toLowerCase())
      )
    : criteria;

  const handleDelete = (index: number) => {
    if (confirm('Delete this criteria entry?')) {
      deleteMutation.mutate({ type: activeType, index });
    }
  };

  const handleMove = (index: number, toType: CriteriaType) => {
    moveMutation.mutate({ fromType: activeType, toType, index });
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-lg text-gray-500">Loading criteria...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-800">Criteria Manager</h1>

      {/* Tabs */}
      <div className="flex gap-2">
        {tabs.map(tab => (
          <button
            key={tab.type}
            onClick={() => navigate(`/criteria/${tab.type}`)}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${
              activeType === tab.type
                ? `bg-${tab.color}-500 text-white`
                : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'
            }`}
            style={activeType === tab.type ? {
              backgroundColor: tab.color === 'red' ? '#ef4444' :
                               tab.color === 'orange' ? '#f97316' : '#22c55e'
            } : {}}
          >
            {tab.label} ({
              tab.type === 'delete' ? data?.delete.length :
              tab.type === 'delete1d' ? data?.delete1d.length :
              data?.keep.length
            })
          </button>
        ))}
      </div>

      {/* Search */}
      <div className="flex gap-4">
        <input
          type="text"
          placeholder="Search domain or subject..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </div>

      {/* Table */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">Domain</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">Subject</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">Exclude</th>
              <th className="px-4 py-3 text-right text-sm font-medium text-gray-700">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-gray-500">
                  No criteria entries found.
                </td>
              </tr>
            ) : (
              filtered.map((entry, idx) => (
                <tr key={idx} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm text-gray-900">{entry.primaryDomain}</td>
                  <td className="px-4 py-3 text-sm text-gray-700">
                    {entry.subject || <span className="text-gray-400">(all)</span>}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {entry.excludeSubject || '-'}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex justify-end gap-2">
                      {/* Move dropdown */}
                      <select
                        onChange={e => {
                          if (e.target.value) {
                            handleMove(idx, e.target.value as CriteriaType);
                            e.target.value = '';
                          }
                        }}
                        className="text-sm border border-gray-300 rounded px-2 py-1"
                        defaultValue=""
                      >
                        <option value="" disabled>Move to...</option>
                        {activeType !== 'delete' && <option value="delete">Delete</option>}
                        {activeType !== 'delete1d' && <option value="delete1d">Delete 1-Day</option>}
                        {activeType !== 'keep' && <option value="keep">Keep</option>}
                      </select>

                      <button
                        onClick={() => handleDelete(idx)}
                        className="px-2 py-1 text-sm text-red-600 hover:bg-red-50 rounded"
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="text-sm text-gray-500">
        Showing {filtered.length} of {criteria.length} entries
      </div>
    </div>
  );
}
