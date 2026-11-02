import React from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import Header from './Header';

export default function AppLayout() {
  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col">
      <Sidebar />
      <div className="lg:pl-64 flex-1 flex flex-col min-w-0 transition-all">
        <Header />
        <main className="p-4 sm:p-6 lg:p-8 max-w-[1600px] w-full mx-auto space-y-6 flex-1">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
