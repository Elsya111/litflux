# Changelog

## 0.46.0

- Remove historical compatibility: only schema 0.3 is accepted; `internalFlows`, `scopeSummaries`, `scopeSummariesByLevel`, `presentation.granularity`, project locales, superflow storage migration and old view snapshots are no longer read. The two bundled sample models were upgraded to 0.3.
- Rename the overall artifact to 项目脉络图 / Project Atlas; the subgraphs remain 业务分解图 and 内部流程图.
- Add the decision frame: selecting a decision or reading through it draws a distinct frame around the decision and its exclusive branches.
- Tighten QA to four checks (`boundaryAndMeaning`, `depthAndSource`, `branchesAndNavigation`, `componentProviders`) with source/page anchors; require `review.author`.
- Require planning, `sourceScope`, `entrypoints`, `reading` and no open clarifications for delivery; planning missing is now an error.
- Add `--check-only`, `render_graph.py --review`, shared `compile_review.py`, real `delivery_audit` wiring, and `business_dag.py check` warnings.
- Allow `primaryFrom` to name an external boundary input; allow `sourceCalls` lines inside the owner source when the endpoint range is narrower.
- Reduce `budgetUnderuse` noise and exclude already-selected invocation components.
- Enforce business-meaningful labels: numbered/generic labels such as 结果1/结果2 and duplicate concept names are rejected. The viewer no longer adds numeric suffixes.
- Fix decision counts under `business-node.` scopes; the status bar now reports declared nodes/decisions, page nodes/decisions, boundary copies and events.
## 0.45.0

- **Breaking rename without compatibility:** the first graph is now the business decomposition graph (`businessDAG`), the second graph is the internal workflow graph (`internalFlows`). Old `understandingDAG`, `businessViews`, `sourceStops` and related names are no longer read. Literal source-function fields such as `source-function`, `definitions`, `implementation`, `signature` and `method` keep their original meaning.
- After the project is read and understood, confirm breadth/depth before drawing (`review.planning`): whole project / main flows / selected scope, and overview / key paths / implementation-to-source. Missing planning is a hint; independent QA must explain the chosen depth.
- Source endpoints are now **structurally hard, evidence-soft**: real source location, concrete detail and `views`/`stop` exclusivity remain required; `sourceCalls`/`delegates`/`noProjectCalls` and multi-stage child graphs become hints/warnings for the agent and QA to judge.
- Add `decision.kind` (`guard`/`loop`/`break`/`exception`/`join`); `exception` may have empty inputs; `break` needs `merge`. Document the loop + break + try/except recipe.
- All judgment branches are now shown together. Decision out-edges are solid amber and control edges are excluded from the data/resource solid forest; `whenActive` constraints are dashed amber; loop/recursion/goto feedback stays wine. Double-click branch cycling is removed.
- Add `branchNotPacked` warnings when a branch has more than three exclusive business steps before its merge and no `members` grouping.
- Add `callSiteUnmapped` build warnings and visible viewer reasons for unmapped call-site ports instead of a silent source fallback.
- Fix `primaryMissing` to count distinct predecessor steps/decisions, not every input value; add `error`/`warning`/`hint` severity, `warningSummary`, and `review.warningPolicy` acknowledgement for warnings/hints.
- Tighten detail budgets to 30 ordinary nodes and 5 decisions.
- Add previous-step reading, branch controls in the reading panel, and a design system for spacing, typography, node/edge styling, motion and branch readability.

## 0.44.0

- Author only the detail view; main/core derive from it by `importance` (`main`/`supporting`/`auxiliary`). Detail limits are 35 ordinary nodes and 7 decisions; main/core have no numeric limit.
- Decisions are part of the fixed control spine: all applicable decisions show in every tier. `importance`/`minGranularity` no longer hide a triangle; the detail view's applicable-decision ceiling of 7 is a build error. `views[].decisions` is deprecated (register once in `presentation.decisions`).
- Add `merge` for decision branch rejoins, retain common successors during branch projection, and add author-chosen `primaryFrom` for the solid predecessor. Undeclared ties produce build warnings; the viewer no longer picks a predecessor by id order.
- Add envelope event badges at the workflow hub and tabs; replace the canvas event lightning shape with the same envelope symbol.
- Make independent QA a hard build gate: `review.qa` plus all seven `review.acceptance.checks` and non-blocking `issues` are required for delivery builds.
- Default delivery outputs to `.litflux/output/` and collaboration artifacts to `.litflux/work/`.
- Rename runtime `superflow` identifiers to `litflux`; keep a one-time localStorage migration.
- Add common-modeling-mistake diagnostics and improve `members`, multi-producer, resource-read, source-range and build-report messages.
- Add `stop.reason: "omitted"` for source-backed code deliberately outside the reviewed scope, `aggregate` resource writes, semantic `sourceCalls`/`delegates` validation, project-overview schema checks, language routing from the review, and clearer budget/entry diagnostics.

## 0.42.0

- **Breaking rewrite:** the agent now performs source discovery, function/call reading, role inference, the project guide, semantic review, source-call audit, reading records and workplan merge by reading the source. Scripts are deterministic only.
- Removed non-deterministic scripts: `extract_python.py`, `python_inventory.py`, `source_project.py`, `source_facts.py`, `node_roles.py`, `focus_graph.py`, `project_catalog.py`, `semantic_review.py`, `source_calls.py`, `review_gate.py`, `workplan.py`, plus `adapters/` and `core/`.
- Kept deterministic scripts: `build_graph.py`, `validate_graph.py`, `render_graph.py`, `route_language.py`, `business_views.py`, `business_dag.py`.
- New build entry: `build_graph.py MODEL.json OUTPUT --review REVIEW.json --source-root ROOT --language zh|en`. Removed `--project-review`, `--facts`, `--adapter`, `--publish`, source fingerprints and automatic extraction.
- Multi-agent collaboration: the lead also acts as shared-role owner; it writes `litflux.workplan.json`/`litflux.spec.json` and `fragments/shared.json`; workflow owners return both graphs plus source ranges, `sourceCalls`/`delegates` and open questions; QA stays independent. No `workplan.py`.
- `validate_graph.py` accepts agent-authored `internalFlows` again through `business_views.py`.
- Remove tests for deleted extraction/gate/workplan modules; keep regression tests for the deterministic scripts and viewer.
- Historical 0.39.0–0.41.0 entries describe behavior removed in this version and remain for history.

## 0.41.0

- Extend the workplan with `sharedArtifacts` so the lead prepares discovery/model/catalog once and subagents stop re-discovering the repository.
- Assign primary source files to workflow owners and verify coverage in `check`; record deliberate exclusions with reasons.
- Add two-phase QA (`independent` then `compare`) so independent findings are written before seeing authored explanations.
- Add `workplan.py audit` to detect duplicate identities, binding splits, unassigned source and missing reading receipts across fragments.
- Add shared-role change requests and make open requests block merge.
- Update orchestration docs and regression tests.

## 0.40.0

- Make the core pipeline language-neutral through a `SourceAdapter` contract. Reviewed facts/models are the primary path; Python AST extraction is an optional adapter.
- Move Python entry candidates and control extraction behind the Python adapter; importing the core no longer loads `extract_python`, `python_inventory`, `project_catalog`, `semantic_review`, `node_roles` or `source_calls`.
- Add language-neutral call-evidence validation in `core/calls.py`; generic projects must provide `sourceCalls` (possibly empty) and are checked for unresolved, complex, decomposed-child and multi-stage cases.
- Add neutral explanation coverage helpers in `core/semantic.py` and neutral catalog attachment/Markdown in `core/catalog.py`.
- Allow reviewed facts to carry per-unit `calls`/`control` evidence; publication audits it without language-specific parsing.
- Update reports to expose adapter capabilities; update README/SPEC and regression tests.

## 0.39.0

- Clarify that the business decomposition graph contains business nodes only; data, resources, components, events and decisions belong to the internal workflow. A node identity is implementation + effective component bindings + members + implementation choices.
- Add the event boundary role (schema 0.3): events appear only at workflow entry, must produce data, need source evidence, and never become decomposition nodes or operations.
- Add `componentAction` for component reference outputs and tighten component-provider direction: a provider edge targets the function the component actually provides; function→component means create/load/select/inject/configure/register/mutate/return.
- Keep data identity in the model when a resource read/write payload is omitted from the display; generic resource labels are rejected when the intermediate data is hidden.
- Add importance hints and `budgetUnderuse` warnings for soft budget filling; operation membership and entry targets remain fixed across tiers.
- Update both language branches, model/dataflow docs, viewer event rendering, and regression tests.

## 0.38.1

- Close the false-simple loophole found by the independent contest_rag run: a multi-stage leaf can no longer be kept as `simple` with a written `composition` note. Multi-stage processing always requires child views.
- Reject `sourceCalls` entries whose `disposition: "decomposed"` points to the same node or to a nonexistent DAG node; a self-referential `childNode` is not decomposition.
- Keep `composition` as explanatory metadata only; it cannot waive the hard gate. Update the mechanism, workflow, publication, model and buildable-format references in both languages.
- Add regressions for composition-waiver rejection and self-child decomposition.

## 0.38.0

- Add a unified [mechanism contract](skills/litflux/references/mechanism.zh.md) / [English](skills/litflux/references/mechanism.en.md): four object roles, two graphs, five edge types, identity, entrances, tiers, source endpoints, interface/implementation resolution, clarification and publication.
- Audit source endpoints instead of trusting a self-declared `simple`: list project/interface calls, `await`/task scheduling, branches, loops and construction; resolve Protocol/ABC/interface calls through fields, construction/injection/factories and actual assembly; block unresolved or known-complex implementations. A multi-stage simple leaf now always requires child views; a written composition note cannot waive it.
- Add `source_calls.py` and integrate it into `review_gate.py` and `business_dag.py inspect --root`; `--publish` now reports source-call/interface gaps and open clarifications.
- Add optional subagent division: lead agent + project scout + workflow owners + shared-role owner + independent QA; `workplan.py prepare/check/merge` validates workstreams and merges review fragments with conflict detection.
- Document the division, handoff, prompt template and fragment schema in both languages; update workflows, model fields, publication and README commands.
- Bump the engine and dataflow-facing docs to 0.38.0; dataflow contract remains 0.2.

## 0.37.1

- Remove conflicting exposure-edge navigation wording from both governing language references; the business graph continues to draw decomposition edges only.
- Make draft inspection, repair and final acceptance precede publication in both workflows; align source-leaf examples with exact ranges and delegate review requirements.
- Clarify scope-preserving source discovery, professional project explanations, component-provider labels and the distinction between storage resources and callable components.
- Allow a source-backed internal reading boundary only for explicitly selected local workflows; whole-project deliveries still reject internal entrances.

## 0.37.0

- Define first-layer roots as source-backed external trigger functions (HTTP, commands, external events and documented callers), excluding code tests; keep internal algorithms below their callers.
- Require complete selected-language instructions and primary source reading records, target-project goal evidence, concrete-delegate review, exact source ranges and final artifact acceptance for publication.
- Add a full clickable Function decomposition graph with shared origins, current path/location, search, zoom and real-context navigation. It has no global node/edge/depth budget and draws decomposition edges only.
- Keep registration metadata separate and show important component → provided-function relations from actual receiver/invocation evidence; preserve invocation metadata in generic source facts.
- Preserve professional project terminology and keep reader/visualization goals out of the target project's overview.
- Use explicit source endpoint ranges without leaking adjacent processing or mutating range metadata.


## 0.36.4

- Audit all 16 reference Markdown files against the governing business DAG rules and both language workflows.
- Replace the legacy Chinese 0.1 authoring contract with current 0.2 model/review guidance; remove conflicting invocation merging, tier-dependent steps, numbered-value labels and component bundling advice.
- Align source scope commands, native/generic preparation and review-digest history behavior; remove obsolete version headings and repair their links.
- Keep historical document snapshots outside the skill and distribution. Reading compatibility does not define a second authoring workflow.

## 0.36.3

- Reject unrelated implementation redirects from grouped steps, mixed single-call/group declarations and implementation choices outside the current source region.
- Restrict composition-local component construction evidence to that composition; sibling constructions cannot establish a binding.
- Require source fingerprints for publishing reused native models, invalidate caches when the selected Python file set changes, and prevent unproven or source-omitting drafts from claiming publication readiness.
- Keep native English coverage and build guidance in English, and use a compact digest of the complete authored DAG to invalidate stale history after review changes.
- Align contributor commands with the business DAG workflow and archive stray local benchmark artifacts outside release contents. Strengthen incomplete-review diagnostics.

## 0.36.2

- Inspect authored business nodes before the complete DAG can compile, retaining each component context and exact composition boundary.
- Report actual public inputs/returns, stage ports and projection issues together; continue reporting other nodes after a local error without inventing repairs or claiming semantic acceptance.
- Document source conversions and coherent grouping in both language branches, based on an independent generation failure that mixed pending work with its completed result.
- Remove conflicting legacy tree/standalone-view authoring directions from the current workflows and field guides; new reviews use node views and source stops in one business DAG.

## 0.36.1

- Preserve selected-branch processing when a judgment is hidden by a tier or folded inside the current view; disclosure changes triangle visibility, not execution semantics.
- Retain unresolved guard limitations instead of treating them as proven active choices. Add regression and browser checks for both branches across all three tiers.

## 0.36.0

- Add source-backed `exposes` relationships for registered routes, commands and event callbacks, separate from execution/decomposition steps.
- Keep capability dependencies and lifecycle construction evidence in the business DAG; validate registration scope, contexts, cycles and reachability.
- Navigate from application setup to event-time capabilities with independent inputs, preserving the actual return path and history without adding fake execution edges.
- Document void registration completion and update both language branches. The independent 0.35 project test exposed this gap and did not pass; structural checks do not certify project understanding.

## 0.35.0

- Adopt source-grounded project-entry decomposition before internal workflows, with node identity determined by implementation and effective component bindings.
- Fix processing members, invocation positions and entry targets across tiers for the same branch/context; refine the shared decomposition to satisfy core budgets.
- Replace single-parent navigation, implementation-only sharing and whole-project internal-function shortcuts; continue through known complex interface implementations before source leaves.
- Compile explicit business DAGs with source scopes, effective component bindings, source endpoints, derived occurrence edges, cycle/reachability checks and a publication gate.
- Reject tier-specific processing changes; preserve stable stage IDs, context-specific implementation defaults and navigation snapshots.
- Display direct successors, shared origins and expandable project decomposition while preserving the actual entry path.
- Update bilingual authoring instructions and tools. Structural and browser fixture checks do not replace independent project generation acceptance.

## 0.34.0

- Require source-backed project understanding before graph design, covering execution, semantics, data/control dependencies, branches and abstract/concrete wiring; preserve it as reusable project context in the selected language.
- Keep normal and exception-handler values as alternatives, isolate sibling handlers, run else only on success and retain finally effects without leaking rethrow-only values into later successful returns.
- Validate exception merge conditions and disclose unknown throw positions; retain source-defined value types for imported uppercase constants instead of treating them as classes.
- Keep Python contract discovery when a project also contains HTML/CSS, configuration or deployment glue.
- Share source scope across project guides, semantic tasks and extraction; omit secondary test code by default and support explicit scope overrides.
- Hide all graph descendants in source mode while retaining measurable layout for returning to the graph.
- Remove project-specific entry selection; reviewed entry order is authoritative.
- Index interface bindings instead of repeatedly scanning every child port.
- Reuse fingerprinted source models and emit manageable batches of pending semantic tasks.
- Require a source-grounded delivery plan before publishing; incomplete workflow samples remain visibly marked drafts.
- Check recursive diagram coverage from actual workflow entrances and implementation choices, stopping at reviewed source endpoints; unused definition libraries do not require diagrams.
- Let agents explicitly curate guide symbol depth while retaining primary file explanations, contract implementation checks, complete source indexes and honest source-only counts.
- Initialize workflow entrances and project guides without projecting an unused global graph; node budgets are checked when a workflow is opened.
- Reject duplicated data/resource/component identities before role normalization instead of silently overwriting an endpoint.
- Emit the next missing business review frontier before expanding its unreviewed descendants, and avoid duplicate scope-reading tasks.
- Inspect reviewed stage ports, producer/consumer relationships and endpoint issues before a full build without inventing concepts or modifying source facts.
- Preserve reviewed business names and purposes when selecting interfaces or implementations; enter the selected implementation rather than a fixed business redirect, and audit alternative implementation coverage.
- Refresh accessible names and tooltips when reusing canvas nodes after implementation changes.
- Reject active non-feedback business-stage cycles instead of disguising nonconvex groups as data role copies; retain genuine resource read/write and same-value return roles.
- Retain child-projection failures in entry diagnostics so a source fallback cannot silently pass as a successfully reviewed child diagram.
- Distinguish nonexistent member IDs from operations outside the current child scope in authoring errors; document and test real definitions as workflow reading roots.

## 0.33.0

- Make agent-led understanding and adaptable tool/template selection explicit in both language workflows.
- Add language-neutral source discovery, reading tasks, fingerprints and an optional compact-facts compiler.
- Build project guides and maps from generic models without running Python AST or Python role inference first.
- Preserve interfaces, traits, protocols, abstract classes and reviewed implementation candidates.
- Report source scope, omitted/unmodeled files and actual adapter capabilities separately from semantic review.

## 0.32.1

- Preserve actual graph measurements while viewing source, so returning to a graph after a source-page reload restores its layout correctly.
- Retain source-page focus isolation without removing the graph from layout measurement.
- Add English and Chinese installation, usage, support, and development documentation.
- Adopt Apache-2.0 for LitFlux; preserve MIT notices for the bundled Dagre and Graphlib libraries.
- Separate local benchmark history from portable regression tests and release contents.

## 0.32.0

- End progressive navigation at accurately located original source when further diagrams would add little understanding.
- Preserve source context in the function call tree and back/forward navigation.
- Route Chinese and English requests into their respective authoring workflows before semantic review.
- Require matching review and output languages, while preserving original source identifiers and paths.

Earlier development snapshots are retained locally in the ignored `history/` archive.
