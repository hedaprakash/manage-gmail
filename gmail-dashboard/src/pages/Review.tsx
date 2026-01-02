import { useState, useMemo } from 'react';
import { useEmails, useMarkKeep, useAddCriteria, useAddCriteria1d, formatDateRange } from '../hooks/useEmails';
import type { DomainGroup } from '../hooks/useEmails';
import StatsCard from '../components/Stats/StatsCard';
import DomainSection from '../components/Email/DomainSection';

const categories = ['All', 'PROMO', 'NEWSLETTER', 'UNKNOWN', 'SECURITY', 'ALERT', 'STATEMENT', 'ORDER'];
type SortOption = 'count' | 'alpha';

export default function Review() {
  const [categoryFilter, setCategoryFilter] = useState('All');
  const [sortBy, setSortBy] = useState<SortOption>('alpha'); // Default to alphabetical for stability
  const { data, isLoading, error } = useEmails();
  const markKeep = useMarkKeep();
  const addCriteria = useAddCriteria();
  const addCriteria1d = useAddCriteria1d();

  // Filter and sort domains - must be called before any early returns (Rules of Hooks)
  const filteredDomains = useMemo(() => {
    if (!data) return [];

    let domains: DomainGroup[] = data.domains;

    // Filter by category if needed
    if (categoryFilter !== 'All') {
      domains = domains.map(d => {
        // Filter patterns in each subdomain
        const filteredSubdomains = d.subdomains?.map(sub => ({
          ...sub,
          patterns: sub.patterns.filter(p => p.category === categoryFilter),
          totalEmails: sub.patterns.filter(p => p.category === categoryFilter).reduce((sum, p) => sum + p.count, 0)
        })).filter(sub => sub.patterns.length > 0) ?? [];

        return {
          ...d,
          subdomains: filteredSubdomains,
          patterns: d.patterns.filter(p => p.category === categoryFilter),
          totalEmails: filteredSubdomains.reduce((sum, sub) => sum + sub.totalEmails, 0)
        };
      }).filter(d => d.totalEmails > 0);
    }

    // Sort domains
    if (sortBy === 'alpha') {
      return [...domains].sort((a, b) => a.domain.localeCompare(b.domain));
    } else {
      return [...domains].sort((a, b) => b.totalEmails - a.totalEmails);
    }
  }, [data, categoryFilter, sortBy]);

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

      {/* Filters Row */}
      <div className="flex flex-wrap items-center justify-between gap-4">
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

        {/* Sort Toggle */}
        <div className="flex items-center gap-2 text-sm">
          <span className="text-gray-500">Sort:</span>
          <button
            onClick={() => setSortBy(sortBy === 'alpha' ? 'count' : 'alpha')}
            className="px-3 py-1.5 rounded border border-gray-300 bg-white hover:bg-gray-50 font-medium"
          >
            {sortBy === 'alpha' ? 'A-Z' : 'Count'}
          </button>
        </div>
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
