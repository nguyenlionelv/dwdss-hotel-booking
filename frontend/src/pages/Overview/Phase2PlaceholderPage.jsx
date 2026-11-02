import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Lock, BarChart3, FileSpreadsheet, BrainCircuit, ArrowLeft } from 'lucide-react';

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
    <div className="max-w-2xl mx-auto py-12">
      <Card className="text-center p-6 sm:p-8 space-y-4">
        <div className="w-12 h-12 rounded-lg bg-muted text-muted-foreground flex items-center justify-center mx-auto border">
          <Lock className="h-6 w-6 text-muted-foreground" />
        </div>

        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-50 text-amber-800 border border-amber-200 text-xs font-semibold uppercase tracking-wider">
          <span>{info.code} • Phase 2 Roadmap (Out of MVP Scope)</span>
        </div>

        <CardTitle className="text-xl sm:text-2xl font-display font-extrabold text-foreground">
          {info.title}
        </CardTitle>

        <CardDescription className="text-xs sm:text-sm text-muted-foreground max-w-lg mx-auto leading-relaxed">
          {info.desc} Theo tài liệu{' '}
          <code className="font-mono text-xs bg-muted px-1.5 py-0.5 rounded border">
            docs/scope_assessment.md
          </code>{' '}
          và{' '}
          <code className="font-mono text-xs bg-muted px-1.5 py-0.5 rounded border">
            docs/detailed_plan.md
          </code>
          , phạm vi MVP chính thức tập trung sâu vào{' '}
          <strong className="text-foreground">Daily Hotel Operations (City Hotel — Lisbon, Portugal)</strong>.
        </CardDescription>

        <div className="pt-4 flex flex-wrap items-center justify-center gap-2.5">
          <Button variant="default" size="sm" asChild className="gap-1.5">
            <Link to="/analytics/operations">
              <BarChart3 className="h-4 w-4" />
              <span>Về Operations Analytics (BI-01)</span>
            </Link>
          </Button>
          <Button variant="outline" size="sm" asChild className="gap-1.5">
            <Link to="/reports/operations">
              <FileSpreadsheet className="h-4 w-4 text-emerald-600" />
              <span>Mở Operations Reports (DO-R01)</span>
            </Link>
          </Button>
          <Button variant="emerald" size="sm" asChild className="gap-1.5">
            <Link to="/dss/demand-forecast">
              <BrainCircuit className="h-4 w-4" />
              <span>Mở DSS Demand Forecast (DO-M01)</span>
            </Link>
          </Button>
        </div>
      </Card>
    </div>
  );
}
