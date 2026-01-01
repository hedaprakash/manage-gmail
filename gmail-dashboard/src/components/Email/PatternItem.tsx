import type { EmailPattern } from '../../hooks/useEmails';
import { formatDateRange } from '../../hooks/useEmails';

interface PatternItemProps {
  pattern: EmailPattern;
  onKeep: () => void;
  onDelete: () => void;
  onDelete1d: () => void;
}

export default function PatternItem({ pattern, onKeep, onDelete, onDelete1d }: PatternItemProps) {
  const dateDisplay = formatDateRange(pattern.minDate, pattern.maxDate, pattern.count);

  return (
    <div className="flex items-center gap-4 px-4 py-3 hover:bg-gray-50 pattern-item">
      {/* Category Badge */}
      <div
        className="flex flex-col items-center min-w-[50px]"
        style={{ color: pattern.categoryColor }}
      >
        <span className="text-xl">{pattern.categoryIcon}</span>
        <span className="text-xs font-medium">{pattern.category.slice(0, 4)}</span>
      </div>

      {/* Subject */}
      <div className="flex-1 min-w-0">
        <div className="text-sm text-gray-900 truncate" title={pattern.subject}>
          {pattern.subject || '(all emails from domain)'}
        </div>
      </div>

      {/* Count & Date */}
      <div className="text-right min-w-[100px]">
        <a
          href={pattern.gmailUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm font-medium text-blue-600 hover:underline"
        >
          {pattern.count} email{pattern.count !== 1 ? 's' : ''} 🔗
        </a>
        <div className="text-xs text-gray-500">{dateDisplay}</div>
      </div>

      {/* Action Buttons */}
      <div className="flex gap-1">
        <button
          onClick={onKeep}
          className="btn btn-keep"
          title="Keep"
        >
          K
        </button>
        <button
          onClick={onDelete}
          className="btn btn-delete"
          title="Delete"
        >
          D
        </button>
        <button
          onClick={onDelete1d}
          className="btn btn-delete-1d"
          title="Delete after 1 day"
        >
          1d
        </button>
      </div>
    </div>
  );
}
