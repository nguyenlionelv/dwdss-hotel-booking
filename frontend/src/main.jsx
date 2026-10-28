import React from 'react';
import ReactDOM from 'react-dom/client';
import { RouterProvider } from 'react-router-dom';
import { SystemProvider } from './hooks/useSystemContext';
import { router } from './app/router';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <SystemProvider>
      <RouterProvider router={router} />
    </SystemProvider>
  </React.StrictMode>
);
