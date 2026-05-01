// frontend/src/components/realtime/TranscriptStream.tsx
import { useEffect, useRef } from "react";
import type { TranscriptChunk } from "../../lib/realtime/types";

export function TranscriptStream({ chunks }: { chunks: TranscriptChunk[] }) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chunks.length]);

  return (
    <div className="flex-1 overflow-y-auto rounded-lg bg-slate-900 p-4 text-slate-100">
      {chunks.length === 0 && (
        <div className="text-slate-500 text-sm">等待音频流…</div>
      )}
      {chunks.map((c) => (
        <div key={c.seq} className="mb-2">
          <span className={`text-xs ${c.speaker === "agent" ? "text-blue-300" : "text-rose-300"}`}>
            {c.speaker === "agent" ? "[我]" : "[客户]"}
          </span>{" "}
          <span className="text-base">{c.text}</span>
        </div>
      ))}
      <div ref={endRef} />
    </div>
  );
}
