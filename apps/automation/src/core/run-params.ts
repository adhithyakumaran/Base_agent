/** Validated QA_PARAM_* values injected by the orchestrator for parameterized runs. */

const PARAM_PATTERNS: Record<string, RegExp> = {
  SKU: /^[A-Za-z0-9-]{3,32}$/,
};

function validateParam(name: string, value: string): string {
  const trimmed = value.trim();
  if (!trimmed) {
    throw new Error(`QA_PARAM_${name.toUpperCase()} is empty`);
  }
  if (/[\r\n\0;|&$`<>]/.test(trimmed)) {
    throw new Error(`QA_PARAM_${name.toUpperCase()} contains unsafe characters`);
  }
  const pattern = PARAM_PATTERNS[name.toUpperCase()];
  if (pattern && !pattern.test(trimmed)) {
    throw new Error(`QA_PARAM_${name.toUpperCase()} failed validation: ${trimmed}`);
  }
  return trimmed;
}

export function getRunParam(name: string): string | undefined {
  const envKey = `QA_PARAM_${name.toUpperCase()}`;
  const raw = process.env[envKey];
  if (raw == null || raw === '') return undefined;
  return validateParam(name, raw);
}

export function getSkuParam(): string | undefined {
  return getRunParam('SKU');
}

export function requireSkuParam(): string {
  const sku = getSkuParam();
  if (!sku) {
    throw new Error('QA_PARAM_SKU is required for this parameterized run');
  }
  return sku;
}
