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

type CriteriaType = 'delete' | 'delete1d' | 'keep';

async function fetchAllCriteria(): Promise<CriteriaResponse> {
  const res = await fetch('/api/criteria');
  if (!res.ok) throw new Error('Failed to fetch criteria');
  return res.json();
}

async function addCriteria(type: CriteriaType, domain: string, subject?: string) {
  const res = await fetch(`/api/criteria/${type}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ domain, subject })
  });
  if (!res.ok) throw new Error('Failed to add criteria');
  return res.json();
}

async function deleteCriteria(type: CriteriaType, index: number) {
  const res = await fetch(`/api/criteria/${type}/${index}`, {
    method: 'DELETE'
  });
  if (!res.ok) throw new Error('Failed to delete criteria');
  return res.json();
}

async function moveCriteria(fromType: CriteriaType, toType: CriteriaType, index: number) {
  const res = await fetch('/api/criteria/move', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ fromType, toType, index })
  });
  if (!res.ok) throw new Error('Failed to move criteria');
  return res.json();
}

export function useCriteria() {
  return useQuery({
    queryKey: ['criteria'],
    queryFn: fetchAllCriteria
  });
}

export function useAddCriteria() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ type, domain, subject }: { type: CriteriaType; domain: string; subject?: string }) =>
      addCriteria(type, domain, subject),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['criteria'] });
      queryClient.invalidateQueries({ queryKey: ['emails'] });
      queryClient.invalidateQueries({ queryKey: ['stats'] });
    }
  });
}

export function useDeleteCriteria() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ type, index }: { type: CriteriaType; index: number }) =>
      deleteCriteria(type, index),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['criteria'] });
      queryClient.invalidateQueries({ queryKey: ['emails'] });
      queryClient.invalidateQueries({ queryKey: ['stats'] });
    }
  });
}

export function useMoveCriteria() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ fromType, toType, index }: { fromType: CriteriaType; toType: CriteriaType; index: number }) =>
      moveCriteria(fromType, toType, index),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['criteria'] });
    }
  });
}
