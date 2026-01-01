import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

export interface CriteriaEntry {
  email: string;
  subdomain: string;
  primaryDomain: string;
  subject: string;
  toEmails: string;
  ccEmails: string;
  excludeSubject: string;
}

interface CriteriaResponse {
  success: boolean;
  delete: CriteriaEntry[];
  delete1d: CriteriaEntry[];
  keep: CriteriaEntry[];
}

interface CriteriaTypeResponse {
  success: boolean;
  type: string;
  count: number;
  entries: CriteriaEntry[];
}

async function fetchAllCriteria(): Promise<CriteriaResponse> {
  const res = await fetch('/api/criteria');
  if (!res.ok) throw new Error('Failed to fetch criteria');
  return res.json();
}

async function fetchCriteriaByType(type: string): Promise<CriteriaTypeResponse> {
  const res = await fetch(`/api/criteria/${type}`);
  if (!res.ok) throw new Error('Failed to fetch criteria');
  return res.json();
}

async function addCriteriaEntry(type: string, entry: Partial<CriteriaEntry>) {
  const res = await fetch(`/api/criteria/${type}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      domain: entry.primaryDomain,
      subject: entry.subject,
      excludeSubject: entry.excludeSubject
    })
  });
  if (!res.ok) throw new Error('Failed to add criteria');
  return res.json();
}

async function deleteCriteriaEntry(type: string, index: number) {
  const res = await fetch(`/api/criteria/${type}/${index}`, {
    method: 'DELETE'
  });
  if (!res.ok) throw new Error('Failed to delete criteria');
  return res.json();
}

async function moveCriteriaEntry(fromType: string, toType: string, index: number) {
  const res = await fetch('/api/criteria/move', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ fromType, toType, index })
  });
  if (!res.ok) throw new Error('Failed to move criteria');
  return res.json();
}

export function useAllCriteria() {
  return useQuery({
    queryKey: ['criteria', 'all'],
    queryFn: fetchAllCriteria
  });
}

export function useCriteriaByType(type: string) {
  return useQuery({
    queryKey: ['criteria', type],
    queryFn: () => fetchCriteriaByType(type)
  });
}

export function useAddCriteriaEntry() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ type, entry }: { type: string; entry: Partial<CriteriaEntry> }) =>
      addCriteriaEntry(type, entry),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['criteria'] });
      queryClient.invalidateQueries({ queryKey: ['emails'] });
      queryClient.invalidateQueries({ queryKey: ['stats'] });
    }
  });
}

export function useDeleteCriteriaEntry() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ type, index }: { type: string; index: number }) =>
      deleteCriteriaEntry(type, index),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['criteria'] });
      queryClient.invalidateQueries({ queryKey: ['emails'] });
      queryClient.invalidateQueries({ queryKey: ['stats'] });
    }
  });
}

export function useMoveCriteriaEntry() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ fromType, toType, index }: { fromType: string; toType: string; index: number }) =>
      moveCriteriaEntry(fromType, toType, index),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['criteria'] });
      queryClient.invalidateQueries({ queryKey: ['emails'] });
      queryClient.invalidateQueries({ queryKey: ['stats'] });
    }
  });
}
