import React from 'react';
import { createBrowserRouter, Navigate } from 'react-router-dom';
import AppLayout from '../components/layout/AppLayout';
import OperationsAnalyticsPage from '../pages/Analytics/Operations/OperationsAnalyticsPage';
import OperationsReportsPage from '../pages/Reports/Operations/OperationsReportsPage';
import DemandForecastPage from '../pages/DSS/DemandForecast/DemandForecastPage';
import Phase2PlaceholderPage from '../pages/Overview/Phase2PlaceholderPage';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    children: [
      {
        index: true,
        element: <Navigate to="/analytics/operations" replace />,
      },
      {
        path: 'analytics',
        element: <Navigate to="/analytics/operations" replace />,
      },
      {
        path: 'analytics/operations',
        element: <OperationsAnalyticsPage />,
      },
      {
        path: 'reports',
        element: <Navigate to="/reports/operations" replace />,
      },
      {
        path: 'reports/operations',
        element: <OperationsReportsPage />,
      },
      {
        path: 'dss',
        element: <Navigate to="/dss/demand-forecast" replace />,
      },
      {
        path: 'dss/demand-forecast',
        element: <DemandForecastPage />,
      },
      // Phase 2 Out-of-Scope Routes
      {
        path: 'analytics/guest-customer',
        element: <Phase2PlaceholderPage />,
      },
      {
        path: 'analytics/revenue-cancellation',
        element: <Phase2PlaceholderPage />,
      },
      {
        path: 'analytics/booking-performance',
        element: <Phase2PlaceholderPage />,
      },
      {
        path: '*',
        element: <Navigate to="/analytics/operations" replace />,
      },
    ],
  },
]);
