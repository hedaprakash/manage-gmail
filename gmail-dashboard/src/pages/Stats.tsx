import { useStats } from '../hooks/useEmails';
import StatsCard from '../components/Stats/StatsCard';

export default function Stats() {
  const { data, isLoading, error } = useStats();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-lg text-gray-500">Loading statistics...</div>
      </div>
    );
  }

  if (error || !data?.success) {
    return (
      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6 text-center">
        <h2 className="text-lg font-semibold text-yellow-800 mb-2">No Data Available</h2>
        <p className="text-yellow-700">Refresh from Gmail to load email statistics.</p>
      </div>
    );
  }

  const { stats } = data;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-800">Email Statistics</h1>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <StatsCard label="Total Emails" value={stats.total} color="blue" />
        <StatsCard label="Will Delete" value={stats.matchedCriteria} color="red" />
        <StatsCard label="Delete 1-Day" value={stats.matchedCriteria1d} color="yellow" />
        <StatsCard label="Protected" value={stats.matchedKeep} color="green" />
        <StatsCard label="Need Review" value={stats.undecided} color="purple" />
      </div>

      {/* Criteria Rules */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <h2 className="text-lg font-semibold mb-4">Criteria Rules</h2>
        <div className="grid grid-cols-3 gap-4">
          <div className="text-center p-4 bg-red-50 rounded-lg">
            <div className="text-2xl font-bold text-red-600">{data.criteriaRules}</div>
            <div className="text-sm text-red-700">Delete Rules</div>
          </div>
          <div className="text-center p-4 bg-orange-50 rounded-lg">
            <div className="text-2xl font-bold text-orange-600">{data.criteria1dRules}</div>
            <div className="text-sm text-orange-700">Delete 1-Day Rules</div>
          </div>
          <div className="text-center p-4 bg-green-50 rounded-lg">
            <div className="text-2xl font-bold text-green-600">{data.keepRules}</div>
            <div className="text-sm text-green-700">Keep Rules</div>
          </div>
        </div>
      </div>

      {/* Top Domains by Category */}
      <div className="grid md:grid-cols-3 gap-6">
        {/* Delete Domains */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h3 className="font-semibold text-red-700 mb-3">Top Delete Domains</h3>
          <ul className="space-y-2">
            {Object.entries(stats.criteriaDomains).map(([domain, count]) => (
              <li key={domain} className="flex justify-between text-sm">
                <span className="text-gray-700 truncate">{domain}</span>
                <span className="text-red-600 font-medium">{count}</span>
              </li>
            ))}
            {Object.keys(stats.criteriaDomains).length === 0 && (
              <li className="text-gray-400 text-sm">No domains</li>
            )}
          </ul>
        </div>

        {/* Delete 1-Day Domains */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h3 className="font-semibold text-orange-700 mb-3">Top Delete 1-Day Domains</h3>
          <ul className="space-y-2">
            {Object.entries(stats.criteria1dDomains).map(([domain, count]) => (
              <li key={domain} className="flex justify-between text-sm">
                <span className="text-gray-700 truncate">{domain}</span>
                <span className="text-orange-600 font-medium">{count}</span>
              </li>
            ))}
            {Object.keys(stats.criteria1dDomains).length === 0 && (
              <li className="text-gray-400 text-sm">No domains</li>
            )}
          </ul>
        </div>

        {/* Keep Domains */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h3 className="font-semibold text-green-700 mb-3">Top Protected Domains</h3>
          <ul className="space-y-2">
            {Object.entries(stats.keepDomains).map(([domain, count]) => (
              <li key={domain} className="flex justify-between text-sm">
                <span className="text-gray-700 truncate">{domain}</span>
                <span className="text-green-600 font-medium">{count}</span>
              </li>
            ))}
            {Object.keys(stats.keepDomains).length === 0 && (
              <li className="text-gray-400 text-sm">No domains</li>
            )}
          </ul>
        </div>
      </div>

      {/* Cache Info */}
      <div className="text-sm text-gray-500 text-center">
        Cache: {data.cacheFile} ({data.cacheAgeHours} hours old)
      </div>
    </div>
  );
}
