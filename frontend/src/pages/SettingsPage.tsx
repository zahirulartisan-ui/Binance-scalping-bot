import React, { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient, getExecutionApiToken, setExecutionApiToken } from "../api/client";
import { LogLevel, RuntimeSettingsPatch, RuntimeSettings } from "../api/types";
import { useToast } from "../context/ToastContext";
import { useTabVisibility } from "../hooks/useTabVisibility";
import {
  Settings,
  ShieldAlert,
  Zap,
  Save,
  AlertTriangle,
  RotateCcw,
  Sliders,
  Server,
  Globe,
  Radio,
  Plus,
  X,
  SlidersHorizontal,
  Folder,
  ShieldCheck,
  CheckCircle2,
  RefreshCw,
} from "lucide-react";

export const SettingsPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const isTabVisible = useTabVisibility();

  // State to track if backend connection is offline/mock
  const [isOfflineMode, setIsOfflineMode] = useState(false);

  // Fetch current settings (polling 15s, paused if tab is hidden)
  const { data: serverSettings, isLoading, isError, error, refetch, isStale } = useQuery({
    queryKey: ["settings"],
    queryFn: async () => {
      try {
        const base = (import.meta as any).env?.VITE_API_BASE_URL || "http://localhost:8000";
        const testRes = await fetch(`${base.replace(/\/+$/, "")}/health`, { method: "GET" }).catch(() => null);
        setIsOfflineMode(!testRes || !testRes.ok);
      } catch {
        setIsOfflineMode(true);
      }
      return apiClient.getSettings();
    },
    refetchInterval: isTabVisible ? 15000 : false,
  });

  // Local form state
  const [logLevel, setLogLevel] = useState<LogLevel>("INFO");
  const [allowedOrigins, setAllowedOrigins] = useState<string[]>([]);
  const [newOriginInput, setNewOriginInput] = useState<string>("");
  const [executionEnabled, setExecutionEnabled] = useState<boolean>(false);
  const [demoTradingMode, setDemoTradingMode] = useState<boolean>(true);
  const [scannerIntervalSeconds, setScannerIntervalSeconds] = useState<number>(10);
  const [riskPerTrade, setRiskPerTrade] = useState<number>(0.01);
  const [maximumOpenTrades, setMaximumOpenTrades] = useState<number>(5);
  const [dailyLossLimit, setDailyLossLimit] = useState<number>(0.05);
  const [emergencyStop, setEmergencyStop] = useState<boolean>(false);
  const [executionApiTokenInput, setExecutionApiTokenInput] = useState<string>(() =>
    getExecutionApiToken()
  );

  // Form input validation state (for fields with min/max, tracking error messages)
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});
  const [backendErrorMsg, setBackendErrorMsg] = useState<string | null>(null);

  // Populated state from server settings
  useEffect(() => {
    if (serverSettings) {
      setLogLevel(serverSettings.log_level);
      setAllowedOrigins(serverSettings.allowed_origins || []);
      setExecutionEnabled(serverSettings.execution_enabled);
      setDemoTradingMode(serverSettings.demo_trading_mode);
      setScannerIntervalSeconds(serverSettings.scanner_interval_seconds);
      setRiskPerTrade(serverSettings.risk_per_trade);
      setMaximumOpenTrades(serverSettings.maximum_open_trades);
      setDailyLossLimit(serverSettings.daily_loss_limit);
      setEmergencyStop(serverSettings.emergency_stop);
    }
  }, [serverSettings]);

  // Track changed/touched fields compared to server settings
  const getChangedFields = (): RuntimeSettingsPatch => {
    if (!serverSettings) return {};
    const patch: RuntimeSettingsPatch = {};

    if (logLevel !== serverSettings.log_level) patch.log_level = logLevel;
    if (JSON.stringify(allowedOrigins) !== JSON.stringify(serverSettings.allowed_origins)) {
      patch.allowed_origins = allowedOrigins;
    }
    if (executionEnabled !== serverSettings.execution_enabled) patch.execution_enabled = executionEnabled;
    if (demoTradingMode !== serverSettings.demo_trading_mode) patch.demo_trading_mode = demoTradingMode;
    if (scannerIntervalSeconds !== serverSettings.scanner_interval_seconds) {
      patch.scanner_interval_seconds = scannerIntervalSeconds;
    }
    if (riskPerTrade !== serverSettings.risk_per_trade) patch.risk_per_trade = riskPerTrade;
    if (maximumOpenTrades !== serverSettings.maximum_open_trades) patch.maximum_open_trades = maximumOpenTrades;
    if (dailyLossLimit !== serverSettings.daily_loss_limit) patch.daily_loss_limit = dailyLossLimit;
    if (emergencyStop !== serverSettings.emergency_stop) patch.emergency_stop = emergencyStop;

    return patch;
  };

  const changedFields = getChangedFields();
  const hasUnsavedChanges = Object.keys(changedFields).length > 0;

  // Mutation for patching settings
  const patchMutation = useMutation({
    mutationFn: (patch: RuntimeSettingsPatch) => apiClient.patchSettings(patch),
    onSuccess: (updated) => {
      queryClient.setQueryData(["settings"], updated);
      queryClient.invalidateQueries({ queryKey: ["health"] });
      setBackendErrorMsg(null);
      setConfirmModal((prev) => ({ ...prev, isOpen: false }));
      showToast({
        type: "success",
        title: "Settings Saved",
        message: "Settings have been successfully patched on the server.",
      });
    },
    onError: (err: any) => {
      setBackendErrorMsg(err?.message || "Failed to update settings patch.");
      showToast({
        type: "error",
        title: "Settings Save Failed",
        message: err?.message || "Check fields and submit again.",
      });
    },
  });

  // Safety confirmation dialog state
  const [confirmModal, setConfirmModal] = useState<{
    isOpen: boolean;
    title: string;
    description: string;
    patch: RuntimeSettingsPatch;
    warnings: string[];
  }>({
    isOpen: false,
    title: "",
    description: "",
    patch: {},
    warnings: [],
  });

  const handleAddOrigin = () => {
    const trimmed = newOriginInput.trim();
    if (!trimmed) return;

    // Simple URL/Origin validation regex
    if (!/^https?:\/\/[a-zA-Z0-9][-a-zA-Z0-9._]*[a-zA-Z0-9](:\d+)?$/.test(trimmed) && trimmed !== "*") {
      setValidationErrors((prev) => ({
        ...prev,
        allowed_origins: "Origin must be a valid schema e.g. http://localhost:3000 or *",
      }));
      return;
    }

    if (!allowedOrigins.includes(trimmed)) {
      setAllowedOrigins([...allowedOrigins, trimmed]);
      setNewOriginInput("");
      setValidationErrors((prev) => {
        const copy = { ...prev };
        delete copy.allowed_origins;
        return copy;
      });
    }
  };

  const handleRemoveOrigin = (index: number) => {
    setAllowedOrigins(allowedOrigins.filter((_, i) => i !== index));
  };

  // Reset local state back to last-known server state
  const handleResetForm = () => {
    if (serverSettings) {
      setLogLevel(serverSettings.log_level);
      setAllowedOrigins(serverSettings.allowed_origins || []);
      setNewOriginInput("");
      setExecutionEnabled(serverSettings.execution_enabled);
      setDemoTradingMode(serverSettings.demo_trading_mode);
      setScannerIntervalSeconds(serverSettings.scanner_interval_seconds);
      setRiskPerTrade(serverSettings.risk_per_trade);
      setMaximumOpenTrades(serverSettings.maximum_open_trades);
      setDailyLossLimit(serverSettings.daily_loss_limit);
      setEmergencyStop(serverSettings.emergency_stop);
      setValidationErrors({});
      setBackendErrorMsg(null);
      showToast({
        type: "info",
        title: "Form Reset",
        message: "Inputs reverted back to last persistent server values.",
      });
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setBackendErrorMsg(null);

    // Clientside Form validations
    const errors: Record<string, string> = {};

    if (allowedOrigins.length === 0) {
      errors.allowed_origins = "At least one allowed CORS origin is required.";
    }
    if (scannerIntervalSeconds < 5 || scannerIntervalSeconds > 3600) {
      errors.scanner_interval_seconds = "Interval must be between 5 and 3600 seconds.";
    }
    if (maximumOpenTrades < 0 || maximumOpenTrades > 50) {
      errors.maximum_open_trades = "Max open trades must be between 0 and 50.";
    }
    if (riskPerTrade < 0.001 || riskPerTrade > 0.05) {
      errors.risk_per_trade = "Risk per trade must be between 0.1% and 5.0%.";
    }
    if (dailyLossLimit < 0.01 || dailyLossLimit > 0.5) {
      errors.daily_loss_limit = "Daily loss limit must be between 1.0% and 50.0%.";
    }

    if (Object.keys(errors).length > 0) {
      setValidationErrors(errors);
      showToast({
        type: "error",
        title: "Form Validation Error",
        message: "Please correct the highlighted inputs before saving.",
      });
      return;
    }

    setValidationErrors({});

    const patch = getChangedFields();
    if (Object.keys(patch).length === 0) {
      showToast({
        type: "info",
        title: "No Changes",
        message: "No fields have been modified.",
      });
      return;
    }

    // Safety checks / Enforcements:
    const warnings: string[] = [];

    // Rule 1: Do not allow execution while emergency stop is active
    const isExecutionTurningOn = patch.execution_enabled === true;
    const isEmergencyStopActive = patch.emergency_stop !== undefined ? patch.emergency_stop : emergencyStop;

    if (isExecutionTurningOn && isEmergencyStopActive) {
      showToast({
        type: "error",
        title: "Safety Blocked",
        message: "Execution cannot be enabled while Emergency Stop is active.",
      });
      return;
    }

    // Rule 2: Do not allow execution unless Demo Trading mode is confirmed (either currently true, or being set to true)
    const isDemoModeOn = patch.demo_trading_mode !== undefined ? patch.demo_trading_mode : demoTradingMode;
    const finalExecutionEnabled = patch.execution_enabled !== undefined ? patch.execution_enabled : executionEnabled;

    if (finalExecutionEnabled && !isDemoModeOn) {
      warnings.push("CRITICAL: Execution is locked to Binance Spot Demo. Keep Demo Trading Mode enabled.");
    }

    // Require confirmation before changing execution or emergency stop
    const isSafetyTriggered =
      patch.execution_enabled !== undefined ||
      patch.emergency_stop !== undefined ||
      patch.demo_trading_mode !== undefined;

    if (isSafetyTriggered) {
      let title = "Confirm Safety Parameter Update";
      let description = "You are changing execution-safety parameters. Please verify current vs proposed settings below.";

      if (patch.emergency_stop === true) {
        title = "ACTIVATING EMERGENCY KILLSWITCH";
        description = "This will immediately halt all strategy scanners and force execution mode OFF across the entire bot engine.";
        warnings.push("CRITICAL: Dispatches are frozen immediately. Orders in transit will not receive updates.");
      } else if (patch.execution_enabled === true) {
        title = "ENABLE AUTO TRADING EXECUTION";
        description = "The strategy engine will begin automatically placing order signals on identified setups.";
      }

      setConfirmModal({
        isOpen: true,
        title,
        description,
        patch,
        warnings,
      });
    } else {
      // Just normal non-critical settings update (PATCH only changed fields)
      patchMutation.mutate(patch);
    }
  };

  const handleToggleEmergencyStopLocal = (checked: boolean) => {
    setEmergencyStop(checked);
    if (checked) {
      // Optimistic safety enforcement: turning emergency stop ON forces execution OFF
      setExecutionEnabled(false);
    }
  };

  return (
    <div className="p-6 space-y-6 max-w-5xl mx-auto font-mono text-xs">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-2xl font-black text-slate-100 tracking-tight flex items-center gap-2">
            <Settings className="w-6 h-6 text-amber-400 inline" /> TERMINAL SETTINGS
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Maintain CORS configurations, logging levels, safety limits, and trade exposure thresholds.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* MOCK DATA OR PREVIEW MODE BADGE */}
          {isOfflineMode && (
            <span className="px-3 py-1 bg-amber-950/80 text-amber-400 border border-amber-500/40 rounded-lg font-bold text-[10px] uppercase">
              PREVIEW FALLBACK ACTIVE
            </span>
          )}

          <button
            type="button"
            onClick={() => refetch()}
            disabled={isLoading}
            className="p-2 bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 rounded-lg flex items-center gap-1 transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Backend Error alerts */}
      {backendErrorMsg && (
        <div className="bg-rose-950/40 border border-rose-500/30 rounded-xl p-4 flex items-start gap-3 text-rose-300">
          <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <h4 className="font-bold text-rose-200 uppercase text-[11px]">Backend Validation Error</h4>
            <p className="text-xs">{backendErrorMsg}</p>
          </div>
        </div>
      )}

      {/* Unsaved Changes Banner */}
      {hasUnsavedChanges && (
        <div className="bg-amber-950/30 border border-amber-500/30 rounded-xl p-4 flex items-center justify-between gap-4 animate-pulse">
          <div className="flex items-center gap-3 text-amber-300">
            <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0" />
            <div>
              <span className="font-black text-amber-200">UNSAVED PARAMETERS DETECTED</span>
              <p className="text-[10px] text-slate-400 mt-0.5">
                Modified parameters: {Object.keys(changedFields).join(", ")}. Click 'Apply Changes' to sync.
              </p>
            </div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleResetForm}
              className="px-3 py-1.5 bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 rounded-lg font-bold transition"
            >
              Reset
            </button>
          </div>
        </div>
      )}

      {isLoading ? (
        <div className="p-12 text-center text-slate-400 font-bold flex flex-col items-center gap-3">
          <span className="w-8 h-8 border-4 border-slate-800 border-t-amber-500 rounded-full animate-spin" />
          <span>Synchronizing settings schema from server...</span>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* GROUP 1: EXECUTION SAFETY (CRITICAL SAFETY SWITCHES) */}
          <section className={`bg-slate-900/90 border rounded-xl p-5 shadow-2xl space-y-4 relative overflow-hidden transition-colors ${
            emergencyStop ? "border-rose-500/60" : "border-slate-800"
          }`}>
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h2 className="text-sm font-black text-rose-400 flex items-center gap-2 uppercase tracking-wider">
                <ShieldAlert className="w-5 h-5 text-rose-400" /> 1. Execution Safety & Emergency Stop
              </h2>
              {emergencyStop && (
                <span className="text-[10px] text-rose-400 bg-rose-950 px-2.5 py-0.5 rounded border border-rose-800 font-bold animate-pulse">
                  EMERGENCY ACTIVE
                </span>
              )}
            </div>

            {emergencyStop && (
              <div className="bg-rose-950/50 border border-rose-500/30 p-3.5 rounded-lg text-rose-300 mb-2 leading-relaxed">
                <strong className="text-rose-200 font-bold block mb-1">WARNING: Emergency Stop Active</strong>
                Trading execution is completely locked. Dispatches will fail. Toggle this setting to OFF, and then apply changes, to restore normal configuration standby.
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Emergency Stop Toggle */}
              <div className={`p-4 rounded-xl border transition-all ${
                emergencyStop
                  ? "bg-rose-950/80 border-rose-500 text-rose-200"
                  : "bg-slate-950/80 border-slate-800 text-slate-300"
              }`}>
                <div className="flex items-center justify-between">
                  <span className="font-bold text-sm tracking-tight flex items-center gap-2">
                    <ShieldAlert className="w-4 h-4 text-rose-400" /> Emergency Stop
                  </span>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={emergencyStop}
                      onChange={(e) => handleToggleEmergencyStopLocal(e.target.checked)}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-slate-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-rose-600" />
                  </label>
                </div>
                <p className="mt-2 text-[11px] text-slate-400 leading-relaxed">
                  Triggers system circuit-breaker. Stops strategy engines and sets execution mode to false automatically.
                </p>
              </div>

              {/* Execution Enabled Toggle */}
              <div className={`p-4 rounded-xl border transition-all ${
                executionEnabled
                  ? "bg-emerald-950/70 border-emerald-500 text-emerald-200"
                  : "bg-slate-950/80 border-slate-800 text-slate-300"
              }`}>
                <div className="flex items-center justify-between">
                  <span className="font-bold text-sm tracking-tight flex items-center gap-2">
                    <Radio className="w-4 h-4 text-emerald-400" /> Execution Enabled
                  </span>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={executionEnabled}
                      disabled={emergencyStop}
                      onChange={(e) => setExecutionEnabled(e.target.checked)}
                      className="sr-only peer disabled:opacity-50"
                    />
                    <div className="w-11 h-6 bg-slate-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-emerald-600 peer-disabled:opacity-40" />
                  </label>
                </div>
                <p className="mt-2 text-[11px] text-slate-400 leading-relaxed">
                  {emergencyStop
                    ? "Blocked: Execution cannot be enabled while Emergency Stop is active."
                    : "Allows the trading engine to dispatch trades to Binance automatically."}
                </p>
              </div>
            </div>
          </section>

          {/* GROUP 2: STRATEGY */}
          <section className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-xl space-y-4">
            <h2 className="text-sm font-black text-slate-100 uppercase tracking-wider border-b border-slate-800 pb-3 flex items-center gap-2">
              <SlidersHorizontal className="w-4 h-4 text-sky-400" /> 2. Strategy Parameters
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Demo Trading Mode Toggle */}
              <div className="space-y-2 bg-slate-950 p-4 rounded-lg border border-slate-800 flex items-center justify-between">
                <div>
                  <div className="font-bold text-slate-300 text-sm">Demo Trading Mode</div>
                  <div className="text-[10px] text-slate-500 mt-1">
                    Dispatches orders to Binance Spot Demo only; real-capital live dispatch is blocked.
                  </div>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={demoTradingMode}
                    onChange={(e) => setDemoTradingMode(e.target.checked)}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-slate-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-sky-600" />
                </label>
              </div>
            </div>
          </section>

          {/* GROUP 3: RISK PARAMETERS */}
          <section className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-xl space-y-4">
            <h2 className="text-sm font-black text-slate-100 uppercase tracking-wider border-b border-slate-800 pb-3 flex items-center gap-2">
              <Sliders className="w-4 h-4 text-amber-400" /> 3. Risk & Exposure Parameters
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Risk per trade input + slider */}
              <div className="space-y-2 bg-slate-950 p-4 rounded-lg border border-slate-800">
                <div className="flex justify-between font-bold text-sm">
                  <span className="text-slate-300">Risk Per Trade:</span>
                  <span className="text-amber-400">{(riskPerTrade * 100).toFixed(1)}%</span>
                </div>
                <input
                  type="range"
                  min="0.001"
                  max="0.05"
                  step="0.001"
                  value={riskPerTrade}
                  onChange={(e) => setRiskPerTrade(parseFloat(e.target.value))}
                  className="w-full accent-amber-500 cursor-pointer"
                />
                <div className="flex justify-between text-[10px] text-slate-500">
                  <span>0.1% min</span>
                  <span>5.0% max</span>
                </div>
                {validationErrors.risk_per_trade && (
                  <p className="text-rose-400 text-[10px] font-bold mt-1">{validationErrors.risk_per_trade}</p>
                )}
              </div>

              {/* Daily Loss Limit slider */}
              <div className="space-y-2 bg-slate-950 p-4 rounded-lg border border-slate-800">
                <div className="flex justify-between font-bold text-sm">
                  <span className="text-slate-300">Daily Loss Limit:</span>
                  <span className="text-rose-400">{(dailyLossLimit * 100).toFixed(1)}%</span>
                </div>
                <input
                  type="range"
                  min="0.01"
                  max="0.5"
                  step="0.01"
                  value={dailyLossLimit}
                  onChange={(e) => setDailyLossLimit(parseFloat(e.target.value))}
                  className="w-full accent-rose-500 cursor-pointer"
                />
                <div className="flex justify-between text-[10px] text-slate-500">
                  <span>1.0% min</span>
                  <span>50.0% max</span>
                </div>
                {validationErrors.daily_loss_limit && (
                  <p className="text-rose-400 text-[10px] font-bold mt-1">{validationErrors.daily_loss_limit}</p>
                )}
              </div>

              {/* Max open trades */}
              <div className="space-y-2 bg-slate-950 p-4 rounded-lg border border-slate-800">
                <label className="block text-slate-300 font-bold text-xs">Maximum Open Trades (0 - 50):</label>
                <input
                  type="number"
                  min={0}
                  max={50}
                  value={maximumOpenTrades}
                  onChange={(e) => setMaximumOpenTrades(parseInt(e.target.value) || 0)}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-slate-100 font-bold focus:outline-none focus:border-amber-400"
                />
                {validationErrors.maximum_open_trades && (
                  <p className="text-rose-400 text-[10px] font-bold mt-1">{validationErrors.maximum_open_trades}</p>
                )}
              </div>
            </div>
          </section>

          {/* GROUP 4: MARKET DATA */}
          <section className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-xl space-y-4">
            <h2 className="text-sm font-black text-slate-100 uppercase tracking-wider border-b border-slate-800 pb-3 flex items-center gap-2">
              <Zap className="w-4 h-4 text-emerald-400" /> 4. Market Data Parameters
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Scanner Interval */}
              <div className="space-y-2 bg-slate-950 p-4 rounded-lg border border-slate-800">
                <label className="block text-slate-300 font-bold text-xs">Scanner Interval (5 - 3600 seconds):</label>
                <input
                  type="number"
                  min={5}
                  max={3600}
                  value={scannerIntervalSeconds}
                  onChange={(e) => setScannerIntervalSeconds(parseInt(e.target.value) || 5)}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-slate-100 font-bold focus:outline-none focus:border-emerald-400"
                />
                {validationErrors.scanner_interval_seconds && (
                  <p className="text-rose-400 text-[10px] font-bold mt-1">{validationErrors.scanner_interval_seconds}</p>
                )}
              </div>
            </div>
          </section>

          {/* GROUP 5: APPLICATION */}
          <section className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-xl space-y-4">
            <h2 className="text-sm font-black text-slate-100 uppercase tracking-wider border-b border-slate-800 pb-3 flex items-center gap-2">
              <Folder className="w-4 h-4 text-purple-400" /> 5. Application Parameters
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Log Level Select */}
              <div className="space-y-2 bg-slate-950 p-4 rounded-lg border border-slate-800">
                <label className="block text-slate-300 font-bold text-xs">Log Level:</label>
                <select
                  value={logLevel}
                  onChange={(e) => setLogLevel(e.target.value as LogLevel)}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-slate-100 font-bold focus:outline-none focus:border-sky-400"
                >
                  {(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] as LogLevel[]).map((lvl) => (
                    <option key={lvl} value={lvl}>
                      {lvl}
                    </option>
                  ))}
                </select>
              </div>

              {/* Server Host info (READ ONLY) */}
              <div className="space-y-2 bg-slate-950 p-4 rounded-lg border border-slate-800">
                <label className="block text-slate-500 font-bold text-xs">API Host (Static Environment Parameter):</label>
                <input
                  type="text"
                  value={serverSettings?.api_host || "0.0.0.0"}
                  disabled
                  className="w-full bg-slate-900/40 border border-slate-800 rounded-lg p-2 text-slate-500 font-semibold cursor-not-allowed"
                />
              </div>

              {/* Session-only execution token */}
              <div className="space-y-2 bg-slate-950 p-4 rounded-lg border border-slate-800 md:col-span-2">
                <label className="block text-slate-300 font-bold text-xs">
                  Execution API Token (Browser Session Only):
                </label>
                <input
                  type="password"
                  value={executionApiTokenInput}
                  placeholder="Paste EXECUTION_API_TOKEN before changing protected settings"
                  onChange={(e) => {
                    setExecutionApiTokenInput(e.target.value);
                    setExecutionApiToken(e.target.value);
                  }}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-slate-100 placeholder-slate-500 focus:outline-none focus:border-purple-400"
                />
                <p className="text-[10px] text-slate-500 leading-relaxed">
                  Required for protected PATCH requests in deployed environments. Stored only in this browser session and sent as X-Execution-Token.
                </p>
              </div>
            </div>
          </section>

          {/* GROUP 6: API CONNECTION (CORS ORIGINS) */}
          <section className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-xl space-y-4">
            <h2 className="text-sm font-black text-slate-100 uppercase tracking-wider border-b border-slate-800 pb-3 flex items-center gap-2">
              <Globe className="w-4 h-4 text-cyan-400" /> 6. API Connection (CORS Origins)
            </h2>

            <div className="space-y-2 bg-slate-950 p-4 rounded-lg border border-slate-800">
              <label className="block text-slate-300 font-bold text-xs mb-1">
                Allowed CORS Origins (min 1 URL domain, e.g. http://localhost:3000):
              </label>

              <div className="flex flex-wrap gap-2 mb-3">
                {allowedOrigins.map((orig, idx) => (
                  <span
                    key={idx}
                    className="inline-flex items-center gap-1.5 px-3 py-1 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 font-mono text-[11px]"
                  >
                    {orig}
                    <button
                      type="button"
                      onClick={() => handleRemoveOrigin(idx)}
                      className="text-slate-400 hover:text-rose-400 transition"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </span>
                ))}
              </div>

              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="https://yourdomain.com"
                  value={newOriginInput}
                  onChange={(e) => setNewOriginInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      handleAddOrigin();
                    }
                  }}
                  className="flex-1 bg-slate-900 border border-slate-700 rounded-lg p-2 text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-400"
                />
                <button
                  type="button"
                  onClick={handleAddOrigin}
                  className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg border border-slate-700 flex items-center gap-1 transition"
                >
                  <Plus className="w-4 h-4" /> Add
                </button>
              </div>
              {validationErrors.allowed_origins && (
                <p className="text-rose-400 text-[10px] font-bold mt-1">{validationErrors.allowed_origins}</p>
              )}
            </div>
          </section>

          {/* Action Footer */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
            <button
              type="button"
              onClick={handleResetForm}
              className="px-4 py-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 hover:bg-slate-800 transition flex items-center gap-2"
            >
              <RotateCcw className="w-4 h-4" /> Revert Inputs
            </button>

            <button
              type="submit"
              disabled={patchMutation.isPending || !hasUnsavedChanges}
              className="px-6 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-black shadow-lg shadow-emerald-950/60 transition flex items-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {patchMutation.isPending ? (
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <Save className="w-4 h-4" />
              )}
              <span>Apply Changes</span>
            </button>
          </div>
        </form>
      )}

      {/* RICH CONFIRMATION MODAL */}
      {confirmModal.isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in">
          <div className="bg-slate-900 border border-slate-700/80 rounded-xl max-w-lg w-full shadow-2xl p-6 text-slate-100 relative animate-in zoom-in-95">
            <h3 className="text-base font-black text-slate-100 flex items-center gap-2 border-b border-slate-800 pb-3 uppercase">
              <ShieldAlert className="w-5 h-5 text-amber-500 animate-pulse" />
              {confirmModal.title}
            </h3>

            <div className="mt-4 space-y-4">
              <p className="text-xs text-slate-300 leading-relaxed">
                {confirmModal.description}
              </p>

              {/* Settings Delta Display */}
              <div className="bg-slate-950 rounded-lg border border-slate-800 p-3.5 space-y-2">
                <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">
                  Target Parameter Delta:
                </div>
                {Object.entries(confirmModal.patch).map(([key, val]) => {
                  const originalVal = (serverSettings as any)?.[key];
                  return (
                    <div key={key} className="grid grid-cols-3 items-start gap-2 py-1.5 border-b border-slate-900/60 last:border-none">
                      <span className="text-slate-400 font-bold font-mono truncate">{key}:</span>
                      <span className="text-slate-500 text-right truncate">
                        {typeof originalVal === "boolean" ? (originalVal ? "ON" : "OFF") : String(originalVal)}
                      </span>
                      <span className="text-amber-400 font-black text-right truncate">
                        ➔ {typeof val === "boolean" ? (val ? "ON" : "OFF") : String(val)}
                      </span>
                    </div>
                  );
                })}
              </div>

              {/* Warning box */}
              {confirmModal.warnings.map((warn, i) => (
                <div key={i} className="flex items-start gap-2.5 bg-rose-950/40 border border-rose-900/60 p-3 rounded-lg text-rose-300 text-xs">
                  <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                  <div className="leading-relaxed">
                    <strong className="font-bold text-rose-200">Guardrail warning:</strong> {warn}
                  </div>
                </div>
              ))}
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
                onClick={() => patchMutation.mutate(confirmModal.patch)}
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
