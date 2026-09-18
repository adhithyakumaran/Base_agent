/** Structured LIVE_DEMO fixture lifecycle markers (stderr only — no secrets). */
export type LiveFixtureStage =
  | 'before_launch'
  | 'browser_launched'
  | 'context_created'
  | 'context_attached'
  | 'login_started'
  | 'login_completed'
  | 'keeper_started'
  | 'ready_to_return'
  | 'teardown_returning';

export function emitLiveFixtureStage(stage: LiveFixtureStage, detail = ''): void {
  const suffix = detail ? ` ${detail}` : '';
  process.stderr.write(`LIVE_FIXTURE:${stage}${suffix}\n`);
}
