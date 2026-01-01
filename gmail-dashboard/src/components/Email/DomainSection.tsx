import { useState } from 'react';
import type { DomainGroup, SubdomainGroup } from '../../hooks/useEmails';
import PatternItem from './PatternItem';

interface DomainSectionProps {
  domain: DomainGroup;
  onKeep: (domain: string, subject: string, category: string) => void;
  onDelete: (domain: string, subject: string) => void;
  onDelete1d: (domain: string, subject: string) => void;
}

interface SubdomainSectionProps {
  subdomain: SubdomainGroup;
  primaryDomain: string;
  onKeep: (domain: string, subject: string, category: string) => void;
  onDelete: (domain: string, subject: string) => void;
  onDelete1d: (domain: string, subject: string) => void;
}

function SubdomainSection({ subdomain, primaryDomain, onKeep, onDelete, onDelete1d }: SubdomainSectionProps) {
  const [expanded, setExpanded] = useState(true);
  const hasMultipleSubdomains = subdomain.subdomain !== primaryDomain;

  return (
    <div className="border-l-4 border-blue-200">
      {/* Subdomain Header - only show if different from primary */}
      {hasMultipleSubdomains && (
        <div className="bg-gray-100 border-b border-gray-200">
          <div className="flex items-center px-4 py-2">
            <button
              onClick={() => setExpanded(!expanded)}
              className="flex items-center gap-2 flex-1 text-left text-gray-700"
            >
              <span className="text-sm">{expanded ? '▼' : '▶'}</span>
              <span className="font-medium text-sm">
                {subdomain.displayName === '(direct)' ? (
                  <span className="text-gray-500 italic">@ {primaryDomain}</span>
                ) : (
                  <>
                    <span className="text-blue-600">{subdomain.displayName}</span>
                    <span className="text-gray-400">.{primaryDomain}</span>
                  </>
                )}
              </span>
              <span className="bg-gray-300 px-2 py-0.5 rounded-full text-xs text-gray-700">
                {subdomain.totalEmails}
              </span>
            </button>
          </div>
        </div>
      )}

      {/* Pattern List */}
      {expanded && (
        <div className="divide-y divide-gray-100">
          {subdomain.patterns.map((pattern, idx) => (
            <PatternItem
              key={`${pattern.subdomain}-${pattern.subject}-${idx}`}
              pattern={pattern}
              showSender={true}
              onKeep={(selectedText) => onKeep(pattern.domain, selectedText ?? pattern.subject, pattern.category)}
              onDelete={(selectedText) => onDelete(pattern.domain, selectedText ?? pattern.subject)}
              onDelete1d={(selectedText) => onDelete1d(pattern.domain, selectedText ?? pattern.subject)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function DomainSection({ domain, onKeep, onDelete, onDelete1d }: DomainSectionProps) {
  const [expanded, setExpanded] = useState(true);
  const hasSubdomains = domain.subdomains && domain.subdomains.length > 1;

  const handleKeepAll = () => {
    onKeep(domain.domain, '', 'DOMAIN');
  };

  const handleDeleteAll = () => {
    onDelete(domain.domain, '');
  };

  const handleDelete1dAll = () => {
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
            {hasSubdomains && (
              <span className="bg-white/10 px-2 py-0.5 rounded-full text-xs">
                {domain.subdomains.length} subdomains
              </span>
            )}
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

      {/* Subdomain List */}
      {expanded && domain.subdomains && (
        <div>
          {domain.subdomains.map((subdomain) => (
            <SubdomainSection
              key={subdomain.subdomain}
              subdomain={subdomain}
              primaryDomain={domain.domain}
              onKeep={onKeep}
              onDelete={onDelete}
              onDelete1d={onDelete1d}
            />
          ))}
        </div>
      )}
    </div>
  );
}
