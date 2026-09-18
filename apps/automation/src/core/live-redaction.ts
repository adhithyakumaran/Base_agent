const SENSITIVE_KEY = /password|passwd|token|secret|credential|authorization|api[_-]?key|bearer/i;

export function isSensitiveTarget(target: string): boolean {
  return SENSITIVE_KEY.test(target);
}

export function summarizeFillValue(target: string, value: unknown): string {
  const text = value === undefined || value === null ? '' : String(value);
  if (isSensitiveTarget(target) || SENSITIVE_KEY.test(text)) {
    return '[redacted]';
  }
  return text;
}
