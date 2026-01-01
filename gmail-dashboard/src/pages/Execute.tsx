import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';

interface PreviewResult {
  success: boolean;
  matchCount: number;
  skippedCount: number;
  matches: Array<{ id: string; from: string; subject: string; date: string }>;
}

interface ExecuteResult {
  success: boolean;
  dryRun: boolean;
  summary: {
    total: number;
    deleted: number;
    skipped: number;
    errors: number;
  };
  progress: {
    logs: string[];
  };
}

async function previewDelete(criteriaFile: string, minAgeDays: number): Promise<PreviewResult> {
  const res = await fetch('/api/execute/preview', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ criteriaFile, minAgeDays })
  });
  if (!res.ok) throw new Error('Preview failed');
  return res.json();
}

async function executeDelete(criteriaFile: string, dryRun: boolean, minAgeDays: number): Promise<ExecuteResult> {
  const res = await fetch('/api/execute/delete', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ criteriaFile, dryRun, minAgeDays })
  });
  if (!res.ok) throw new Error('Execution failed');
  return res.json();
}

export default function Execute() {
  const [criteriaFile, setCriteriaFile] = useState<'criteria' | 'criteria_1d'>('criteria');
  const [dryRun, setDryRun] = useState(true);
  const [minAgeDays, setMinAgeDays] = useState(0);

  const previewMutation = useMutation({
    mutationFn: () => previewDelete(criteriaFile, minAgeDays)
  });

  const executeMutation = useMutation({
    mutationFn: () => executeDelete(criteriaFile, dryRun, minAgeDays)
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-800">Execute Email Deletion</h1>

      {/* Options */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 space-y-4">
        <h2 className="font-semibold text-gray-700">Options</h2>

        {/* Criteria File */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Criteria File</label>
          <div className="flex gap-4">
            <label className="flex items-center gap-2">
              <input
                type="radio"
                name="criteria"
                checked={criteriaFile === 'criteria'}
                onChange={() => setCriteriaFile('criteria')}
                className="text-blue-600"
              />
              <span>criteria.json (immediate delete)</span>
            </label>
            <label className="flex items-center gap-2">
              <input
                type="radio"
                name="criteria"
                checked={criteriaFile === 'criteria_1d'}
                onChange={() => setCriteriaFile('criteria_1d')}
                className="text-blue-600"
              />
              <span>criteria_1day_old.json (delayed delete)</span>
            </label>
          </div>
        </div>

        {/* Min Age */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Minimum Age (days)
          </label>
          <input
            type="number"
            min="0"
            value={minAgeDays}
            onChange={e => setMinAgeDays(parseInt(e.target.value) || 0)}
            className="w-24 px-3 py-2 border border-gray-300 rounded-lg"
          />
          <p className="text-sm text-gray-500 mt-1">
            Only delete emails older than this. Use 1+ to protect recent OTPs.
          </p>
        </div>

        {/* Dry Run */}
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={dryRun}
            onChange={e => setDryRun(e.target.checked)}
            className="text-blue-600 rounded"
          />
          <span className="text-sm text-gray-700">
            Dry Run (preview only, no actual deletion)
          </span>
        </label>
      </div>

      {/* Action Buttons */}
      <div className="flex gap-4">
        <button
          onClick={() => previewMutation.mutate()}
          disabled={previewMutation.isPending}
          className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50"
        >
          {previewMutation.isPending ? 'Loading...' : 'Preview Matches'}
        </button>
        <button
          onClick={() => {
            if (!dryRun && !confirm('This will PERMANENTLY delete emails. Continue?')) {
              return;
            }
            executeMutation.mutate();
          }}
          disabled={executeMutation.isPending}
          className={`px-4 py-2 rounded-lg text-white disabled:opacity-50 ${
            dryRun ? 'bg-orange-500 hover:bg-orange-600' : 'bg-red-500 hover:bg-red-600'
          }`}
        >
          {executeMutation.isPending ? 'Executing...' : dryRun ? 'Execute (Dry Run)' : 'Execute Delete'}
        </button>
      </div>

      {/* Preview Results */}
      {previewMutation.data && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h3 className="font-semibold text-gray-700 mb-4">Preview Results</h3>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div className="text-center p-3 bg-red-50 rounded-lg">
              <div className="text-xl font-bold text-red-600">{previewMutation.data.matchCount}</div>
              <div className="text-sm text-red-700">Will be deleted</div>
            </div>
            <div className="text-center p-3 bg-yellow-50 rounded-lg">
              <div className="text-xl font-bold text-yellow-600">{previewMutation.data.skippedCount}</div>
              <div className="text-sm text-yellow-700">Skipped (too recent)</div>
            </div>
          </div>
          {previewMutation.data.matches.length > 0 && (
            <div className="max-h-64 overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 sticky top-0">
                  <tr>
                    <th className="px-2 py-1 text-left">From</th>
                    <th className="px-2 py-1 text-left">Subject</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {previewMutation.data.matches.slice(0, 50).map((m, i) => (
                    <tr key={i}>
                      <td className="px-2 py-1 truncate max-w-[150px]">{m.from}</td>
                      <td className="px-2 py-1 truncate max-w-[300px]">{m.subject}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {previewMutation.data.matches.length > 50 && (
                <p className="text-center text-gray-500 py-2">
                  ... and {previewMutation.data.matches.length - 50} more
                </p>
              )}
            </div>
          )}
        </div>
      )}

      {/* Execution Results */}
      {executeMutation.data && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h3 className="font-semibold text-gray-700 mb-4">
            Execution Results {executeMutation.data.dryRun && '(Dry Run)'}
          </h3>
          <div className="grid grid-cols-4 gap-4 mb-4">
            <div className="text-center p-3 bg-gray-50 rounded-lg">
              <div className="text-xl font-bold text-gray-600">{executeMutation.data.summary.total}</div>
              <div className="text-sm text-gray-700">Total</div>
            </div>
            <div className="text-center p-3 bg-red-50 rounded-lg">
              <div className="text-xl font-bold text-red-600">{executeMutation.data.summary.deleted}</div>
              <div className="text-sm text-red-700">Deleted</div>
            </div>
            <div className="text-center p-3 bg-yellow-50 rounded-lg">
              <div className="text-xl font-bold text-yellow-600">{executeMutation.data.summary.skipped}</div>
              <div className="text-sm text-yellow-700">Skipped</div>
            </div>
            <div className="text-center p-3 bg-orange-50 rounded-lg">
              <div className="text-xl font-bold text-orange-600">{executeMutation.data.summary.errors}</div>
              <div className="text-sm text-orange-700">Errors</div>
            </div>
          </div>

          {/* Logs */}
          <div className="bg-gray-900 text-gray-100 rounded-lg p-4 max-h-64 overflow-y-auto font-mono text-xs">
            {executeMutation.data.progress.logs.map((log, i) => (
              <div key={i} className="py-0.5">{log}</div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
