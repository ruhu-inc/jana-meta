// Live-run fix 2026-11-01: a failed `teaching_outline` job showed its raw key "study.generate.teaching_outline" as
// its label. Every job kind the contract allows has a `study.generate.*` label and every aid kind a `study.tool.*`
// one, so no row can ever show a key.
import { readFileSync } from "node:fs";
import path from "node:path";
import { expect, test } from "vitest";
import { BASE, translator } from "@jana/i18n";

const schema = JSON.parse(readFileSync(path.resolve(import.meta.dirname, "../../../contracts/study/workspace.schema.json"), "utf8")) as { $defs: Record<string, { enum?: string[] }> };

test("every JobKind has a study.generate label and every AidKind a study.tool label", () => {
  const jobKinds = schema.$defs.JobKind!.enum!, aidKinds = schema.$defs.AidKind!.enum!;
  expect(jobKinds).toContain("teaching_outline");
  const t = translator("en");
  for (const kind of jobKinds) {
    expect(BASE[`study.generate.${kind}`], `study.generate.${kind}`).toBeTruthy();
    expect(t(`study.generate.${kind}`)).not.toMatch(/^study\./);
  }
  for (const kind of aidKinds) {
    expect(BASE[`study.tool.${kind}`], `study.tool.${kind}`).toBeTruthy();
    expect(t(`study.tool.${kind}`)).not.toMatch(/^study\./);
  }
});
