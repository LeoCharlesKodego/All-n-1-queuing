import { useEffect, useRef, useState } from "react";

export function useLive(onEvent) {
  const handler = useRef(onEvent);
  const [connected, setConnected] = useState(false);
  const socketRef = useRef(null);
  const retryRef = useRef(null);

  useEffect(() => {
    handler.current = onEvent;
  }, [onEvent]);

  useEffect(() => {
    let closed = false;
    let heartbeat = null;

    const connect = () => {
      if (closed) return;
      const proto = window.location.protocol === "https:" ? "wss" : "ws";
      const socket = new WebSocket(`${proto}://${window.location.host}/ws`);
      socketRef.current = socket;

      socket.onopen = () => {
        setConnected(true);
        if (heartbeat) clearInterval(heartbeat);
        heartbeat = setInterval(() => {
          try {
            socket.send("ping");
          } catch {
            /* ignore */
          }
        }, 25000);
      };
      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type !== "hello") handler.current?.(data);
        } catch {
          /* ignore malformed */
        }
      };
      socket.onclose = () => {
        setConnected(false);
        if (heartbeat) clearInterval(heartbeat);
        if (!closed) retryRef.current = setTimeout(connect, 2000);
      };
      socket.onerror = () => {
        socket.close();
      };
    };

    connect();
    return () => {
      closed = true;
      if (heartbeat) clearInterval(heartbeat);
      if (retryRef.current) clearTimeout(retryRef.current);
      socketRef.current?.close();
    };
  }, []);

  return connected;
}
