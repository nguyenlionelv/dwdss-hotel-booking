import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-[4px] text-xs font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-3.5 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default:
          "bg-brand text-white hover:bg-brand-hover",
        destructive:
          "bg-status-critical text-white hover:bg-status-critical/90",
        outline:
          "border border-divider bg-transparent text-ink-primary hover:bg-surface-subtle",
        secondary:
          "border border-divider bg-surface-primary text-ink-primary hover:bg-surface-subtle",
        ghost:
          "text-ink-secondary hover:text-ink-primary hover:bg-surface-subtle",
        link:
          "text-brand underline-offset-4 hover:underline p-0 h-auto",
        emerald:
          "bg-brand text-white hover:bg-brand-hover",
      },
      size: {
        default: "h-8 px-3 py-1.5",
        sm: "h-7 rounded-[4px] px-2.5 text-xs",
        lg: "h-9 rounded-[4px] px-4 text-sm",
        icon: "h-8 w-8",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

const Button = React.forwardRef(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
