import { existsSync } from "fs";
import path from "path";

/** Resolve monorepo root from apps/console (or legacy qa-console) cwd. */
export function repoRoot(): string {
  let dir = process.cwd();
  for (let depth = 0; depth < 6; depth++) {
    if (existsSync(path.join(dir, "repo_paths.py")) || existsSync(path.join(dir, "pyproject.toml"))) {
      return dir;
    }
    dir = path.resolve(dir, "..");
  }
  return path.resolve(process.cwd(), "../..");
}
