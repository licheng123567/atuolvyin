import { useEffect } from "react";
import { openSupervisorSocket } from "../lib/supervisor/supervisor-ws-client";
import { useSupervisorAlertStore } from "../store/supervisor-alerts";

export function useSupervisorAlerts(token: string | null) {
  const addAlert = useSupervisorAlertStore((s) => s.addAlert);

  useEffect(() => {
    if (!token) return;
    const handle = openSupervisorSocket({
      token,
      onAlert: addAlert,
    });
    return () => handle.close();
  }, [token, addAlert]);
}
