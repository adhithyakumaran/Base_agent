/**
 * Shared Playwright --grep patterns for flow positive/negative runs.
 * Used by run-flow.mjs and regression tests.
 */

/** Exclude @param-test harness specs from flow positive runs. */
export const EXCLUDE_PARAM_HARNESS = '(?!.*@param-test)';

export function normalizeFlowId(rawFlowId) {
  const flowId = String(rawFlowId || '').replace(/^@/, '');
  if (!/^BF-[A-Z0-9-]+$/.test(flowId)) {
    throw new Error(`Invalid flow id: ${rawFlowId}`);
  }
  return flowId;
}

export function buildFlowGrep(polarity, rawFlowId) {
  const flowId = normalizeFlowId(rawFlowId);
  const flowTag = `@${flowId}`;
  const escapedTag = flowTag.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  if (polarity === 'positive') {
    return `(?=.*${escapedTag})(?=.*@positive)${EXCLUDE_PARAM_HARNESS}`;
  }
  if (polarity === 'negative') {
    return `(?=.*${escapedTag})(?=.*@negative)`;
  }
  throw new Error(`Unknown polarity: ${polarity}`);
}
