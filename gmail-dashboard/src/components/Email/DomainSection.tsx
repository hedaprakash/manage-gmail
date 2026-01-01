import { useState } from 'react';
import type { DomainGroup } from '../../hooks/useEmails';
import PatternItem from './PatternItem';

interface DomainSectionProps {
  domain: DomainGroup;
  onKeep: (domain: string, subject: string, category: string) => void;
  onDelete: (domain: string, subject: string) => void;
  onDelete1d: (domain: string, subject: string) => void;
}

export default function DomainSection({ domain, onKeep, onDelete, onDelete1d }: DomainSectionProps) {
  const [expanded, setExpanded] = useState(true);

  const handleKeepAll = () => {
    // Keep all = add domain-only entry (empty subject)
    onKeep(domain.domain, '', 'DOMAIN');
  };

  const handleDeleteAll = () => {
    // Delete all = add domain-only entry
    onDelete(domain.domain, '');
  };

  const handleDelete1dAll = () => {
    // Delete 1d all = add domain-only entry
    onDelete1d(domain.domain, '');
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
      {/* Domain Header */}
      <div className="bg-blue-500 text-white">
        <div className="flex items-center px-4 py-3">
          <button
            onClick={() => setExpanded(!expanded)}
            className="flex items-center gap-3 flex-1 text-left"
          >
            <span className="text-lg">{expanded ? '▼' : '▶'}</span>
            <span className="font-semibold">{domain.domain}</span>
            <span className="bg-white/20 px-2 py-0.5 rounded-full text-sm">
              {domain.totalEmails} emails
            </span>
          </button>

          {/* Domain-level action buttons */}
          <div className="flex gap-2">
            <button
              onClick={handleKeepAll}
              className="px-3 py-1 text-xs font-medium bg-green-500 hover:bg-green-600 rounded"
            >
              Keep All
            </button>
            <button
              onClick={handleDeleteAll}
              className="px-3 py-1 text-xs font-medium bg-red-500 hover:bg-red-600 rounded"
            >
              Del All
            </button>
            <button
              onClick={handleDelete1dAll}
              className="px-3 py-1 text-xs font-medium bg-orange-500 hover:bg-orange-600 rounded"
            >
              Del 1d
            </button>
          </div>
        </div>
      </div>

      {/* Pattern List */}
      {expanded && (
        <div className="divide-y divide-gray-100">
          {domain.patterns.map((pattern, idx) => (
            <PatternItem
              key={`${pattern.subject}-${idx}`}
              pattern={pattern}
              onKeep={() => onKeep(pattern.domain, pattern.subject, pattern.category)}
              onDelete={() => onDelete(pattern.domain, pattern.subject)}
              onDelete1d={() => onDelete1d(pattern.domain, pattern.subject)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
