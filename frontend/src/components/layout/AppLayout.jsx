import React from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import Header from './Header';

export default function AppLayout() {
  return (
    <div className="min-h-screen bg-[#f4f5f8] text-slate-900 flex">
      <Sidebar />
      <div className="ml-[260px] flex-1 flex flex-col min-w-0">
        <Header />
        <main className="p-8 max-w-[1600px] w-full mx-auto space-y-7 flex-1">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
