import React from "react";
import { ChevronDown } from "lucide-react";

export default function CompactFilter({ id, label, value, onChange, options }) {
  const selectedLabel = options.find((option) => option.value === value)?.label || "";

  return (
    <div className="flex w-full min-w-0 max-w-full flex-col gap-2.5 sm:w-48">
      <label htmlFor={id} className="text-[12px] text-ink-secondary">
        {label}
      </label>
      <div className="relative h-9 w-full">
        <select
          id={id}
          value={value}
          title={options.find((option) => option.value === value)?.title || selectedLabel}
          onChange={onChange}
          className="absolute inset-0 h-9 w-full min-w-0 appearance-none rounded-[4px] border border-divider bg-surface-primary pl-3 pr-9 text-[13px] font-normal text-ink-primary transition-colors hover:border-ink-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
        >
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <ChevronDown aria-hidden="true" className="pointer-events-none absolute right-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-secondary" />
      </div>
    </div>
  );
}
