// Complete gallery target matrix in Chromium; native webview and human visual review remain separate.
import { execFile } from "node:child_process";
import { mkdtemp, readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { promisify } from "node:util";
import { expect, test } from "vitest";
import { STATES } from "@jana/ui/gallery";

const root = path.resolve(import.meta.dirname, "../../..");
// A shared CI runner takes far longer over every gallery state than a laptop does; the CI gallery stage runs this.
const slowdown = process.env.CI ? 4 : 1;

test.skipIf(process.env.JANA_WHOLE_GALLERY_TESTS === "elsewhere")("dsn17_target_size", async () => {
  const output = await mkdtemp(path.join(tmpdir(), "jana-gallery-targets-"));
  const run = promisify(execFile);
  await run(process.execPath, ["node_modules/vite/bin/vite.js", "build", "--config", "benchmark.config.ts"], { cwd: path.join(root, "apps/desktop"), timeout: 60000 });
  await run(process.execPath, ["scripts/ci/browser-targets.mjs", `--out=${output}`, "--self-test"], { cwd: root, timeout: 600000 * slowdown });
  const report = JSON.parse(await readFile(path.join(output, "targets.json"), "utf8"));
  expect(report.cases).toBe(STATES.length * 8);
  expect(report.checked).toBeGreaterThan(1000);
  expect(report.failures).toBe(0); expect(report.errors).toEqual([]);
  expect(report.self_test).toBe(true);
  expect(report.physical_probes).toHaveLength(3);
  expect(report.physical_probes.every((p: { pass: boolean }) => p.pass)).toBe(true);
}, 670000 * slowdown);
