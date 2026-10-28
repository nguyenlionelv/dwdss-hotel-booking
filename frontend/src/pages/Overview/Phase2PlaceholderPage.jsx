import React from 'react';
import { Link, useLocation } from 'react-router-dom';

const DOMAIN_INFO = {
  '/analytics/guest-customer': {
    title: 'Guest & Customer Composition Analytics',
    code: 'MART-02 / BI-02',
    desc: 'Phân tích cơ cấu khách (Single / Couple / Family), quy mô đoàn và lựa chọn hạng phòng.',
  },
  '/analytics/revenue-cancellation': {
    title: 'Revenue & Cancellation Risk Analytics',
    code: 'MART-03 / BI-03',
    desc: 'Phân tích tỷ lệ hủy đặt phòng theo Lead-time, Deposit Type và phân khúc thị trường.',
  },
  '/analytics/booking-performance': {
    title: 'Booking Channel & Segment Performance',
    code: 'MART-04 / BI-04',
    desc: 'Đánh giá hiệu quả kênh phân phối (OTA, Direct, Corporate) và đại lý du lịch.',
  },
};

export default function Phase2PlaceholderPage() {
  const location = useLocation();
  const info = DOMAIN_INFO[location.pathname] || {
    title: 'Phase 2 Extended Hospitality Domain',
    code: 'PHASE-2',
    desc: 'Phân hệ mở rộng nằm ngoài phạm vi MVP hiện tại của dự án.',
  };

  return (
    <div className="max-w-3xl mx-auto py-12">
      <div className="quixotic-card p-8 text-center space-y-5">
        <div className="w-14 h-14 rounded-2xl bg-slate-100 text-slate-600 flex items-center justify-center mx-auto">
          <span className="material-symbols-outlined text-3xl">lock_clock</span>
        </div>

        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-50 text-amber-800 border border-amber-200 text-xs font-bold uppercase tracking-wider">
          <span>{info.code} • Phase 2 Roadmap (Out of MVP Scope)</span>
        </div>

        <h1 className="text-2xl font-display font-extrabold text-slate-900">
          {info.title}
        </h1>

        <p className="text-sm text-slate-600 max-w-xl mx-auto leading-relaxed">
          {info.desc} Theo tài liệu{' '}
          <code className="font-mono text-xs bg-slate-100 px-1.5 py-0.5 rounded">
            docs/scope_assessment.md
          </code>{' '}
          và{' '}
          <code className="font-mono text-xs bg-slate-100 px-1.5 py-0.5 rounded">
            docs/detailed_plan.md
          </code>
          , phạm vi MVP chính thức tập trung sâu vào{' '}
          <strong>Daily Hotel Operations (City Hotel — Lisbon, Portugal)</strong>.
        </p>

        <div className="pt-4 flex flex-wrap items-center justify-center gap-3">
          <Link
            to="/analytics/operations"
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-[#0059b5] text-white text-xs font-bold shadow-sm hover:bg-[#00438a] transition-all"
          >
            <span className="material-symbols-outlined text-[18px]">analytics</span>
            Về Operations Analytics (BI-01)
          </Link>
          <Link
            to="/reports/operations"
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white border border-slate-200 text-slate-700 text-xs font-bold hover:bg-slate-50 transition-all"
          >
            <span className="material-symbols-outlined text-[18px]">assessment</span>
            Mở Operations Reports (DO-R01)
          </Link>
          <Link
            to="/dss/demand-forecast"
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-emerald-600 text-white text-xs font-bold shadow-sm hover:bg-emerald-700 transition-all"
          >
            <span className="material-symbols-outlined text-[18px]">psychology</span>
            Mở DSS Demand Forecast (DO-M01)
          </Link>
        </div>
      </div>
    </div>
  );
}
