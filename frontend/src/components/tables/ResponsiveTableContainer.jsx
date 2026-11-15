import React from 'react';
import { cn } from '@/lib/utils';

/**
 * Accessible Scrollable Table Container following modern-web-guidance (responsive-table)
 * and DESIGN.md Section 5.4 & 6.1:
 * - Focusable container (tabIndex={0}) with role="region" and aria-label / aria-labelledby
 * - Minimal 1px border (border-divider), no shadows or large rounded corners
 */
export default function ResponsiveTableContainer({
  ariaLabel,
  ariaLabelledBy,
  children,
  className = '',
}) {
  return (
    <div
      className={cn(
        'table-scroll-region border border-divider bg-surface-primary',
        className
      )}
      role="region"
      aria-label={ariaLabel}
      aria-labelledby={ariaLabelledBy}
      tabIndex={0}
    >
      {children}
    </div>
  );
}
