import { execFile } from "node:child_process";
import { mkdtemp, readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { promisify } from "node:util";
import { expect, test } from "vitest";
const root = path.resolve(import.meta.dirname, "../../..");
// A shared CI runner takes far longer over every gallery state than a laptop does; the CI gallery stage runs this.
const slowdown = process.env.CI ? 4 : 1;

test.skipIf(process.env.JANA_WHOLE_GALLERY_TESTS === "elsewhere")("uxs45_capture_states_gallery: all capture fixtures in two themes and widths", async () => {
  const out = await mkdtemp(path.join(tmpdir(), "jana-capture-gallery-")), run = promisify(execFile);
  await run(process.execPath, ["node_modules/vite/bin/vite.js", "build", "--config", "benchmark.config.ts"], { cwd: path.join(root, "apps/desktop"), timeout: 60000 });
  let failure: unknown;
  try { await run(process.execPath, ["scripts/ci/browser-capture-gallery.mjs", out], { cwd: root, timeout: 240000 * slowdown }); } catch (error) { failure = error; }
  const result = JSON.parse(await readFile(path.join(out, "result.json"), "utf8"));
  expect(result.errors, `Evidence: ${out}`).toEqual([]); expect(result.results).toHaveLength(result.expected);
  expect(result.results.every((r: { violations: number }) => r.violations === 0)).toBe(true);
  expect(failure).toBeUndefined();
}, 305000 * slowdown);
