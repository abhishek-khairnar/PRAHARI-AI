import { useEffect, useRef } from 'react';

/**
 * Custom hook for controlled polling with safety checks against piling requests.
 * @param {Function} callback - Async function to run on each interval tick
 * @param {number} intervalMs - Polling frequency in milliseconds
 * @param {boolean} enabled - Whether polling is currently active
 */
export function usePolling(callback, intervalMs = 1000, enabled = true) {
  const isExecutingRef = useRef(false);
  const savedCallback = useRef(callback);

  useEffect(() => {
    savedCallback.current = callback;
  }, [callback]);

  useEffect(() => {
    if (!enabled || intervalMs <= 0) return;

    const tick = async () => {
      if (isExecutingRef.current) return;
      isExecutingRef.current = true;
      try {
        await savedCallback.current();
      } catch (err) {
        console.error("Polling execution error:", err);
      } finally {
        isExecutingRef.current = false;
      }
    };

    // Execute immediately on mount/enable
    tick();

    const id = setInterval(tick, intervalMs);
    return () => clearInterval(id);
  }, [intervalMs, enabled]);
}
