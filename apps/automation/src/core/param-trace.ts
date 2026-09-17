/** Safe parameter trace markers for orchestrator/evidence (no secrets beyond SKU). */

export function emitParamTrace(fields: Record<string, string | undefined>): void {
  for (const [key, value] of Object.entries(fields)) {
    if (value === undefined) continue;
    const safe = value.replace(/[\r\n]/g, ' ').slice(0, 256);
    process.stderr.write(`PARAM_TRACE:${key}=${safe}\n`);
  }
}
