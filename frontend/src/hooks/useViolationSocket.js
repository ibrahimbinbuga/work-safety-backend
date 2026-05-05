import { useEffect, useRef, useState, useCallback } from 'react';

const WS_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000')
  .replace('https://', 'wss://')
  .replace('http://', 'ws://');

const RECONNECT_DELAY = 5000;

export function useViolationSocket(token, companyCode) {
  const [notifications, setNotifications] = useState([]);
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);
  const mountedRef = useRef(true);

  const dismiss = useCallback((id) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  }, []);

  const connect = useCallback(() => {
    if (!token || !companyCode) return;
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const url = `${WS_BASE}/api/company/${companyCode}/ws/violations`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('[WS] Connected — sending auth token');
      ws.send(token);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.event !== 'violation') return;

        const id = Date.now() + Math.random();
        const notification = { id, ...data, receivedAt: new Date() };

        setNotifications((prev) => [notification, ...prev].slice(0, 5));

        // Auto-dismiss after 6 seconds
        setTimeout(() => {
          if (mountedRef.current) dismiss(id);
        }, 6000);
      } catch (e) {
        console.error('[WS] Parse error:', e);
      }
    };

    ws.onclose = () => {
      console.log('[WS] Disconnected — reconnecting in 5s');
      if (mountedRef.current) {
        reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY);
      }
    };

    ws.onerror = (err) => {
      console.error('[WS] Error:', err);
      ws.close();
    };
  }, [token, companyCode, dismiss]);

  useEffect(() => {
    mountedRef.current = true;
    connect();

    return () => {
      mountedRef.current = false;
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { notifications, dismiss };
}
