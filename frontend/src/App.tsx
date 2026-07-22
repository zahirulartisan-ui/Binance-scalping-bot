import React from "react";
import { HashRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ToastProvider } from "./context/ToastContext";
import { SymbolProvider } from "./context/SymbolContext";
import { Sidebar } from "./components/layout/Sidebar";
import { TopBar } from "./components/layout/TopBar";
import { DashboardPage } from "./pages/DashboardPage";
import { ScannerPage } from "./pages/ScannerPage";
import { SignalsPage } from "./pages/SignalsPage";
import { RegimePage } from "./pages/RegimePage";
import { SetupsPage } from "./pages/SetupsPage";
import { CandlesPage } from "./pages/CandlesPage";
import { SettingsPage } from "./pages/SettingsPage";
import { RiskControlPage } from "./pages/RiskControlPage";
import { ActiveTradesPage } from "./pages/ActiveTradesPage";
import { TradeJournalPage } from "./pages/TradeJournalPage";

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
                </main>
              </div>
            </div>
          </HashRouter>
        </SymbolProvider>
      </ToastProvider>
    </QueryClientProvider>
  );
}
