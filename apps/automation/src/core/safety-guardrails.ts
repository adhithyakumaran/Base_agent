/** Guardrails for sensitive flows — enforced at runtime in tests. */

export const SAFETY = {
  readonlyFlows: new Set([
    'BF-ADMINISTRATION-009',
    'BF-MANUAL-INVOICE-009',
    'BF-REPORTS-007',
  ]),
  deniedActions: [
    /create invoice/i,
    /submit payment/i,
    /delete/i,
    /change access control/i,
    /modify user/i,
  ],
} as const;

export function assertNoDestructiveAction(actionLabel: string, flowId: string): void {
  if (!SAFETY.readonlyFlows.has(flowId)) return;
  for (const pattern of SAFETY.deniedActions) {
    if (pattern.test(actionLabel)) {
      throw new Error(`Safety guardrail blocked destructive action "${actionLabel}" in ${flowId}`);
    }
  }
}

export function tag(flowId: string): string {
  return flowId.replace(/-/g, '_');
}
