import { useEffect } from "react";
import { openSupervisorSocket } from "../lib/supervisor/supervisor-ws-client";
import { useLiveCallStore } from "../store/live-calls";
import { useSupervisorAlertStore } from "../store/supervisor-alerts";

export function useSupervisorAlerts(token: string | null) {
  const addAlert = useSupervisorAlertStore((s) => s.addAlert);
  const applyEvent = useLiveCallStore((s) => s.applyEvent);

  useEffect(() => {
    if (!token) return;
    const handle = openSupervisorSocket({
      token,
      onAlert: addAlert,
      onCallEvent: applyEvent,  // Sprint 14.2
    });
    return () => handle.close();
  }, [token, addAlert, applyEvent]);
}
