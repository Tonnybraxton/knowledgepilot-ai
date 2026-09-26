"use client";
import { useCallback, useSyncExternalStore } from "react";

function subscribe(callback: () => void) {
  window.addEventListener("storage", callback);
  window.addEventListener("kp-preference", callback);
  return () => { window.removeEventListener("storage", callback); window.removeEventListener("kp-preference", callback); };
}
export function useStoredValue(key: string, fallback: string): [string, (value: string) => void] {
  const snapshot = useCallback(() => { try { return localStorage.getItem(key) ?? fallback; } catch { return fallback; } }, [key, fallback]);
  const value = useSyncExternalStore(subscribe, snapshot, () => fallback);
  return [value, next => { try { localStorage.setItem(key, next); window.dispatchEvent(new Event("kp-preference")); } catch { /* Preferences are optional when browser storage is unavailable. */ } }];
}
