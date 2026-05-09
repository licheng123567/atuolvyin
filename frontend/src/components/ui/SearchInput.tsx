// v1.6.5 — 通用搜索输入框（带 icon + 清除按钮 + 受控）
//
// 用法：
//   const [keyword, setKeyword] = useState("");
//   <SearchInput value={keyword} onChange={setKeyword} placeholder="按姓名/手机号搜索" />
//
// 注意：此组件本身不做 debounce，调用方按需用 useDebouncedValue 包一层。
import { Search, X } from "lucide-react";

interface Props {
  value: string;
  onChange: (next: string) => void;
  placeholder?: string;
  width?: number | string;
}

export function SearchInput({
  value,
  onChange,
  placeholder = "搜索",
  width = 220,
}: Props) {
  return (
    <div style={{ position: "relative", display: "inline-block", width }}>
      <Search
        size={14}
        style={{
          position: "absolute",
          left: 8,
          top: "50%",
          transform: "translateY(-50%)",
          color: "var(--color-neutral-400)",
          pointerEvents: "none",
        }}
      />
      <input
        type="text"
        className="form-control"
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={{
          paddingLeft: 28,
          paddingRight: value ? 28 : 10,
          width: "100%",
          height: 32,
          fontSize: 13,
        }}
      />
      {value && (
        <button
          type="button"
          onClick={() => onChange("")}
          aria-label="清除搜索"
          style={{
            position: "absolute",
            right: 6,
            top: "50%",
            transform: "translateY(-50%)",
            background: "none",
            border: "none",
            cursor: "pointer",
            color: "var(--color-neutral-400)",
            padding: 2,
            display: "flex",
            alignItems: "center",
          }}
        >
          <X size={13} />
        </button>
      )}
    </div>
  );
}
