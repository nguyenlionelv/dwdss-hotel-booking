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
          "border-[#E5E5E0] bg-[#FFFFFF] text-[#252525]",
        secondary:
          "border-[#E5E5E0] bg-[#F4F4F0] text-[#666666]",
        destructive:
          "border-[#B64C43]/30 bg-[#B64C43]/5 text-[#B64C43]",
        outline:
          "border-[#E5E5E0] bg-transparent text-[#666666]",
        emerald:
          "border-[#477A61]/30 bg-[#477A61]/5 text-[#477A61]",
        amber:
          "border-[#C58B35]/35 bg-[#C58B35]/5 text-[#9A681E]",
        blue:
          "border-[#547A9B]/30 bg-[#547A9B]/5 text-[#547A9B]",
        slate:
          "border-[#E5E5E0] bg-[#F4F4F0] text-[#666666]",
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
