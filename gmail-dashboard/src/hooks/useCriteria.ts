import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

// Types for the unified criteria format
export type Action = 'delete' | 'delete_1d' | 'keep';

export interface DomainRules {
  default?: Action | null;
  excludeSubjects?: string[];
  keep?: string[];
  delete?: string[];
  delete_1d?: string[];
  subdomains?: { [subdomain: string]: DomainRules };
}

export interface UnifiedCriteria {
  [primaryDomain: string]: DomainRules;
}

export interface CriteriaStats {
  totalDomains: number;
  withDefault: { delete: number; delete_1d: number; keep: number };
  withSubjectPatterns: number;
  withSubdomains: number;
  withExcludeSubjects: number;
}

interface CriteriaResponse {
  success: boolean;
  criteria: UnifiedCriteria;
  stats: CriteriaStats;
}

interface DomainRulesResponse {
  success: boolean;
  domain: string;
  rules: DomainRules;
}

// Flattened view for table display
export interface FlattenedRule {
  domain: string;
  subdomain?: string;
  action: Action | 'default';
  type: 'default' | 'pattern' | 'exclude';
  value: string;
}

// Flatten unified criteria into a table-friendly format
export function flattenCriteria(criteria: UnifiedCriteria): FlattenedRule[] {
  const rules: FlattenedRule[] = [];

  for (const [domain, domainRules] of Object.entries(criteria)) {
    // Add default action
    if (domainRules.default) {
      rules.push({
        domain,
        action: domainRules.default,
        type: 'default',
        value: '(all emails)'
      });
    }

    // Add exclude subjects
    if (domainRules.excludeSubjects?.length) {
      for (const term of domainRules.excludeSubjects) {
        rules.push({
          domain,
          action: 'default',
          type: 'exclude',
          value: term
        });
      }
    }

    // Add patterns
    for (const action of ['keep', 'delete', 'delete_1d'] as const) {
      const patterns = domainRules[action];
      if (patterns?.length) {
        for (const pattern of patterns) {
          rules.push({
            domain,
            action,
            type: 'pattern',
            value: pattern
          });
        }
      }
    }

    // Add subdomain rules
    if (domainRules.subdomains) {
      for (const [subdomain, subRules] of Object.entries(domainRules.subdomains)) {
        if (subRules.default) {
          rules.push({
            domain,
            subdomain,
            action: subRules.default,
            type: 'default',
            value: '(all emails)'
          });
        }

        for (const action of ['keep', 'delete', 'delete_1d'] as const) {
          const patterns = subRules[action];
          if (patterns?.length) {
            for (const pattern of patterns) {
              rules.push({
                domain,
                subdomain,
                action,
                type: 'pattern',
                value: pattern
              });
            }
          }
        }
      }
    }
  }

  // Sort by domain
  rules.sort((a, b) => a.domain.localeCompare(b.domain));

  return rules;
}

async function fetchAllCriteria(): Promise<CriteriaResponse> {
  const res = await fetch('/api/criteria');
  if (!res.ok) throw new Error('Failed to fetch criteria');
  return res.json();
}

async function fetchDomainCriteria(domain: string): Promise<DomainRulesResponse> {
  const res = await fetch(`/api/criteria/domain/${encodeURIComponent(domain)}`);
  if (!res.ok) throw new Error('Failed to fetch domain criteria');
  return res.json();
}

async function addRule(domain: string, action: Action, subjectPattern?: string, subdomain?: string) {
  const res = await fetch('/api/criteria/rule', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ domain, action, subjectPattern, subdomain })
  });
  if (!res.ok) throw new Error('Failed to add rule');
  return res.json();
}

async function deleteRule(domain: string, action?: Action, subjectPattern?: string, subdomain?: string) {
  const res = await fetch('/api/criteria/rule', {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ domain, action, subjectPattern, subdomain })
  });
  if (!res.ok) throw new Error('Failed to delete rule');
  return res.json();
}

async function deleteDomain(domain: string) {
  const res = await fetch(`/api/criteria/domain/${encodeURIComponent(domain)}`, {
    method: 'DELETE'
  });
  if (!res.ok) throw new Error('Failed to delete domain');
  return res.json();
}

async function updateDomainRules(domain: string, rules: DomainRules) {
  const res = await fetch(`/api/criteria/domain/${encodeURIComponent(domain)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(rules)
  });
  if (!res.ok) throw new Error('Failed to update domain');
  return res.json();
}

export function useCriteria() {
  return useQuery({
    queryKey: ['criteria'],
    queryFn: fetchAllCriteria
  });
}

export function useDomainCriteria(domain: string) {
  return useQuery({
    queryKey: ['criteria', 'domain', domain],
    queryFn: () => fetchDomainCriteria(domain),
    enabled: !!domain
  });
}

export function useAddRule() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ domain, action, subjectPattern, subdomain }: {
      domain: string;
      action: Action;
      subjectPattern?: string;
      subdomain?: string;
    }) => addRule(domain, action, subjectPattern, subdomain),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['criteria'] });
      queryClient.invalidateQueries({ queryKey: ['emails'] });
      queryClient.invalidateQueries({ queryKey: ['stats'] });
    }
  });
}

export function useDeleteRule() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ domain, action, subjectPattern, subdomain }: {
      domain: string;
      action?: Action;
      subjectPattern?: string;
      subdomain?: string;
    }) => deleteRule(domain, action, subjectPattern, subdomain),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['criteria'] });
      queryClient.invalidateQueries({ queryKey: ['emails'] });
      queryClient.invalidateQueries({ queryKey: ['stats'] });
    }
  });
}

export function useDeleteDomain() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (domain: string) => deleteDomain(domain),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['criteria'] });
      queryClient.invalidateQueries({ queryKey: ['emails'] });
      queryClient.invalidateQueries({ queryKey: ['stats'] });
    }
  });
}

export function useUpdateDomain() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ domain, rules }: { domain: string; rules: DomainRules }) =>
      updateDomainRules(domain, rules),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['criteria'] });
      queryClient.invalidateQueries({ queryKey: ['emails'] });
      queryClient.invalidateQueries({ queryKey: ['stats'] });
    }
  });
}

// Legacy exports for backwards compatibility
export type CriteriaEntry = {
  email: string;
  subdomain: string;
  primaryDomain: string;
  subject: string;
  toEmails: string;
  ccEmails: string;
  excludeSubject: string;
};

// Legacy hooks (deprecated)
export function useDeleteCriteria() {
  return useDeleteRule();
}

export function useMoveCriteria() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ fromType, toType, domain, pattern }: {
      fromType: Action;
      toType: Action;
      domain: string;
      pattern?: string;
    }) => {
      // Delete from old, add to new
      await deleteRule(domain, fromType, pattern);
      await addRule(domain, toType, pattern);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['criteria'] });
    }
  });
}
