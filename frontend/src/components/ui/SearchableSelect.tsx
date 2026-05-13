// v1.5.6 — 可搜索下拉（零依赖；样式贴合 .form-control）
// 用法：长选项列表（≥ 8 项）建议替换原生 <select>，短列表保持 native。
import { ChevronDown, Search, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

export interface SearchableSelectOption {
  value: string | number;
  label: string;
  // 可选副标题（用于显示手机号 / 子标签）
  subtitle?: string;
}

interface Props {
  value: string | number | null | "";
  onChange: (value: string | number | "") => void;
  options: SearchableSelectOption[];
  placeholder?: string;
  emptyText?: string;
  disabled?: boolean;
  allowClear?: boolean;
  className?: string;
  style?: React.CSSProperties;
}

export function SearchableSelect({
  value,
  onChange,
  options,
  placeholder = "请选择",
  emptyText = "无匹配项",
  disabled = false,
  allowClear = true,
  className = "form-control",
  style,
}: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIdx, setActiveIdx] = useState(0);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const selected = useMemo(
    () => options.find((o) => o.value === value) ?? null,
    [options, value],
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

  function pick(opt: SearchableSelectOption) {
    onChange(opt.value);
    setOpen(false);
    setQuery("");
  }

  function clear(e: React.MouseEvent) {
    e.stopPropagation();
    onChange("");
    setQuery("");
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
      if (opt) pick(opt);
    } else if (e.key === "Escape") {
      setOpen(false);
      setQuery("");
    }
  }

  return (
    <div
      ref={wrapperRef}
      style={{ position: "relative", ...style }}
    >
      {/* trigger */}
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
          padding: "6px 10px",
        }}
      >
        <span style={{ flex: 1, color: selected ? "inherit" : "#9ca3af", fontSize: 13, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {selected ? selected.label : placeholder}
        </span>
        {allowClear && selected && !disabled && (
          <X
            className="w-3 h-3"
            style={{ color: "#9ca3af", cursor: "pointer" }}
            onClick={clear}
          />
        )}
        <ChevronDown className="w-3.5 h-3.5" style={{ color: "#9ca3af" }} />
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
                const isSel = opt.value === value;
                const isActive = idx === activeIdx;
                return (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => pick(opt)}
                    onMouseEnter={() => setActiveIdx(idx)}
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "flex-start",
                      gap: 1,
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
                    <span>{opt.label}</span>
                    {opt.subtitle && (
                      <span style={{ fontSize: 11, color: "#9ca3af" }}>{opt.subtitle}</span>
                    )}
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
