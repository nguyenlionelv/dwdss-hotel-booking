import React, { useId } from 'react';

export default function SegmentedControl({ label, value, onChange, options }) {
  const id = useId();
  return (
    <fieldset className="min-w-0 max-w-full space-y-2.5">
      <legend className="text-[12px] font-normal text-ink-secondary">{label}</legend>
      <div className="time-grain-control max-w-full flex-wrap gap-y-1">
        {options.map(option => (
          <label key={option.value} className="relative">
            <input type="radio" name={id} value={option.value} checked={value === option.value}
              onChange={() => onChange(option.value)} className="time-grain-input sr-only" />
            <span className="time-grain-option">{option.label}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
