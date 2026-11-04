import React from 'react';
import { cn } from '@/lib/utils';

/**
 * Accessible Scrollable Table Container following modern-web-guidance (responsive-table):
 * - Focusable container (tabIndex={0}) for keyboard horizontal scrolling
 * - Explicit role="region" and aria-label / aria-labelledby
 * - Sticky thead via .table-scroll-region CSS
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
        'table-scroll-region border rounded-md bg-card shadow-2xs',
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
