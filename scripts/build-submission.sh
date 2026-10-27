#!/usr/bin/env bash
# Build the hackathon submission tree (SPEC §9, JM-D17): only the parts the entry needs, from one commit, with no
# history. The tree is written to OUT; nothing is pushed or submitted.
#
#   scripts/build-submission.sh [--ref REF] [--no-chemistry] [--verify] OUT
#
#   --ref REF       the commit to build from (default HEAD; the working tree's uncommitted changes are never included)
#   --no-chemistry  leave the Chemistry pack out; by default it ships with Mathematics and Physics (owner, §9)
#   --verify        afterwards, copy OUT to a scratch folder, install it from its lockfiles and run the core suites
#                   there, so OUT itself never holds node_modules, .venv or target
#
# Needs git, uv, pnpm, cargo and Node 24 (.nvmrc). The lockfiles are regenerated for the smaller workspace from the
# versions already pinned here, so `pnpm install --frozen-lockfile`, `uv sync --locked` and `cargo build --locked`
# work in the tree.
set -euo pipefail

ref=HEAD chemistry=1 verify=0 out=""
while (($#)); do
  case "$1" in
    --ref) ref="$2"; shift 2 ;;
    --no-chemistry) chemistry=0; shift ;;
    --verify) verify=1; shift ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    -*) echo "unknown option $1" >&2; exit 2 ;;
    *) out="$1"; shift ;;
  esac
done
[[ -n "$out" ]] || { echo "usage: $0 [--ref REF] [--no-chemistry] [--verify] OUT" >&2; exit 2; }
repo="$(cd "$(dirname "$0")/.." && pwd)"
[[ "$(node -v 2>/dev/null)" == v24.* ]] || { echo "Node 24 is needed (.nvmrc); found $(node -v 2>/dev/null || echo none)" >&2; exit 1; }
if [[ -e "$out" ]] && [[ -n "$(ls -A "$out" 2>/dev/null)" ]]; then
  echo "$out exists and is not empty; choose a new folder" >&2; exit 1
fi
mkdir -p "$out"
out="$(cd "$out" && pwd)"

subjects=(mth phy)
((chemistry)) && subjects+=(chm)

# What ships. Everything else in the repository stays out: Studio and the authoring app (apps/studio), the frozen S0
# prototype, the telemetry ingest, the private specification and its contract additions, governance records,
# packaging and release tooling, repository-rule tests, CI configuration, held-out evals, the Accounting pack, and
# CONTRIBUTING.md (its content licence line says CC BY 4.0, where §9 and the packs' records say LicenseRef-Own).
include=(
  # Root manifests, lockfiles, toolchain pins and licences
  .dependency-cruiser.cjs .editorconfig .gitignore .importlinter .nvmrc .python-version
  Cargo.lock Cargo.toml LICENSE NOTICE README.md THIRD_PARTY_NOTICES
  deny.toml dependency-reviews.toml eslint.config.js package.json pnpm-lock.yaml pnpm-workspace.yaml
  pyproject.toml rust-toolchain.toml tsconfig.base.json turbo.json uv.lock
  # The desktop app and its shared packages
  apps/desktop packages assets
  # The engine, its workers and the cloud gateway (with the research agent, §18); Study's worker, which agent-core and
  # the gateway depend on
  services/agent-core services/tool-worker services/perception-worker services/study-worker services/cloud-gateway
  # The pack builder and the development signer: the browser demo host builds and signs the content packs from their
  # sources on first launch (apps/desktop/dev/seed_packs.py), with the published development key only
  services/pack-builder services/signing-service
  # Public wire contracts, the tutor's authored content and skills (teaching skills per shipped subject, below), and
  # the evaluation corpora the tests read
  contracts content/agent content/curriculum/README.md evals
  skills/counts.toml skills/agent skills/pedagogy skills/teaching/DESCRIPTION.md
  # Repository tooling the app and its checks run: codegen, the browser demo host, the browser test drivers and the
  # offline test runner; the asset licence register, which the app shows (App.tsx)
  scripts/pyproject.toml scripts/README.md scripts/jana_tools scripts/codegen scripts/ci
  scripts/governance/shipped-assets.toml
)
for s in "${subjects[@]}"; do
  include+=("content/curriculum/$s" "content/curriculum/ref/$s-o" "skills/teaching/$s")
done
include+=(content/curriculum/ref/common)
exclude=(
  # Held-out items (sealed, release key only) and anything the private specification owns
  ":(exclude)evals/held-out"
  # The gateway's deployment folder names internal hosts, project ids and an address; only the local dev config ships
  ":(exclude,glob)services/cloud-gateway/deploy/*"
)

# Tests that need what the tree leaves out, deselected there (pytest node ids; see below). Found by the trial install
# of 2026-10-27; each fails in the tree only because the file named is absent. --verify catches any new one.
A=services/agent-core/tests P=services/pack-builder/tests
deselect_always=(
  # The Accounting pack's sources (content/curriculum/acc, ref/acc-o), or every launched subject's pack at once
  "$A/test_cur06_syllabus_points.py::cur06_kc_and_lesson_points"
  "$A/test_m11e_degraded.py::arc26_degraded_modes"
  "$A/test_m13_misconception_wiring.py::test_ref_chart_fits_the_contract"
  "$A/test_m13_misconception_wiring.py::test_runtime_chart_decides_wrong_account_class"
  "$A/test_m13e_retrieval.py::mem21_topic_scoped"
  "$A/test_m13e_retrieval.py::test_grounding_reaches_the_coach_prompt"
  "$A/test_m13f_teaching_skills.py::skl25_kc_to_skill_coverage"
  "$A/test_m13g_learn.py::test_lesson_view_resolves_blocks_and_never_carries_keys"
  "$A/test_m13g_learn.py::test_subject_map_sections_tiles_and_states"
  "$A/test_m13g_learn.py::test_subject_map_without_a_working_pack"
  "$A/test_m25a_snap_and_working.py::jrn06_failure_branches[F3]"
  "$A/test_m25b_numbers_and_answers.py::prd05_not_sure_on_out_of_pack[nearest_lesson_cited]"
  "$A/test_m25b_numbers_and_answers.py::prd05_not_sure_on_out_of_pack[signal_and_honesty_rule]"
  "$A/test_m25b_numbers_and_answers.py::prd05_zero_unchecked_numbers[suites]"
  "$A/test_m25b_offline_and_privacy.py::prd03_core_journeys_offline"
  "$A/test_m25b_offline_and_privacy.py::prd07_no_account_no_traffic"
  "$A/test_m45a_ask_anything.py::stu20_homework_routes_to_tutor"
  "$A/test_m45a_ask_anything.py::uxs67_one_input_routes"
  "$A/test_mastery_tutor_handoff.py::test_all_new_mastery_questions_and_corrected_physics_keep_every_checked_board_line"
  "$A/test_prm09_course_glossary.py::test_prm09_glossary_terms_from_the_packs"
  "$P/test_cur18_quantities.py::test_cur18_check_arguments_bind"
  "$P/test_loc10_pack_units.py::loc10_unit_format[acc]"
  "$P/test_m13_chart_of_accounts.py"
  "$P/test_m13_content_gaps.py::test_build_accepts_structured_items"  # also fails on main, for another reason
  "$P/test_m13_content_gates.py::cur11_lesson_structure_valid"
  "$P/test_m13_content_gates.py::cur11_step_lesson_structure_valid"
  "$P/test_m13_content_gates.py::cur12_worked_example_checked"
  "$P/test_m13_content_gates.py::cur13_item_record_complete"
  "$P/test_m13_content_gates.py::cur16_diagnostic_mcq_rules"
  "$P/test_m13_content_gates.py::cur25_qa_checks_block"
  "$P/test_m13_content_gates.py::cur28_conventions_applied"
  "$P/test_m13_content_gates.py::prv17_pack_content_scan"
  "$P/test_m13_mock_papers.py::asm15_blueprint_match[acc]"
  "$P/test_m13_mock_papers.py::test_grade_scale_is_one_set_of_board_letters_per_pack"
  "$P/test_m13_mock_papers.py::test_mock_pool_keeps_practice_minimums[acc]"
  "$P/test_m17_diagrams.py::vsl22_library_entries_valid"
  "$P/test_studio_form_coverage.py::aut07_forms_cover_contract"
  # Studio's and the voice sidecar's packaging scripts (scripts/packaging) and the CI workflow (.github)
  "$A/test_m31_voice_closures.py::voc01_standard_engines_only"
  "$P/test_m22_studio.py::aut04_studio_not_in_student_build"
  "services/signing-service/tests/test_sec12_offline_update_signing.py::test_sec12_updater_key_is_the_apps_and_ci_holds_none"
)
deselect_chemistry=(
  # The Chemistry pack's sources (content/curriculum/chm, ref/chm-o)
  "$A/test_vsl46_chemistry_kinds.py"
  "$A/test_vsl47_predict.py::test_vsl47_scenarios_are_the_renderers"
  "$P/test_loc10_pack_units.py::loc10_unit_format[chm]"
  "$P/test_m13_mock_papers.py::asm15_blueprint_match[chm]"
  "$P/test_m13_mock_papers.py::test_mock_pool_keeps_practice_minimums[chm]"
)

git -C "$repo" rev-parse --verify --quiet "$ref^{commit}" >/dev/null || { echo "no commit $ref" >&2; exit 1; }
commit="$(git -C "$repo" rev-parse "$ref^{commit}")"
git -C "$repo" archive --format=tar "$commit" -- "${include[@]}" "${exclude[@]}" | tar -x -C "$out"
git -C "$repo" show "$commit:services/cloud-gateway/deploy/meta-dev.toml" \
  > "$(mkdir -p "$out/services/cloud-gateway/deploy" && echo "$out/services/cloud-gateway/deploy/meta-dev.toml")"

# The smaller workspace: no Studio member in pnpm or Cargo, no ingest in the Python checks' paths.
cd "$out"
sed -i.bak '/^  - apps\/studio$/d' pnpm-workspace.yaml
sed -i.bak 's|^members = \["apps/desktop/src-tauri", "apps/studio/src-tauri"\]$|members = ["apps/desktop/src-tauri"]|' Cargo.toml
sed -i.bak '/services\/ingest/d' pyproject.toml eslint.config.js
rm -f pnpm-workspace.yaml.bak Cargo.toml.bak pyproject.toml.bak eslint.config.js.bak
grep -q apps/studio pnpm-workspace.yaml Cargo.toml && { echo "Studio still in a workspace manifest" >&2; exit 1; }

# Lockfiles for that workspace, keeping every version already pinned (no upgrades).
export TURBO_TELEMETRY_DISABLED=1 DO_NOT_TRACK=1
uv lock --quiet
pnpm install --lockfile-only --prefer-offline --silent
cargo metadata --format-version 1 >/dev/null
# The import-layer contracts (ARC-18) name the ingest, which does not ship: drop its own contracts and its module lines.
python3 - <<'PY'
import pathlib, re
path = pathlib.Path(".importlinter")
blocks = re.split(r"(?=^\[importlinter:contract:)", path.read_text(), flags=re.M)
kept = [b for b in blocks if not b.startswith("[importlinter:contract:ops24-ingest-")]
path.write_text(re.sub(r"^    ingest\n", "", "".join(kept), flags=re.M))
PY

# The pinned skill count (SKL-24) for the teaching skills of the shipped subjects only.
teaching="$(find skills/teaching -mindepth 2 -maxdepth 2 -type d | wc -l | tr -d ' ')"
sed -i.bak "s/^teaching = [0-9]*$/teaching = $teaching/" skills/counts.toml && rm -f skills/counts.toml.bak

# Tests of the parts left out (the other subjects' packs, Studio, packaging and release tooling) are deselected in the
# tree's pytest configuration, by node id, so `uv run pytest` there runs everything else.
# (The ${a[@]+...} spelling keeps an empty list working under `set -u` in macOS's bash 3.2.)
deselect=(${deselect_always[@]+"${deselect_always[@]}"})
((chemistry)) || deselect+=(${deselect_chemistry[@]+"${deselect_chemistry[@]}"})
python3 - ${deselect[@]+"${deselect[@]}"} <<'PY'
import pathlib, sys
path = pathlib.Path("pyproject.toml")
text = path.read_text()
old = 'addopts = ["-ra", "--strict-markers"]'
assert old in text, "pytest addopts moved"
ids = "".join(f'\n    "--deselect={node}",' for node in sys.argv[1:])
path.write_text(text.replace(old, f'addopts = ["-ra", "--strict-markers",{ids}\n]'))
PY

# The submission repository: this tree as one commit, no history (§9). The author is this repository's git user.
git init --quiet --initial-branch=main
git add --all
git -c core.hooksPath=/dev/null -c user.name="$(git -C "$repo" config user.name)" \
  -c user.email="$(git -C "$repo" config user.email)" commit --quiet -m "Jana on Meta's models: submission for the Meta Global AI Developer Hackathon" \
  -m "Built from jana-meta $commit by scripts/build-submission.sh."

echo "built $out from $commit (subjects: ${subjects[*]})"
echo "files: $(git ls-files | wc -l | tr -d ' '), size without .git: $(du -sh -I .git "$out" | cut -f1)"

((verify)) || exit 0

# Install the tree from scratch in a copy and run the core suites there.
work="$(mktemp -d "${TMPDIR:-/tmp}/jana-meta-submission-check.XXXXXX")"
cp -R "$out/." "$work"
cd "$work"
echo "verifying in $work"
export UV_PROJECT_ENVIRONMENT="$work/.venv" CARGO_TARGET_DIR="$work/target"
status=0
pnpm install --frozen-lockfile
uv sync --locked --all-packages
cargo build --locked --workspace
uv run --frozen pytest -q -p no:cacheprovider services || status=1
pnpm test || status=1
cargo test --locked --workspace || status=1
echo "verify: $([[ $status == 0 ]] && echo passed || echo FAILED) in $work"
exit $status
