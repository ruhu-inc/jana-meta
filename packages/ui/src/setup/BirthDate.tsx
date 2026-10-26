// The date of birth asked when a profile is made (JM-D1, JM-D15): Jana is for learners aged 18 and over. The date is
// checked on this computer and then dropped; only the adult band is stored, and nothing is created for someone under 18.
import { useId } from "react";
import { isAdult } from "@jana/client-core";
import { useT } from "../i18n.js";
import { FIELD_LOOK, Notice } from "../primitives/index.js";

export type BirthDateCheck = "missing" | "invalid" | "under_18" | "adult";

/** What a date of birth allows: a profile only when it is `adult`. */
export function birthDateCheck(value: string, today: Date = new Date()): BirthDateCheck {
  if (value === "") return "missing";
  const adult = isAdult(value, today);
  return adult === null ? "invalid" : adult ? "adult" : "under_18";
}

/** The field, its one-line reason, and what an entered date means when it does not allow a profile. */
export function BirthDateField({ value, onChange, disabled = false, labelClass }: {
  value: string; onChange: (value: string) => void; disabled?: boolean; labelClass?: string;
}) {
  const t = useT();
  const help = useId();
  const check = birthDateCheck(value);
  return (
    <div className="flex flex-col gap-2">
      <label className={labelClass ?? "flex flex-col gap-1.5 text-meta font-medium text-muted"}>
        {t("first_run.birth_date")}
        <input type="date" className={FIELD_LOOK} value={value} disabled={disabled} required aria-describedby={help}
          aria-invalid={check === "invalid" || check === "under_18"} onChange={(event) => onChange(event.target.value)} />
      </label>
      <p id={help} className="text-meta text-muted">{t("first_run.birth_date_help")}</p>
      {check === "under_18" && <Notice tone="warn" message={t("first_run.under_18")} />}
      {check === "invalid" && <Notice tone="warn" message={t("first_run.birth_date_invalid")} />}
    </div>
  );
}
