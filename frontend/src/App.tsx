import React, { Suspense, lazy } from "react";
import { HashRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ToastProvider } from "./context/ToastContext";
import { SymbolProvider } from "./context/SymbolContext";
import { Sidebar } from "./components/layout/Sidebar";
import { TopBar } from "./components/layout/TopBar";

const DashboardPage = lazy(() =>
  import("./pages/DashboardPage").then((module) => ({ default: module.DashboardPage }))
);
const ScannerPage = lazy(() =>
  import("./pages/ScannerPage").then((module) => ({ default: module.ScannerPage }))
);
const SignalsPage = lazy(() =>
  import("./pages/SignalsPage").then((module) => ({ default: module.SignalsPage }))
);
const RegimePage = lazy(() =>
  import("./pages/RegimePage").then((module) => ({ default: module.RegimePage }))
);
const SetupsPage = lazy(() =>
  import("./pages/SetupsPage").then((module) => ({ default: module.SetupsPage }))
);
const CandlesPage = lazy(() =>
  import("./pages/CandlesPage").then((module) => ({ default: module.CandlesPage }))
);
const SettingsPage = lazy(() =>
  import("./pages/SettingsPage").then((module) => ({ default: module.SettingsPage }))
);
const RiskControlPage = lazy(() =>
  import("./pages/RiskControlPage").then((module) => ({ default: module.RiskControlPage }))
);
const ActiveTradesPage = lazy(() =>
  import("./pages/ActiveTradesPage").then((module) => ({ default: module.ActiveTradesPage }))
);
const TradeJournalPage = lazy(() =>
  import("./pages/TradeJournalPage").then((module) => ({ default: module.TradeJournalPage }))
);

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

export default function App() {
  const [isMobileOpen, setIsMobileOpen] = React.useState(false);

  const pageFallback = (
    <div className="flex min-h-[50vh] items-center justify-center">
      <div className="rounded-xl border border-slate-800 bg-slate-900/70 px-5 py-4 text-xs font-mono text-slate-400">
        Loading workspace feed...
      </div>
    </div>
  );

  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <SymbolProvider>
          <HashRouter>
            <div className="flex min-h-screen bg-[#090d16] text-slate-100 font-sans antialiased selection:bg-amber-500 selection:text-black">
              {/* Desktop Sidebar (Persistent) */}
              <div className="hidden lg:block w-64 border-r border-slate-800/80 shrink-0 sticky top-0 h-screen">
                <Sidebar />
              </div>

              {/* Mobile Drawer Backdrop */}
              {isMobileOpen && (
                <div
                  className="fixed inset-0 bg-black/70 z-40 lg:hidden backdrop-blur-sm transition-opacity"
                  onClick={() => setIsMobileOpen(false)}
                />
              )}

              {/* Mobile Drawer Sidebar */}
              <div
                className={`fixed inset-y-0 left-0 w-64 bg-slate-950 border-r border-slate-800/80 z-50 transform lg:hidden transition-transform duration-300 ease-in-out ${
                  isMobileOpen ? "translate-x-0" : "-translate-x-full"
                }`}
              >
                <Sidebar onClose={() => setIsMobileOpen(false)} />
              </div>

              {/* Main Content Area */}
              <div className="flex-1 flex flex-col min-w-0">
                <TopBar onMenuClick={() => setIsMobileOpen(true)} />
                <main className="flex-1 overflow-y-auto">
                  <Suspense fallback={pageFallback}>
                    <Routes>
                      <Route path="/" element={<DashboardPage />} />
                      <Route path="/scanner" element={<ScannerPage />} />
                      <Route path="/signals" element={<SignalsPage />} />
                      <Route path="/regime" element={<RegimePage />} />
                      <Route path="/setups" element={<SetupsPage />} />
                      <Route path="/candles" element={<CandlesPage />} />
                      <Route path="/risk" element={<RiskControlPage />} />
                      <Route path="/active-trades" element={<ActiveTradesPage />} />
                      <Route path="/trade-journal" element={<TradeJournalPage />} />
                      <Route path="/settings" element={<SettingsPage />} />
                      <Route path="*" element={<Navigate to="/" replace />} />
                    </Routes>
                  </Suspense>
                </main>
              </div>
            </div>
          </HashRouter>
        </SymbolProvider>
      </ToastProvider>
    </QueryClientProvider>
  );
}
