# Analyzer Insights Audit

## Findings

- `service-ui` uses controller/reducer/saga modules registered in the root store, not Redux Toolkit slices.
- Project analyzer settings are persisted through project configuration attributes with the `analyzer.` prefix.
- `service-api` rejects unknown project attributes, so every new analyzer feature toggle must be added to `ProjectAttributeEnum` and validated server-side.
- Existing suggest APIs already return ranking metadata through `SuggestInfo` (`resultPosition`, `esScore`, `esPosition`, `modelInfo`, `methodName`). These endpoints can be enriched instead of replaced.
- Existing launch cluster data is already available through `GET /v1/{projectKey}/launch/cluster/{launchId}` and is suitable for a root-cause cluster view.
- Existing launch comparison data is already available through `GET /v1/{projectKey}/launch/compare?ids=...` and can back comparison visuals.
- Existing flakiness data exists in widget loaders, but there was no dedicated UI-oriented API for launch/item flakiness, coverage, or triage aging.

## Implementation Direction

- Add a dedicated analyzer insights API in `service-api` for launch-level and item-level insight aggregation.
- Reuse the existing cluster and launch comparison APIs where they already provide the required data shape.
- Enrich `SuggestInfo` responses so the make-decision modal can show confidence, ranking, and hybrid/rerank indicators without introducing new suggestion endpoints.
- Add project-scoped analyzer feature flags under a new `Insights` sub-tab in the existing analyzer settings UI.
- Add a dedicated project-level Analyzer Insights page in `service-ui` backed by a new controller module, plus a lightweight flakiness detail modal.

## Scope Covered By The New API/UI

- Flakiness badge and detail panel
- Quarantine candidates tab
- Confidence score indicator
- Ranked suggestions panel
- Root-cause cluster view
- Triage aging heatmap
- Analyzer coverage KPI
- Release aggregate history view
- Launch comparison diff
- Hybrid search indicator