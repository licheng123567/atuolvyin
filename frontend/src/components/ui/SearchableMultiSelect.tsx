// v2.2 — 可搜索多选下拉（零依赖；样式与 SearchableSelect 同源）
// 用法：长的多选人员列表（督导组 / 默认催收团队等）替换原生 checkbox 列表。
import { Check, ChevronDown, Search, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { SearchableSelectOption } from "./SearchableSelect";

interface Props {
  value: (string | number)[];
  onChange: (value: (string | number)[]) => void;
  options: SearchableSelectOption[];
  placeholder?: string;
  emptyText?: string;
  disabled?: boolean;
  className?: string;
  style?: React.CSSProperties;
}

export function SearchableMultiSelect({
  value,
  onChange,
  options,
  placeholder = "请选择",
  emptyText = "无匹配项",
  disabled = false,
  className = "form-control",
  style,
}: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIdx, setActiveIdx] = useState(0);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const selectedSet = useMemo(() => new Set(value), [value]);
  const selectedOptions = useMemo(
    () => options.filter((o) => selectedSet.has(o.value)),
    [options, selectedSet],
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return options;
    return options.filter(
      (o) =>
        o.label.toLowerCase().includes(q) ||
        (o.subtitle ?? "").toLowerCase().includes(q) ||
        String(o.value).toLowerCase().includes(q),
    );
  }, [options, query]);

  useEffect(() => {
    if (!open) return;
    function onClickOutside(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
        setQuery("");
      }
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, [open]);

  useEffect(() => {
    if (open) {
      setActiveIdx(0);
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [open]);

  // 多选：选中状态切换，下拉框保持打开（便于连续多选）
  function toggle(opt: SearchableSelectOption) {
    if (selectedSet.has(opt.value)) {
      onChange(value.filter((v) => v !== opt.value));
    } else {
      onChange([...value, opt.value]);
    }
  }

  function removeChip(e: React.MouseEvent, v: string | number) {
    e.stopPropagation();
    onChange(value.filter((x) => x !== v));
  }

  function onKey(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIdx((i) => Math.min(filtered.length - 1, i + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIdx((i) => Math.max(0, i - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const opt = filtered[activeIdx];
      if (opt) toggle(opt);
    } else if (e.key === "Escape") {
      setOpen(false);
      setQuery("");
    }
  }

  return (
    <div ref={wrapperRef} style={{ position: "relative", ...style }}>
      {/* trigger — 已选项以 chip 呈现 */}
      <button
        type="button"
        disabled={disabled}
        onClick={() => !disabled && setOpen((v) => !v)}
        className={className}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          textAlign: "left",
          background: disabled ? "#f3f4f6" : "white",
          cursor: disabled ? "not-allowed" : "pointer",
          width: "100%",
          minHeight: 32,
          padding: "5px 10px",
        }}
      >
        <span style={{ flex: 1, display: "flex", flexWrap: "wrap", gap: 4, minWidth: 0 }}>
          {selectedOptions.length === 0 ? (
            <span style={{ color: "#9ca3af", fontSize: 13 }}>{placeholder}</span>
          ) : (
            selectedOptions.map((o) => (
              <span
                key={o.value}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 4,
                  fontSize: 12,
                  padding: "2px 6px",
                  borderRadius: 4,
                  background: "#eff6ff",
                  color: "var(--color-primary)",
                }}
              >
                {o.label}
                {!disabled && (
                  <X
                    className="w-3 h-3"
                    style={{ cursor: "pointer" }}
                    onClick={(e) => removeChip(e, o.value)}
                  />
                )}
              </span>
            ))
          )}
        </span>
        <ChevronDown className="w-3.5 h-3.5" style={{ color: "#9ca3af", flexShrink: 0 }} />
      </button>

      {/* dropdown */}
      {open && (
        <div
          style={{
            position: "absolute",
            top: "calc(100% + 4px)",
            left: 0,
            right: 0,
            background: "white",
            border: "1px solid var(--color-neutral-200)",
            borderRadius: 6,
            boxShadow: "0 4px 12px rgba(0,0,0,.1)",
            zIndex: 50,
            maxHeight: 280,
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
          }}
        >
          {/* search input */}
          <div style={{ padding: 6, borderBottom: "1px solid #f3f4f6", display: "flex", alignItems: "center", gap: 6 }}>
            <Search className="w-3.5 h-3.5" style={{ color: "#9ca3af" }} />
            <input
              ref={inputRef}
              value={query}
              onChange={(e) => { setQuery(e.target.value); setActiveIdx(0); }}
              onKeyDown={onKey}
              placeholder="搜索..."
              style={{ flex: 1, border: "none", outline: "none", fontSize: 13, padding: "4px 0" }}
            />
          </div>

          {/* options list */}
          <div style={{ overflowY: "auto", flex: 1 }}>
            {filtered.length === 0 ? (
              <div style={{ padding: "16px 12px", fontSize: 12, color: "#9ca3af", textAlign: "center" }}>
                {emptyText}
              </div>
            ) : (
              filtered.map((opt, idx) => {
                const isSel = selectedSet.has(opt.value);
                const isActive = idx === activeIdx;
                return (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => toggle(opt)}
                    onMouseEnter={() => setActiveIdx(idx)}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      padding: "8px 12px",
                      width: "100%",
                      border: "none",
                      background: isActive ? "#f3f4f6" : isSel ? "#eff6ff" : "transparent",
                      color: isSel ? "var(--color-primary)" : "var(--color-neutral-700)",
                      fontSize: 13,
                      fontWeight: isSel ? 600 : 400,
                      cursor: "pointer",
                      textAlign: "left",
                    }}
                  >
                    <span
                      style={{
                        width: 14,
                        height: 14,
                        flexShrink: 0,
                        borderRadius: 3,
                        border: isSel ? "none" : "1px solid var(--color-neutral-200, #e5e7eb)",
                        background: isSel ? "var(--color-primary)" : "white",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                      }}
                    >
                      {isSel && <Check className="w-3 h-3" style={{ color: "white" }} />}
                    </span>
                    <span style={{ display: "flex", flexDirection: "column", gap: 1 }}>
                      <span>{opt.label}</span>
                      {opt.subtitle && (
                        <span style={{ fontSize: 11, color: "#9ca3af" }}>{opt.subtitle}</span>
                      )}
                    </span>
                  </button>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
