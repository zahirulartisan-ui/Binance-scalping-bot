import React, { createContext, useContext, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../api/client";
import { MarketSymbol } from "../api/types";

interface SymbolContextValue {
  selectedSymbol: string;
  setSelectedSymbol: (symbol: string) => void;
  symbols: MarketSymbol[];
  isLoadingSymbols: boolean;
}

const SymbolContext = createContext<SymbolContextValue | undefined>(undefined);

export const SymbolProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [selectedSymbol, setSelectedSymbol] = useState<string>("BTCUSDT");

  const { data: symbols = [], isLoading: isLoadingSymbols } = useQuery({
    queryKey: ["symbols"],
    queryFn: () => apiClient.getSymbols(true, 100),
    staleTime: 60000,
  });

  return (
    <SymbolContext.Provider
      value={{
        selectedSymbol,
        setSelectedSymbol,
        symbols,
        isLoadingSymbols,
      }}
    >
      {children}
    </SymbolContext.Provider>
  );
};

export const useSymbol = (): SymbolContextValue => {
  const ctx = useContext(SymbolContext);
  if (!ctx) {
    throw new Error("useSymbol must be used within a SymbolProvider");
  }
  return ctx;
};
