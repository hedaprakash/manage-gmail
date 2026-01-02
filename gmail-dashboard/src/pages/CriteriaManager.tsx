import { useState, useMemo } from 'react';
import {
  useCriteria,
  useDeleteRule,
  useDeleteDomain,
  flattenCriteria,
  type Action,
  type FlattenedRule
} from '../hooks/useCriteria';

type FilterType = 'all' | 'delete' | 'delete_1d' | 'keep';

const actionColors: Record<string, { bg: string; text: string; label: string }> = {
  delete: { bg: 'bg-red-100', text: 'text-red-700', label: 'Delete' },
  delete_1d: { bg: 'bg-orange-100', text: 'text-orange-700', label: 'Delete 1-Day' },
  keep: { bg: 'bg-green-100', text: 'text-green-700', label: 'Keep' },
  default: { bg: 'bg-gray-100', text: 'text-gray-700', label: 'Exclude' }
};

export default function CriteriaManager() {
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<FilterType>('all');
  const [expandedDomains, setExpandedDomains] = useState<Set<string>>(new Set());

  const { data, isLoading } = useCriteria();
  const deleteRuleMutation = useDeleteRule();
  const deleteDomainMutation = useDeleteDomain();

  // Flatten criteria for table display
  const flatRules = useMemo(() => {
    if (!data?.criteria) return [];
    return flattenCriteria(data.criteria);
  }, [data?.criteria]);

  // Filter rules
  const filteredRules = useMemo(() => {
    let rules = flatRules;

    // Apply action filter
    if (filter !== 'all') {
      rules = rules.filter(r => r.action === filter);
    }

    // Apply search filter
    if (search) {
      const searchLower = search.toLowerCase();
      rules = rules.filter(r =>
        r.domain.toLowerCase().includes(searchLower) ||
        r.value.toLowerCase().includes(searchLower) ||
        (r.subdomain?.toLowerCase().includes(searchLower))
      );
    }

    return rules;
  }, [flatRules, filter, search]);

  // Group by domain for collapsed view
  const groupedByDomain = useMemo(() => {
    const groups: Record<string, FlattenedRule[]> = {};
    for (const rule of filteredRules) {
      if (!groups[rule.domain]) {
        groups[rule.domain] = [];
      }
      groups[rule.domain].push(rule);
    }
    return groups;
  }, [filteredRules]);

  const toggleDomain = (domain: string) => {
    setExpandedDomains(prev => {
      const next = new Set(prev);
      if (next.has(domain)) {
        next.delete(domain);
      } else {
        next.add(domain);
      }
      return next;
    });
  };

  const handleDeleteRule = (rule: FlattenedRule) => {
    const action = rule.action === 'default' ? undefined : rule.action as Action;
    const pattern = rule.type === 'pattern' ? rule.value : undefined;

    if (confirm(`Delete this rule for ${rule.domain}?`)) {
      deleteRuleMutation.mutate({
        domain: rule.domain,
        action,
        subjectPattern: pattern,
        subdomain: rule.subdomain
      });
    }
  };

  const handleDeleteDomain = (domain: string) => {
    if (confirm(`Delete ALL rules for ${domain}? This cannot be undone.`)) {
      deleteDomainMutation.mutate(domain);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-lg text-gray-500">Loading criteria...</div>
      </div>
    );
  }

  const stats = data?.stats;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-800">Criteria Manager</h1>
        <div className="text-sm text-gray-500">
          {stats?.totalDomains || 0} domains configured
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => setFilter('all')}
          className={`px-4 py-2 rounded-lg font-medium transition-colors ${
            filter === 'all'
              ? 'bg-blue-500 text-white'
              : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'
          }`}
        >
          All ({flatRules.length})
        </button>
        <button
          onClick={() => setFilter('delete')}
          className={`px-4 py-2 rounded-lg font-medium transition-colors ${
            filter === 'delete'
              ? 'bg-red-500 text-white'
              : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'
          }`}
        >
          Delete ({flatRules.filter(r => r.action === 'delete').length})
        </button>
        <button
          onClick={() => setFilter('delete_1d')}
          className={`px-4 py-2 rounded-lg font-medium transition-colors ${
            filter === 'delete_1d'
              ? 'bg-orange-500 text-white'
              : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'
          }`}
        >
          Delete 1-Day ({flatRules.filter(r => r.action === 'delete_1d').length})
        </button>
        <button
          onClick={() => setFilter('keep')}
          className={`px-4 py-2 rounded-lg font-medium transition-colors ${
            filter === 'keep'
              ? 'bg-green-500 text-white'
              : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'
          }`}
        >
          Keep ({flatRules.filter(r => r.action === 'keep').length})
        </button>
      </div>

      {/* Search */}
      <div className="flex gap-4">
        <input
          type="text"
          placeholder="Search domain or pattern..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
        {search && (
          <button
            onClick={() => setSearch('')}
            className="px-4 py-2 text-gray-500 hover:text-gray-700"
          >
            Clear
          </button>
        )}
      </div>

      {/* Domain Groups */}
      <div className="space-y-2">
        {Object.keys(groupedByDomain).length === 0 ? (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8 text-center text-gray-500">
            No criteria entries found.
          </div>
        ) : (
          Object.entries(groupedByDomain).map(([domain, rules]) => {
            const isExpanded = expandedDomains.has(domain);
            const defaultRule = rules.find(r => r.type === 'default' && !r.subdomain);
            const hasSubdomains = rules.some(r => r.subdomain);

            return (
              <div key={domain} className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
                {/* Domain Header */}
                <div
                  className="flex items-center justify-between px-4 py-3 bg-gray-50 cursor-pointer hover:bg-gray-100"
                  onClick={() => toggleDomain(domain)}
                >
                  <div className="flex items-center gap-3">
                    <span className="text-gray-400">{isExpanded ? '▼' : '▶'}</span>
                    <span className="font-medium text-gray-900">{domain}</span>
                    {defaultRule && (
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${actionColors[defaultRule.action].bg} ${actionColors[defaultRule.action].text}`}>
                        {actionColors[defaultRule.action].label}
                      </span>
                    )}
                    {hasSubdomains && (
                      <span className="px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-700">
                        Has Subdomains
                      </span>
                    )}
                    <span className="text-sm text-gray-500">
                      ({rules.length} rule{rules.length !== 1 ? 's' : ''})
                    </span>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteDomain(domain);
                    }}
                    className="px-2 py-1 text-sm text-red-600 hover:bg-red-50 rounded"
                  >
                    Delete All
                  </button>
                </div>

                {/* Expanded Rules */}
                {isExpanded && (
                  <div className="divide-y divide-gray-100">
                    {rules.map((rule, idx) => (
                      <div key={idx} className="flex items-center justify-between px-4 py-2 hover:bg-gray-50">
                        <div className="flex items-center gap-3">
                          {rule.subdomain && (
                            <span className="text-xs text-purple-600 bg-purple-50 px-2 py-0.5 rounded">
                              {rule.subdomain}
                            </span>
                          )}
                          <span className={`px-2 py-0.5 rounded text-xs font-medium ${actionColors[rule.action].bg} ${actionColors[rule.action].text}`}>
                            {actionColors[rule.action].label}
                          </span>
                          <span className="text-sm text-gray-500">
                            {rule.type === 'default' ? (
                              <em>Default action</em>
                            ) : rule.type === 'exclude' ? (
                              <span>Exclude: <strong>{rule.value}</strong></span>
                            ) : (
                              <span>Pattern: <strong>{rule.value}</strong></span>
                            )}
                          </span>
                        </div>
                        <button
                          onClick={() => handleDeleteRule(rule)}
                          className="px-2 py-1 text-sm text-red-600 hover:bg-red-50 rounded"
                        >
                          Remove
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      <div className="text-sm text-gray-500">
        Showing {Object.keys(groupedByDomain).length} domains with {filteredRules.length} rules
      </div>
    </div>
  );
}
