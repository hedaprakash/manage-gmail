import { useState } from 'react';
import { useEmails, useMarkKeep, useAddCriteria, useAddCriteria1d, formatDateRange } from '../hooks/useEmails';
import StatsCard from '../components/Stats/StatsCard';
import DomainSection from '../components/Email/DomainSection';

const categories = ['All', 'PROMO', 'NEWSLETTER', 'UNKNOWN', 'SECURITY', 'ALERT', 'STATEMENT', 'ORDER'];

export default function Review() {
  const [categoryFilter, setCategoryFilter] = useState('All');
  const { data, isLoading, error } = useEmails();
  const markKeep = useMarkKeep();
  const addCriteria = useAddCriteria();
  const addCriteria1d = useAddCriteria1d();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-lg text-gray-500">Loading emails...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6 text-center">
        <h2 className="text-lg font-semibold text-yellow-800 mb-2">No Cached Emails</h2>
        <p className="text-yellow-700 mb-4">
          {error instanceof Error ? error.message : 'Click "Refresh from Gmail" to fetch emails.'}
        </p>
      </div>
    );
  }

  if (!data) return null;

  // Filter domains by category if needed
  const filteredDomains = categoryFilter === 'All'
    ? data.domains
    : data.domains.map(d => ({
        ...d,
        patterns: d.patterns.filter(p => p.category === categoryFilter),
        totalEmails: d.patterns.filter(p => p.category === categoryFilter).reduce((sum, p) => sum + p.count, 0)
      })).filter(d => d.patterns.length > 0);

  const handleKeep = (domain: string, subject: string, category: string) => {
    markKeep.mutate({ domain, subject, category });
  };

  const handleDelete = (domain: string, subject: string) => {
    addCriteria.mutate({ domain, subject });
  };

  const handleDelete1d = (domain: string, subject: string) => {
    addCriteria1d.mutate({ domain, subject });
  };

  return (
    <div className="space-y-6">
      {/* Stats Row */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <StatsCard label="Total" value={data.totalEmails} color="blue" />
        <StatsCard label="Filtered Out" value={data.filteredOut} color="gray" />
        <StatsCard label="Need Review" value={data.undecidedEmails} color="yellow" />
        <StatsCard label="Domains" value={data.domains.length} color="purple" />
        <StatsCard
          label="Cache Age"
          value={`${data.cacheAgeHours}h`}
          color={data.cacheAgeHours > 5 ? 'red' : 'green'}
        />
      </div>

      {/* Category Filters */}
      <div className="flex flex-wrap gap-2">
        {categories.map(cat => (
          <button
            key={cat}
            onClick={() => setCategoryFilter(cat)}
            className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
              categoryFilter === cat
                ? 'bg-blue-500 text-white'
                : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'
            }`}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* Domain List */}
      <div className="space-y-4">
        {filteredDomains.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            No emails match the selected filter.
          </div>
        ) : (
          filteredDomains.map(domain => (
            <DomainSection
              key={domain.domain}
              domain={domain}
              onKeep={handleKeep}
              onDelete={handleDelete}
              onDelete1d={handleDelete1d}
            />
          ))
        )}
      </div>
    </div>
  );
}
