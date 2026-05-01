// frontend/src/components/realtime/SuggestionCardStack.tsx
import type { Suggestion } from "../../lib/realtime/types";

interface Props {
  suggestions: Suggestion[];
  onFeedback: (id: string, action: "adopt" | "ignore") => void;
  readOnly?: boolean;
}

export function SuggestionCardStack({ suggestions, onFeedback, readOnly }: Props) {
  if (suggestions.length === 0) {
    return (
      <div className="rounded-lg border border-slate-200 p-4 text-sm text-slate-500">
        AI 建议会在这里出现
      </div>
    );
  }
  const latest = suggestions[suggestions.length - 1];
  const history = suggestions.slice(0, -1);
  return (
    <div className="flex flex-col gap-3">
      <div className="rounded-lg border border-emerald-300 bg-emerald-50 p-4">
        <div className="text-xs font-semibold text-emerald-700">💡 当前建议</div>
        <div className="mt-1 text-base text-slate-900">{latest.text}</div>
        {!readOnly && (
          <div className="mt-3 flex gap-2">
            <button
              onClick={() => onFeedback(latest.id, "adopt")}
              className="rounded-md bg-emerald-600 px-3 py-1 text-sm text-white hover:bg-emerald-700"
            >采用</button>
            <button
              onClick={() => onFeedback(latest.id, "ignore")}
              className="rounded-md border border-slate-300 px-3 py-1 text-sm text-slate-700"
            >忽略</button>
          </div>
        )}
      </div>
      {history.length > 0 && (
        <details className="rounded-md border border-slate-200 p-2 text-sm">
          <summary className="cursor-pointer text-slate-600">历史 ({history.length})</summary>
          <ul className="mt-2 space-y-1">
            {history.map((s) => <li key={s.id} className="text-slate-700">• {s.text}</li>)}
          </ul>
        </details>
      )}
    </div>
  );
}
