"use client";

import { type ReactNode } from "react";

import { LayoutProvider, useLayoutContext } from "@/lib/LayoutContext";
import { SessionProvider, useSessionContext } from "@/lib/SessionContext";
import { InspectorProvider, useInspectorContext } from "@/lib/InspectorContext";

export function AppProvider({ children }: { children: ReactNode }) {
  return (
    <LayoutProvider>
      <SessionProvider>
        <InspectorProvider>
          {children}
        </InspectorProvider>
      </SessionProvider>
    </LayoutProvider>
  );
}

export function useAppStore() {
  const layout = useLayoutContext();
  const session = useSessionContext();
  const inspector = useInspectorContext();

  return {
    ...layout,
    ...session,
    ...inspector
  };
}
