/** Structured product-search diagnostics for LIVE_DEMO and reports. */

export function emitProductSearchTrace(marker: string, value?: string): void {
  const line = value === undefined ? `PRODUCT_SEARCH_TRACE:${marker}` : `PRODUCT_SEARCH_TRACE:${marker}=${value}`;
  const safe = line.replace(/[\r\n]/g, ' ').slice(0, 512);
  process.stderr.write(`${safe}\n`);
}
