import React from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import Header from './Header';

export default function AppLayout() {
  return (
    <div className="min-h-screen bg-[#FAFAF8] text-[#252525] flex flex-col">
      <Sidebar />
      <div className="lg:pl-[240px] flex-1 flex flex-col min-w-0">
        <Header />
        <main className="px-6 py-6 sm:px-8 lg:px-10 lg:py-8 max-w-[1600px] w-full mx-auto space-y-8 lg:space-y-10 flex-1">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
