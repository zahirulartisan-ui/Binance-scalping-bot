import React from "react";
import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  TrendingUp,
  SlidersHorizontal,
  BarChart2,
  Settings,
  Bot,
  Zap,
  Sparkles,
  Activity,
  ShieldAlert,
  Layers,
  BookOpen,
  X,
} from "lucide-react";

export const Sidebar: React.FC<{ onClose?: () => void }> = ({ onClose }) => {
  const navItems = [
    { path: "/", label: "Dashboard", icon: LayoutDashboard },
    { path: "/scanner", label: "AI Market Scanner", icon: Sparkles },
    { path: "/signals", label: "Trading Signals", icon: Activity },
    { path: "/setups", label: "Strategy Setups", icon: SlidersHorizontal },
    { path: "/active-trades", label: "Active Trades", icon: Layers },
    { path: "/trade-journal", label: "Trade Journal", icon: BookOpen },
    { path: "/regime", label: "Market Regime", icon: TrendingUp },
    { path: "/candles", label: "Symbols & Candles", icon: BarChart2 },
    { path: "/risk", label: "Risk Control", icon: ShieldAlert },
    { path: "/settings", label: "Settings", icon: Settings },
  ];

  return (
    <aside className="w-full h-full bg-slate-950 flex flex-col justify-between select-none">
      <div>
        {/* Brand Header */}
        <div className="p-5 border-b border-slate-800/80 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-500 to-amber-700 p-0.5 shadow-lg shadow-amber-950/40 flex items-center justify-center">
              <div className="w-full h-full bg-slate-950 rounded-[10px] flex items-center justify-center">
                <Bot className="w-5 h-5 text-amber-400" />
              </div>
            </div>
            <div>
              <div className="flex items-center gap-1.5 font-extrabold text-slate-100 text-sm tracking-tight font-mono">
                SCALPER<span className="text-amber-400 font-sans">BOT</span>
              </div>
              <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider flex items-center gap-1">
                <Zap className="w-3 h-3 text-emerald-400 inline" /> Binance HFT Engine
              </div>
            </div>
          </div>
          {onClose && (
            <button
              onClick={onClose}
              className="lg:hidden p-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-100 transition"
              title="Close Navigation Menu"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Navigation Section */}
        <nav className="p-3 space-y-1">
          <div className="px-3 py-2 text-[10px] font-mono text-slate-400 uppercase tracking-widest font-semibold">
            Terminal Views
          </div>
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.path === "/"}
                onClick={() => {
                  if (onClose) onClose();
                }}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-xs font-mono transition-all group ${
                    isActive
                      ? "bg-slate-900 text-amber-400 border border-amber-500/30 font-semibold shadow-sm"
                      : "text-slate-400 hover:text-slate-100 hover:bg-slate-900/60"
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon
                      className={`w-4 h-4 transition-colors ${
                        isActive ? "text-amber-400" : "text-slate-400 group-hover:text-slate-200"
                      }`}
                    />
                    <span>{item.label}</span>
                  </>
                )}
              </NavLink>
            );
          })}
        </nav>
      </div>

      {/* Terminal Footer Info */}
      <div className="p-4 m-3 rounded-xl bg-slate-900/80 border border-slate-800 text-[11px] font-mono text-slate-400 space-y-2">
        <div className="flex items-center justify-between text-slate-300 font-semibold">
          <span>Engine Mode</span>
          <span className="text-emerald-400">REST Polling</span>
        </div>
        <div className="text-[10px] text-slate-400 leading-tight">
          Read-mostly dashboard. Auto-trading executes server-side.
        </div>
      </div>
    </aside>
  );
};
