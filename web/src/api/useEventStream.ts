import { useEffect, useRef } from 'react';

const API_BASE = (import.meta as any).env?.VITE_API_BASE?.toString().trim() || '';

export interface SSEEvent {
  type: string;
  prev: number;
  current: number;
  count: number;
}

/**
 * React hook that opens an SSE connection to `/api/v1/events/stream`
 * and calls `onEvent` whenever the server reports new rows in the DB.
 *
 * The EventSource auto-reconnects on disconnect (browser built-in).
 */
export function useEventStream(onEvent: (evt: SSEEvent) => void) {
  const cbRef = useRef(onEvent);
  cbRef.current = onEvent;

  useEffect(() => {
    const url = `${API_BASE}/api/v1/events/stream`;
    const es = new EventSource(url, { withCredentials: false });

    const handler = (e: MessageEvent) => {
      try {
        const data: SSEEvent = JSON.parse(e.data);
        cbRef.current(data);
      } catch {
        // ignore unparseable events
      }
    };

    // Listen to all named event types we emit
    for (const name of ['news:new', 'insights:new', 'feedback:new', 'sent:new']) {
      es.addEventListener(name, handler);
    }

    return () => {
      es.close();
    };
  }, []);
}
