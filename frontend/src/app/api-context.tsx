import { createContext, useContext, type ReactNode } from "react";
import type { ApiClient } from "../lib/api-client";

const ApiContext = createContext<ApiClient | null>(null);

type ApiProviderProps = {
  apiClient: ApiClient;
  children: ReactNode;
};

export function ApiProvider({ apiClient, children }: ApiProviderProps) {
  return <ApiContext.Provider value={apiClient}>{children}</ApiContext.Provider>;
}

export function useApiClient(): ApiClient {
  const apiClient = useContext(ApiContext);
  if (!apiClient) {
    throw new Error("ApiProvider is missing.");
  }
  return apiClient;
}
