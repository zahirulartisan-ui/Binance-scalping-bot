import React, { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../api/client";
import { useTabVisibility } from "../hooks/useTabVisibility";
import { useToast } from "../context/ToastContext";
import { ConfirmDialog } from "../components/common/ConfirmDialog";
import {
  ShieldAlert,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Clock,
  Activity,
  Sliders,
  Server,
  Radio,
  WifiOff,
  Signal,
  HelpCircle,
} from "lucide-react";

export const RiskControlPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const isTabVisible = useTabVisibility();

  const [isOfflineMode, setIsOfflineMode] = useState(false);
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);

  // Safety controls confirmation state
  const [confirmModal, setConfirmModal] = useState<{
    isOpen: boolean;
    title: string;
    description: string;
    targetField: "emergency_stop" | "execution_enabled";
    newValue: boolean;
    currentValue: boolean;
    warning: string;
  }>({
    isOpen: false,
    title: "",
    description: "",
    targetField: "emergency_stop",
    newValue: false,
    currentValue: false,
    warning: "",
  });

  // Queries (polling every 10 seconds, paused if tab is hidden)
  const {
    data: health,
    isLoading: isLoadingHealth,
    isError: isErrorHealth,
    error: errorHealth,
    refetch: refetchHealth,
    isStale: isStaleHealth,
  } = useQuery({
    queryKey: ["health"],
    queryFn: async () => {
      try {
        // Direct test fetch to see if we are in real API or mock fallback
        const base = (import.meta as any).env?.VITE_API_BASE_URL || "http://localhost:8000";
        const testRes = await fetch(`${base.replace(/\/+$/, "")}/health`, { method: "GET" }).catch(() => null);
        setIsOfflineMode(!testRes || !testRes.ok);
      } catch {
        setIsOfflineMode(true);
      }
      return apiClient.getHealth();
    },
    refetchInterval: isTabVisible ? 10000 : false,
  });

  const {
    data: settings,
    isLoading: isLoadingSettings,
    isError: isErrorSettings,
    error: errorSettings,
    refetch: refetchSettings,
    isStale: isStaleSettings,
  } = useQuery({
    queryKey: ["settings"],
    queryFn: () => apiClient.getSettings(),
    refetchInterval: isTabVisible ? 10000 : false,
  });

  const {
    data: marketDataStatus,
    isLoading: isLoadingMarketStatus,
    isError: isErrorMarketStatus,
    error: errorMarketStatus,
    refetch: refetchMarketStatus,
    isStale: isStaleMarketStatus,
  } = useQuery({
    queryKey: ["marketDataStatus"],
    queryFn: () => apiClient.getMarketDataStatus(),
    refetchInterval: isTabVisible ? 10000 : false,
  });

  const {
    data: btcRegime,
    isLoading: isLoadingBtcRegime,
    isError: isErrorBtcRegime,
    error: errorBtcRegime,
    refetch: refetchBtcRegime,
    isStale: isStaleBtcRegime,
  } = useQuery({
    queryKey: ["btcRegime"],
    queryFn: () => apiClient.getMarketRegimeBtc(),
    refetchInterval: isTabVisible ? 10000 : false,
  });

  useEffect(() => {
    if (health || settings || marketDataStatus || btcRegime) {
      setLastRefreshed(new Date());
    }
  }, [health, settings, marketDataStatus, btcRegime]);

  // Combined Loading & Error States
  const isLoading = isLoadingHealth || isLoadingSettings || isLoadingMarketStatus || isLoadingBtcRegime;
  const isAnyError = isErrorHealth || isErrorSettings || isErrorMarketStatus || isErrorBtcRegime;

  const handleManualRefresh = async () => {
    await Promise.all([
      refetchHealth(),
      refetchSettings(),
      refetchMarketStatus(),
      refetchBtcRegime(),
    ]);
    showToast({
      type: "info",
      title: "Data Refreshed",
      message: "Risk parameters and engine statuses have been updated.",
    });
  };

  // Mutation for settings modification (emergency stop / execution toggle)
  const patchMutation = useMutation({
    mutationFn: (patch: Record<string, any>) => apiClient.patchSettings(patch),
    onSuccess: (updated) => {
      queryClient.setQueryData(["settings"], updated);
      queryClient.invalidateQueries({ queryKey: ["health"] });
      setConfirmModal((prev) => ({ ...prev, isOpen: false }));
      showToast({
        type: "success",
        title: "Safety Parameter Updated",
        message: "Status successfully written and verified by the backend.",
      });
    },
    onError: (err: any) => {
      showToast({
        type: "error",
        title: "Action Rejected",
        message: err?.message || "Failed to submit safety action to engine.",
      });
    },
  });

  // Calculate overall state
  const getOverallState = (): {
    label: "SAFE" | "WARNING" | "BLOCKED" | "DISABLED" | "UNKNOWN";
    color: string;
    bgColor: string;
    borderColor: string;
    icon: React.ReactNode;
    desc: string;
  } => {
    if (isLoading) {
      return {
        label: "UNKNOWN",
        color: "text-slate-400",
        bgColor: "bg-slate-950/80",
        borderColor: "border-slate-800",
        icon: <HelpCircle className="w-5 h-5 text-slate-400" />,
        desc: "Checking engine parameters and fetching current network schemas...",
      };
    }

    if (isAnyError) {
      return {
        label: "UNKNOWN",
        color: "text-slate-400",
        bgColor: "bg-slate-950/80",
        borderColor: "border-slate-800",
        icon: <HelpCircle className="w-5 h-5 text-slate-400" />,
        desc: "Unable to retrieve critical server status. Reconnecting...",
      };
    }

    if (settings?.emergency_stop) {
      return {
        label: "BLOCKED",
        color: "text-rose-400",
        bgColor: "bg-rose-950/60",
        borderColor: "border-rose-500/50",
        icon: <ShieldAlert className="w-5 h-5 text-rose-400" />,
        desc: "EMERGENCY KILLSWITCH TRIGGERED. Order dispatch and strategy execution are strictly frozen.",
      };
    }

    if (btcRegime?.market_wide_block) {
      return {
        label: "BLOCKED",
        color: "text-rose-400",
        bgColor: "bg-rose-950/60",
        borderColor: "border-rose-500/50",
        icon: <ShieldAlert className="w-5 h-5 text-rose-400" />,
        desc: "Market-wide trade freeze active. Scalper execution is blocked by extreme volatility conditions.",
      };
    }

    if (!settings?.execution_enabled) {
      return {
        label: "DISABLED",
        color: "text-amber-400",
        bgColor: "bg-amber-950/40",
        borderColor: "border-amber-800/60",
        icon: <AlertTriangle className="w-5 h-5 text-amber-400" />,
        desc: "System running in passive analysis mode. Strategy engine evaluates setups but does not place trades.",
      };
    }

    // Check for warnings: degraded health, stale data, etc.
    const isHealthDegraded = health?.application?.status !== "ok" || health?.database?.status !== "ok";
    const dataAge = btcRegime?.evaluated_at
      ? (Date.now() - new Date(btcRegime.evaluated_at).getTime()) / 1000
      : 999;
    const isDataStale = dataAge > 30;

    if (isHealthDegraded || isDataStale || isOfflineMode) {
      return {
        label: "WARNING",
        color: "text-orange-400",
        bgColor: "bg-orange-950/40",
        borderColor: "border-orange-500/40",
        icon: <AlertTriangle className="w-5 h-5 text-orange-400" />,
        desc: "Engine online, but some telemetry data is stale or connection parameters are falling back.",
      };
    }

    return {
      label: "SAFE",
      color: "text-emerald-400",
      bgColor: "bg-emerald-950/40",
      borderColor: "border-emerald-500/30",
      icon: <ShieldCheck className="w-5 h-5 text-emerald-400" />,
      desc: "All health diagnostics pass. Order dispatch active in confirmed Demo Trading environment.",
    };
  };

  const overall = getOverallState();

  const triggerToggleEmergencyStop = (active: boolean) => {
    const title = active ? "ACTIVATE EMERGENCY STOP" : "DEACTIVATE EMERGENCY STOP";
    const description = active
      ? "You are activating the emergency system killswitch. This action immediately stops all order workflows and forces the auto-trading execution mode OFF."
      : "You are turning the emergency stop OFF. Please note that this will NOT automatically re-enable execution; you must review parameters first.";
    const warning = active
      ? "CRITICAL: This stops the bot immediately. Live order tracking will be frozen."
      : "WARNING: Ensure the market conditions have stabilized before enabling execution manually.";

    setConfirmModal({
      isOpen: true,
      title,
      description,
      targetField: "emergency_stop",
      newValue: active,
      currentValue: !!settings?.emergency_stop,
      warning,
    });
  };

  const triggerToggleExecution = (active: boolean) => {
    // If emergency stop is active, we cannot enable execution
    if (active && settings?.emergency_stop) {
      showToast({
        type: "error",
        title: "Execution Blocked",
        message: "Execution cannot be enabled while Emergency Stop is active.",
      });
      return;
    }

    const title = active ? "ENABLE AUTO TRADING EXECUTION" : "DISABLE AUTO TRADING EXECUTION";
    const description = active
      ? "You are enabling automated order dispatch. The bot will begin placing trades on Binance based on identified setups."
      : "You are disabling order dispatch. The bot will continue scanning but will not enter new positions.";
    const warning = active
      ? "CRITICAL: The bot will enter demo/live trades automatically using the allocated risk parameters."
      : "Note: Active open trades may still need manual management or will close on Take Profit/Stop Loss.";

    setConfirmModal({
      isOpen: true,
      title,
      description,
      targetField: "execution_enabled",
      newValue: active,
      currentValue: !!settings?.execution_enabled,
      warning,
    });
  };

  const confirmAndSubmitPatch = () => {
    const patch: Record<string, any> = {};
    patch[confirmModal.targetField] = confirmModal.newValue;

    // Optimistic rule: Turning emergency stop ON forces execution OFF
    if (confirmModal.targetField === "emergency_stop" && confirmModal.newValue === true) {
      patch["execution_enabled"] = false;
    }

    patchMutation.mutate(patch);
  };

  return (
    <div className="p-6 space-y-6 max-w-5xl mx-auto font-mono text-xs">
      {/* Header and Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-2xl font-black text-slate-100 tracking-tight flex items-center gap-2">
            <ShieldAlert className="w-6 h-6 text-rose-500 inline" /> ENGINE RISK CONTROL CENTER
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Real-time circuit breakers, safety diagnostics, and core risk boundaries.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* MOCK DATA OR PREVIEW MODE BADGE */}
          {isOfflineMode && (
            <span className="px-3 py-1 bg-amber-950/80 text-amber-400 border border-amber-500/40 rounded-lg font-bold text-[10px] uppercase flex items-center gap-1.5 animate-pulse">
              <WifiOff className="w-3.5 h-3.5" /> PREVIEW FALLBACK ACTIVE
            </span>
          )}

          {lastRefreshed && (
            <div className="text-slate-500 text-[10px] hidden md:flex items-center gap-1">
              <Clock className="w-3 h-3" /> Last check: {lastRefreshed.toLocaleTimeString()}
            </div>
          )}

          <button
            onClick={handleManualRefresh}
            disabled={isLoading}
            className="p-2 bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 rounded-lg flex items-center gap-1.5 transition disabled:opacity-40"
            title="Force refresh system telemetry"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
            <span>Force Sync</span>
          </button>
        </div>
      </div>

      {/* OVERALL SAFETY STATE BANNER */}
      <div className={`border rounded-xl p-5 ${overall.bgColor} ${overall.borderColor} transition-all`}>
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-start gap-4">
            <div className="p-3 bg-slate-950/80 rounded-xl border border-slate-800 shrink-0">
              {overall.icon}
            </div>
            <div className="space-y-1.5">
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-400 font-bold uppercase tracking-widest">
                  System Guard State:
                </span>
                <span className={`px-2 py-0.5 rounded text-[11px] font-black border uppercase tracking-wider ${
                  overall.label === "SAFE" ? "bg-emerald-950/80 border-emerald-500 text-emerald-400" :
                  overall.label === "WARNING" ? "bg-orange-950/80 border-orange-500 text-orange-400" :
                  overall.label === "BLOCKED" ? "bg-rose-950/80 border-rose-500 text-rose-400" :
                  "bg-slate-900 border-slate-700 text-slate-400"
                }`}>
                  {overall.label}
                </span>
              </div>
              <p className="text-slate-200 text-xs font-semibold leading-relaxed">
                {overall.desc}
              </p>
            </div>
          </div>

          {/* Quick Kill Switch Controls */}
          {!isLoading && !isAnyError && (
            <div className="flex flex-wrap items-center gap-3 shrink-0">
              {settings?.emergency_stop ? (
                <button
                  onClick={() => triggerToggleEmergencyStop(false)}
                  disabled={patchMutation.isPending}
                  className="px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 font-bold rounded-lg shadow transition flex items-center gap-2"
                >
                  <ShieldCheck className="w-4 h-4 text-emerald-400" /> Reset Stop
                </button>
              ) : (
                <button
                  onClick={() => triggerToggleEmergencyStop(true)}
                  disabled={patchMutation.isPending}
                  className="px-5 py-2.5 bg-rose-600 hover:bg-rose-500 text-white font-black rounded-lg shadow-lg shadow-rose-950/40 transition flex items-center gap-2"
                >
                  <ShieldAlert className="w-4 h-4 animate-bounce" /> TRIGGER KILLSWITCH
                </button>
              )}

              <button
                onClick={() => triggerToggleExecution(!settings?.execution_enabled)}
                disabled={patchMutation.isPending || !!settings?.emergency_stop}
                className={`px-4 py-2.5 rounded-lg border font-bold shadow transition flex items-center gap-2 ${
                  settings?.execution_enabled
                    ? "bg-slate-900 hover:bg-slate-800 text-rose-400 border-slate-800"
                    : "bg-emerald-600 hover:bg-emerald-500 text-white border-transparent"
                }`}
              >
                <Radio className="w-4 h-4" />
                <span>{settings?.execution_enabled ? "Deactivate Run" : "Activate Run"}</span>
              </button>
            </div>
          )}
        </div>
      </div>

      {/* CORE DIAGNOSTICS GRID */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Card 1: System Telemetry & Connection Status */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 space-y-4">
          <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
            <Server className="w-4 h-4 text-sky-400" />
            <h3 className="font-bold text-slate-100 uppercase tracking-wider">
              System Telemetry & Connection
            </h3>
          </div>

          <div className="space-y-3">
            {/* Backend API status */}
            <div className="flex items-center justify-between p-2.5 bg-slate-950 rounded-lg border border-slate-800">
              <span className="text-slate-400 font-bold">FastAPI Server Health</span>
              <div className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full ${isErrorHealth ? "bg-rose-500 animate-pulse" : "bg-emerald-500"}`} />
                <span className={`font-bold ${isErrorHealth ? "text-rose-400" : "text-slate-200"}`}>
                  {isLoadingHealth ? "SYNCING..." : isErrorHealth ? "OFFLINE" : "HEALTHY"}
                </span>
              </div>
            </div>

            {/* Database status */}
            <div className="flex items-center justify-between p-2.5 bg-slate-950 rounded-lg border border-slate-800">
              <span className="text-slate-400 font-bold">PostgreSQL Pool Status</span>
              <div className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full ${isErrorHealth ? "bg-rose-500 animate-pulse" : health?.database?.status === "ok" ? "bg-emerald-500" : "bg-amber-500"}`} />
                <span className={`font-bold ${isErrorHealth ? "text-rose-400" : "text-slate-200"}`}>
                  {isLoadingHealth ? "SYNCING..." : isErrorHealth ? "UNREACHABLE" : health?.database?.status?.toUpperCase() || "UNKNOWN"}
                </span>
              </div>
            </div>

            {/* API Environment mode */}
            <div className="flex items-center justify-between p-2.5 bg-slate-950 rounded-lg border border-slate-800">
              <span className="text-slate-400 font-bold">Runtime Environment</span>
              <span className="font-bold text-sky-400 uppercase">
                {isLoadingHealth ? "..." : health?.environment?.status || "development"}
              </span>
            </div>

            {/* Data freshness */}
            <div className="flex items-center justify-between p-2.5 bg-slate-950 rounded-lg border border-slate-800">
              <span className="text-slate-400 font-bold">Telemetry Data Freshness</span>
              <div className="flex items-center gap-1.5 font-bold text-slate-200">
                <Clock className="w-3.5 h-3.5 text-slate-400" />
                <span>
                  {isLoadingBtcRegime ? "..." : btcRegime?.evaluated_at ? (
                    `${Math.max(0, Math.floor((Date.now() - new Date(btcRegime.evaluated_at).getTime()) / 1000))}s ago`
                  ) : "No data received"}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Card 2: Strategy Scanner Status */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 space-y-4">
          <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
            <Activity className="w-4 h-4 text-emerald-400" />
            <h3 className="font-bold text-slate-100 uppercase tracking-wider">
              Strategy Scanner Status
            </h3>
          </div>

          <div className="space-y-3">
            {/* Collection switch */}
            <div className="flex items-center justify-between p-2.5 bg-slate-950 rounded-lg border border-slate-800">
              <span className="text-slate-400 font-bold">Market Collection Enabled</span>
              <span className={`px-2 py-0.5 rounded font-bold text-[10px] ${
                marketDataStatus?.collection_enabled
                  ? "bg-emerald-950 border border-emerald-800 text-emerald-400"
                  : "bg-rose-950 border border-rose-800 text-rose-400"
              }`}>
                {isLoadingMarketStatus ? "..." : marketDataStatus?.collection_enabled ? "ENABLED" : "DISABLED"}
              </span>
            </div>

            {/* Scanner runner state */}
            <div className="flex items-center justify-between p-2.5 bg-slate-950 rounded-lg border border-slate-800">
              <span className="text-slate-400 font-bold">Scanner Runner Active</span>
              <span className={`px-2 py-0.5 rounded font-bold text-[10px] ${
                marketDataStatus?.runner_active
                  ? "bg-emerald-950 border border-emerald-800 text-emerald-400"
                  : "bg-rose-950 border border-rose-800 text-rose-400"
              }`}>
                {isLoadingMarketStatus ? "..." : marketDataStatus?.runner_active ? "ACTIVE" : "INACTIVE"}
              </span>
            </div>

            {/* Scanner interval */}
            <div className="flex items-center justify-between p-2.5 bg-slate-950 rounded-lg border border-slate-800">
              <span className="text-slate-400 font-bold">Scanner Cycle Interval</span>
              <span className="font-bold text-slate-200">
                {isLoadingSettings ? "..." : `${settings?.scanner_interval_seconds || 10} seconds`}
              </span>
            </div>

            {/* Latest cycle */}
            <div className="flex items-center justify-between p-2.5 bg-slate-950 rounded-lg border border-slate-800">
              <span className="text-slate-400 font-bold">Latest Scan Cycle</span>
              <span className="font-bold text-slate-200 uppercase">
                {isLoadingMarketStatus ? "..." : marketDataStatus?.latest_cycle_status || "completed"}
              </span>
            </div>
          </div>
        </div>

        {/* Card 3: Core Risk & Exposure Limits */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 space-y-4">
          <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
            <Sliders className="w-4 h-4 text-amber-400" />
            <h3 className="font-bold text-slate-100 uppercase tracking-wider">
              Core Risk Boundaries
            </h3>
          </div>

          <div className="space-y-3">
            {/* Risk per trade */}
            <div className="flex items-center justify-between p-2.5 bg-slate-950 rounded-lg border border-slate-800">
              <span className="text-slate-400 font-bold">Allocated Risk Per Trade</span>
              <span className="font-bold text-amber-400">
                {isLoadingSettings ? "..." : `${((settings?.risk_per_trade || 0) * 100).toFixed(2)}%`}
              </span>
            </div>

            {/* Daily loss limit */}
            <div className="flex items-center justify-between p-2.5 bg-slate-950 rounded-lg border border-slate-800">
              <span className="text-slate-400 font-bold">Daily Max Drawdown Limit</span>
              <span className="font-bold text-rose-400">
                {isLoadingSettings ? "..." : `${((settings?.daily_loss_limit || 0) * 100).toFixed(1)}%`}
              </span>
            </div>

            {/* Max open trades */}
            <div className="flex items-center justify-between p-2.5 bg-slate-950 rounded-lg border border-slate-800">
              <span className="text-slate-400 font-bold">Maximum Open Positions</span>
              <span className="font-bold text-slate-200">
                {isLoadingSettings ? "..." : `${settings?.maximum_open_trades || 0} Trades`}
              </span>
            </div>

            {/* Demo trading mode */}
            <div className="flex items-center justify-between p-2.5 bg-slate-950 rounded-lg border border-slate-800">
              <span className="text-slate-400 font-bold">Simulated Execution Environment</span>
              <span className={`px-2 py-0.5 rounded font-bold text-[10px] ${
                settings?.demo_trading_mode
                  ? "bg-sky-950 border border-sky-800 text-sky-400"
                  : "bg-rose-950 border border-rose-800 text-rose-400"
              }`}>
                {isLoadingSettings ? "..." : settings?.demo_trading_mode ? "DEMO MODE (VIRTUAL)" : "LIVE DISPATCH (WARNING)"}
              </span>
            </div>
          </div>
        </div>

        {/* Card 4: Market Blocks & Core Guardrails */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 space-y-4">
          <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
            <ShieldAlert className="w-4 h-4 text-rose-400" />
            <h3 className="font-bold text-slate-100 uppercase tracking-wider">
              Market Blocks & Guardrails
            </h3>
          </div>

          <div className="space-y-3">
            {/* Emergency Stop state */}
            <div className="flex items-center justify-between p-2.5 bg-slate-950 rounded-lg border border-slate-800">
              <span className="text-slate-400 font-bold">Emergency Stop Killswitch</span>
              <span className={`px-2 py-0.5 rounded font-bold text-[10px] ${
                settings?.emergency_stop
                  ? "bg-rose-950 border border-rose-800 text-rose-400 animate-pulse"
                  : "bg-emerald-950 border border-emerald-800 text-emerald-400"
              }`}>
                {isLoadingSettings ? "..." : settings?.emergency_stop ? "ACTIVE" : "INACTIVE"}
              </span>
            </div>

            {/* Market Wide Block state */}
            <div className="flex items-center justify-between p-2.5 bg-slate-950 rounded-lg border border-slate-800">
              <span className="text-slate-400 font-bold">Market-Wide Block (Volatility Check)</span>
              <span className={`px-2 py-0.5 rounded font-bold text-[10px] ${
                btcRegime?.market_wide_block || settings?.emergency_stop
                  ? "bg-rose-950 border border-rose-800 text-rose-400"
                  : "bg-emerald-950 border border-emerald-800 text-emerald-400"
              }`}>
                {isLoadingBtcRegime || isLoadingSettings ? "..." : (btcRegime?.market_wide_block || settings?.emergency_stop) ? "BLOCKED" : "CLEAR"}
              </span>
            </div>

            {/* Execution status */}
            <div className="flex items-center justify-between p-2.5 bg-slate-950 rounded-lg border border-slate-800">
              <span className="text-slate-400 font-bold">Execution Engine Status</span>
              <span className={`px-2 py-0.5 rounded font-bold text-[10px] ${
                settings?.execution_enabled
                  ? "bg-emerald-950 border border-emerald-800 text-emerald-400"
                  : "bg-slate-900 border border-slate-700 text-slate-400"
              }`}>
                {isLoadingSettings ? "..." : settings?.execution_enabled ? "RUNNING" : "STANDBY"}
              </span>
            </div>

            {/* Server IP Origins */}
            <div className="flex items-center justify-between p-2.5 bg-slate-950 rounded-lg border border-slate-800">
              <span className="text-slate-400 font-bold">Allowed API Origins</span>
              <span className="font-bold text-slate-300 truncate max-w-[150px]" title={settings?.allowed_origins?.join(", ")}>
                {isLoadingSettings ? "..." : settings?.allowed_origins?.join(", ") || "None"}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* CONFIRMATION DIALOG */}
      {confirmModal.isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in">
          <div className="bg-slate-900 border border-slate-700/80 rounded-xl max-w-lg w-full shadow-2xl p-6 text-slate-100 relative animate-in zoom-in-95">
            <h3 className="text-base font-black text-slate-100 flex items-center gap-2 border-b border-slate-800 pb-3">
              <ShieldAlert className="w-5 h-5 text-amber-500 animate-pulse" />
              {confirmModal.title}
            </h3>

            <div className="mt-4 space-y-4">
              <p className="text-xs text-slate-300 leading-relaxed">
                {confirmModal.description}
              </p>

              {/* Proposed Settings Schema Diff display */}
              <div className="bg-slate-950 rounded-lg border border-slate-800 p-3.5 space-y-2">
                <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">
                  Target Parameter Delta:
                </div>
                <div className="grid grid-cols-3 items-center gap-2 py-1 border-b border-slate-900">
                  <span className="text-slate-400 font-bold">Field Affected:</span>
                  <span className="col-span-2 text-sky-400 font-bold font-mono">
                    {confirmModal.targetField}
                  </span>
                </div>
                <div className="grid grid-cols-3 items-center gap-2 py-1 border-b border-slate-900">
                  <span className="text-slate-400 font-bold">Current State:</span>
                  <span className="col-span-2 text-slate-400 font-bold">
                    {confirmModal.currentValue ? "ENABLED / ACTIVE" : "DISABLED / INACTIVE"}
                  </span>
                </div>
                <div className="grid grid-cols-3 items-center gap-2 py-1">
                  <span className="text-slate-300 font-bold">Proposed State:</span>
                  <span className={`col-span-2 font-black uppercase ${
                    confirmModal.newValue ? "text-rose-400" : "text-emerald-400"
                  }`}>
                    {confirmModal.newValue ? "ENABLED / ACTIVE" : "DISABLED / INACTIVE"}
                  </span>
                </div>
              </div>

              {/* Warning warning warning */}
              <div className="flex items-start gap-2.5 bg-rose-950/40 border border-rose-900/60 p-3 rounded-lg text-rose-300">
                <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                <div className="leading-relaxed">
                  <strong className="font-bold text-rose-200">Guardrail warning:</strong> {confirmModal.warning}
                </div>
              </div>
            </div>

            <div className="mt-6 flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
              <button
                type="button"
                onClick={() => setConfirmModal((prev) => ({ ...prev, isOpen: false }))}
                disabled={patchMutation.isPending}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-semibold transition"
              >
                Cancel Action
              </button>
              <button
                type="button"
                onClick={confirmAndSubmitPatch}
                disabled={patchMutation.isPending}
                className="px-5 py-2 bg-rose-600 hover:bg-rose-500 text-white rounded-lg text-xs font-black shadow-lg shadow-rose-950/40 transition flex items-center gap-2"
              >
                {patchMutation.isPending ? (
                  <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                ) : (
                  <CheckCircle2 className="w-4 h-4" />
                )}
                <span>Acknowledge & Save</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
