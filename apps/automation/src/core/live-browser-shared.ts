import type { BrowserContext } from '@playwright/test';

let sharedContext: BrowserContext | null = null;
let sharedProfileKey: string | null = null;
let sessionAuthenticated = false;

export function liveProfileKey(): string {
  return process.env.QA_LIVE_PROFILE_DIR || 'default-live';
}

export function getSharedLiveContext(): BrowserContext | null {
  if (sharedProfileKey !== liveProfileKey()) return null;
  return sharedContext;
}

export function setSharedLiveContext(context: BrowserContext | null): void {
  sharedContext = context;
  sharedProfileKey = context ? liveProfileKey() : null;
  if (!context) sessionAuthenticated = false;
}

export function isLiveSessionAuthenticated(): boolean {
  return sessionAuthenticated;
}

export function markLiveSessionAuthenticated(): void {
  sessionAuthenticated = true;
}

export function resetLiveBrowserSharedForTests(): void {
  sharedContext = null;
  sharedProfileKey = null;
  sessionAuthenticated = false;
}
