import * as React from "react";
import { cva } from "class-variance-authority";
import { cn } from "@/lib/utils";

/**
 * Compact status indicator & metadata label (DESIGN.md Section 6.4):
 * Restrained, non-pill, minimal borders, semantic dot option.
 */
const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-[3px] border px-1.5 py-0.5 text-[11px] font-medium leading-tight transition-colors",
  {
    variants: {
      variant: {
        default:
          "border-divider bg-surface-primary text-ink-primary",
        secondary:
          "border-divider bg-surface-subtle text-ink-secondary",
        destructive:
          "border-status-critical/30 bg-status-critical/10 text-status-critical",
        outline:
          "border-divider bg-transparent text-ink-secondary",
        emerald:
          "border-status-success/30 bg-status-success/10 text-status-success",
        amber:
          "border-status-warning/35 bg-status-warning/10 text-status-warning",
        blue:
          "border-series-3/30 bg-series-3/10 text-series-3",
        slate:
          "border-divider bg-surface-subtle text-ink-secondary",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

function Badge({ className, variant, ...props }) {
  return (
    <span className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
