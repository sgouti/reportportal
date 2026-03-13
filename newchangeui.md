You are a senior full-stack engineer agent. Your mission 
is to add 11 new UI features to ReportPortal's frontend 
that surface upgraded ML analyzer capabilities to QA 
engineers, team leads, and product managers.

REPOSITORIES:
UI:      https://github.com/reportportal/service-ui
API:     https://github.com/reportportal/service-api
Analyzer:https://github.com/reportportal/service-auto-analyzer

=======================================================
MISSION
=======================================================

Build UI features that make the upgraded ML analyzer 
results visible, actionable, and trustworthy. Every 
feature must surface real analyzer data — no mocked 
values in production code. Engineers should understand 
WHY the system made decisions, not just WHAT it decided.

=======================================================
RULES — NEVER VIOLATE THESE
=======================================================

- React + Redux — match existing codebase patterns exactly
- No new UI framework or CSS library introductions
- All features behind feature flags (FF_ prefix in Redux)
- Mobile responsive — every new component works at 768px
- Accessibility — ARIA labels on all new interactive elements
- No breaking changes to existing UI components or routes
- New API endpoints must be backward compatible
- Loading states for every async data fetch
- Empty states for every new widget (no blank panels)
- Error boundaries on every new component

=======================================================
STEP 1: READ FIRST — DO NOT SKIP
=======================================================

Before writing any code:

1. Clone all three repositories
2. Read service-ui/src/ full structure — understand:
   - Component patterns (functional vs class)
   - Redux store structure and action patterns
   - Existing styling approach (CSS modules or styled)
   - How widgets are registered in dashboards
   - How launch items are rendered in test view
   - Existing JIRA integration component structure
   - How existing ML suggestions are displayed today
3. Read service-api/ to understand:
   - Existing REST endpoint patterns
   - Auth and project scoping on endpoints
   - How analyzer results are currently returned
4. Document what you found before writing code

=======================================================
STEP 2: BACKEND API ENDPOINTS NEEDED
=======================================================

Add these endpoints to service-api before any UI work.
UI components depend on these contracts.

2a. Flakiness data per test item:
GET /api/v1/{projectName}/item/{itemId}/flakiness
Response:
{
  "itemId": "string",
  "flakinessScore": 0-100,
  "label": "STABLE|UNSTABLE|FLAKY|CRITICALLY_FLAKY",
  "autoQuarantine": boolean,
  "passRate": float,
  "alternationRate": float,
  "analyzedRuns": integer,
  "history": [
    {"launchId": str, "status": "PASSED|FAILED", "timestamp": str}
  ]
}

2b. Flakiness batch for full launch:
GET /api/v1/{projectName}/launch/{launchId}/flakiness
Response:
{
  "launchId": "string",
  "summary": {
    "stable": integer,
    "unstable": integer,
    "flaky": integer,
    "criticallyFlaky": integer,
    "quarantined": integer
  },
  "items": [ ...array of flakiness results... ]
}

2c. Failure clusters for a launch:
GET /api/v1/{projectName}/launch/{launchId}/clusters
Response:
{
  "clusters": [
    {
      "clusterId": "string",
      "label": "string",
      "size": integer,
      "representativeError": "string",
      "linkedTicket": "string|null",
      "items": ["itemId1", "itemId2"]
    }
  ]
}

2d. ML suggestion confidence scores:
GET /api/v1/{projectName}/item/{itemId}/suggestions
Response:
{
  "suggestions": [
    {
      "defectType": "string",
      "defectLocator": "string", 
      "confidence": float,
      "matchSource": "semantic|keyword",
      "matchedLaunch": "string",
      "matchedItem": "string"
    }
  ]
}

2e. Triage aging for a project:
GET /api/v1/{projectName}/triage/aging
Response:
{
  "buckets": {
    "fresh": {"count": int, "items": []},
    "aging": {"count": int, "items": []},
    "stale": {"count": int, "items": []},
    "breach": {"count": int, "items": []}
  },
  "totalToInvestigate": integer
}

2f. Auto-analysis coverage stats:
GET /api/v1/{projectName}/analyzer/coverage
Response:
{
  "currentSprint": {
    "coveragePercent": float,
    "avgConfidence": float,
    "manualTriagePercent": float,
    "totalItems": integer,
    "autoClassified": integer
  },
  "previousSprint": { ...same structure... },
  "trend": "IMPROVING|STABLE|DEGRADING"
}

2g. Release / sprint aggregate view:
GET /api/v1/{projectName}/release/{releaseAttribute}
Response:
{
  "releaseName": "string",
  "passRate": float,
  "qualityGateStatus": "PASS|WARN|BLOCK",
  "openCriticalFailures": integer,
  "flakyExcluded": integer,
  "autoClassified": float,
  "newFailuresVsPrevious": integer,
  "fixedVsPrevious": integer,
  "launches": [ ...launch summaries... ]
}

2h. Launch comparison diff:
GET /api/v1/{projectName}/launch/compare
  ?baseline={launchId}&target={launchId}
Response:
{
  "newFailures": [ ...items... ],
  "fixed": [ ...items... ],
  "consistent": [ ...items... ],
  "flaky": [ ...items... ]
}

=======================================================
STEP 3: REDUX STATE ADDITIONS
=======================================================

Add to existing Redux store. Do not modify existing 
slices — add new slices only.

New slices to add:

flakinessSlice:
  state: { byItemId: {}, byLaunchId: {}, loading, error }
  actions: fetchItemFlakiness, fetchLaunchFlakiness, 
            quarantineItem, releaseFromQuarantine

clustersSlice:
  state: { byLaunchId: {}, loading, error }
  actions: fetchClusters, linkClusterToTicket

suggestionsSlice:
  state: { byItemId: {}, loading, error }
  actions: fetchSuggestionsWithConfidence

triageAgingSlice:
  state: { byProject: {}, loading, error }
  actions: fetchTriageAging

analyzerCoverageSlice:
  state: { byProject: {}, loading, error }
  actions: fetchCoverage

releaseSlice:
  state: { byRelease: {}, loading, error }
  actions: fetchReleaseView

featureFlagsSlice:
  state:
    FF_FLAKINESS_ENABLED: true
    FF_CLUSTERS_ENABLED: true
    FF_CONFIDENCE_SCORES_ENABLED: true
    FF_RANKED_SUGGESTIONS_ENABLED: true
    FF_TRIAGE_AGING_ENABLED: true
    FF_RELEASE_VIEW_ENABLED: true
    FF_COVERAGE_KPI_ENABLED: true
    FF_COMPARISON_DIFF_ENABLED: true
    FF_HYBRID_SEARCH_INDICATOR_ENABLED: true

=======================================================
STEP 4: BUILD THESE 11 UI COMPONENTS
=======================================================

Build in this exact order. Each depends on previous.

---
FEATURE 1: FlakinessBadge
---
File: src/components/flakiness/FlakinessBadge.jsx

Props: { score: number, label: string, itemId: string }

Renders a small pill badge next to test item name:
- STABLE (score 0-20):          green pill  "STABLE 95"
- UNSTABLE (score 21-50):       amber pill  "UNSTABLE 42"
- FLAKY (score 51-75):          orange pill "FLAKY 63"
- CRITICALLY_FLAKY (76-100):    red pill    "CRITICAL 8"
- null score:                   no badge rendered

On click: opens FlakinessDetailPanel (Feature 2)

States:
- Loading: pulse skeleton same width as badge
- Error: no badge rendered, silent fail

Integrate into: existing test item row component
in the launch detail view. Badge appears immediately
after test item name, before status icon.

---
FEATURE 2: FlakinessDetailPanel
---
File: src/components/flakiness/FlakinessDetailPanel.jsx

Side panel (drawer) that opens from FlakinessBadge click.

Shows:
- Flakiness score gauge (0-100 arc visualization)
- Label with explanation in plain English:
  "This test changed status 8 times in the last 20 runs"
- Pass/fail history timeline: 
  last 30 runs as colored dots (green=pass, red=fail)
  in chronological order left to right
- Key metrics: pass rate %, alternation rate %, runs analyzed
- Auto-quarantine status with toggle (for QA leads only)
- "View all runs" link to filtered launch list

Fetches from: GET /api/v1/{project}/item/{itemId}/flakiness
Show loading spinner while fetching.
Show "Insufficient data — needs 10+ runs" if analyzedRuns < 10

---
FEATURE 3: QuarantineTab
---
File: src/components/flakiness/QuarantineTab.jsx

New tab inside launch detail view: "Quarantine"
Only visible when FF_FLAKINESS_ENABLED = true
Tab shows badge count of quarantined items.

Content:
- List of all auto-quarantined tests in this launch
- Each row shows: test name, flakiness score badge,
  quarantine reason, "Release" button
- Empty state: "No quarantined tests — great signal 
  reliability!" with checkmark icon
- Banner at top: "These N tests are excluded from 
  pass rate calculations"

Pass rate on launch header must recalculate 
excluding quarantined items when this feature is ON.
Show original vs adjusted pass rate:
"Pass rate: 91% (94% excluding 6 quarantined tests)"

---
FEATURE 4: ConfidenceScoreIndicator
---
File: src/components/analysis/ConfidenceScoreIndicator.jsx

Props: { confidence: float, defectType: string, 
         matchedLaunch: string }

Renders inline with existing auto-classified item display.
Current display: "✓ Auto-classified: Automation Bug"
New display:
"✓ Auto-classified: Automation Bug
 Confidence: 94% | Matched: Sprint 38 launch"

Color coding on confidence:
- 90-100%: green text
- 70-89%:  default text
- 50-69%:  amber text + amber dot warning icon
- below 50%: red text + "Review recommended" tooltip

Low confidence items (below 70%) get amber left border
on their row in the test list — draws eye without 
being alarming.

Integrate into: existing defect type display component
wherever auto-classified results currently render.

---
FEATURE 5: RankedSuggestionsPanel
---
File: src/components/analysis/RankedSuggestionsPanel.jsx

Replace existing single ML suggestion with ranked list.

Current: one suggestion shown
New: top 3 suggestions ranked by confidence

Layout per suggestion:
[1] Automation Bug — Timing Issue          87% ●●●●○
    Matched: "session timeout" in Sprint 41
    [Apply this decision]

[2] Product Bug — API response changed     61% ●●●○○ 
    Matched: "401 on checkout" in Sprint 39
    [Apply this decision]

[3] System Issue — Env config mismatch     45% ●●○○○
    Matched: "staging env var" in Sprint 37
    [Apply this decision]

Confidence bar: 5 filled dots proportional to score.
matchSource shown as small tag: "semantic" or "keyword"
in different colors so engineers see how match was found.

[Apply this decision] triggers existing defect type 
assignment flow — no changes to that logic.

Fetch from: GET /api/v1/{project}/item/{itemId}/suggestions
Only render when item is in TO_INVESTIGATE status.

---
FEATURE 6: RootCauseClusterView
---
File: src/components/clusters/RootCauseClusterView.jsx

New view mode toggle on launch detail page.
Existing: "Test" view (flat list of all items)
New toggle: "Clusters" view

Cluster card layout:
┌─────────────────────────────────────────────┐
│ 📦 DB Connection Timeout            31 tests│
│ "connection pool exhausted after..."        │
│ ████████████████████████░░░░░  62% of fails│
│ [Link to JIRA]  [Expand tests]  [Triage all]│
└─────────────────────────────────────────────┘

Clusters sorted by size descending.
"Triage all" button opens bulk decision modal —
apply one defect type to all items in cluster.
"Link to JIRA" opens existing JIRA integration modal
and applies ticket to all items in cluster.

Expand tests: shows collapsible list of test names
in this cluster. Each still links to individual item.

Empty state: "Clustering requires 5+ failures. 
This launch has fewer failures than needed."

Fetch from: GET /api/v1/{project}/launch/{id}/clusters
Show skeleton cards while loading (3 placeholder cards).

---
FEATURE 7: TriageAgingHeatmap
---
File: src/components/widgets/TriageAgingHeatmap.jsx

New dashboard widget. Register in existing widget catalog.
Widget name: "Triage Health"
Widget description: "Time-in-triage for To Investigate items"

Visual layout:
┌── Triage Health ─────────────────────────────┐
│                                              │
│  0–24h    ████████████████░░  24 items  ✓   │
│  1–3 days ████████░░░░░░░░░░   8 items  ⚠   │
│  3–7 days ████░░░░░░░░░░░░░░   4 items  ⚠   │
│  7+ days  ██░░░░░░░░░░░░░░░░   2 items  🔴  │
│                                              │
│  2 items breaching SLA — assign now          │
└──────────────────────────────────────────────┘

Bars are clickable — clicking "7+ days" opens filtered 
list of those specific To Investigate items.

SLA breach items: show assignee avatar if assigned,
"Unassigned" tag if not. Breach row pulses red border.

Fetch from: GET /api/v1/{project}/triage/aging
Refresh every 5 minutes automatically.
Empty state: "All clear — no items in triage!" 
with green checkmark.

---
FEATURE 8: AnalyzerCoverageKPI
---
File: src/components/widgets/AnalyzerCoverageKPI.jsx

New dashboard widget. Register in widget catalog.
Widget name: "Auto-Analysis Coverage"

Layout:
┌── Auto-Analysis Coverage ────────────────────┐
│                                              │
│   93%          ▲ +28% vs last sprint        │
│   Auto-classified                            │
│                                              │
│   Avg confidence:    87%                     │
│   Manual triage:      7%  (14 of 200 items) │
│   Trend:         IMPROVING  ↑               │
│                                              │
└──────────────────────────────────────────────┘

Trend indicator colors:
IMPROVING: green with up arrow
STABLE:    grey with right arrow  
DEGRADING: red with down arrow + tooltip 
           "Consider reviewing pattern rules"

Sprint comparison is automatic — uses launch attributes
with key "sprint" to group current vs previous.

If no sprint attributes set: show message 
"Add sprint attribute to launches to enable comparison"
with link to attribute documentation.

---
FEATURE 9: ReleaseAggregateView
---
File: src/pages/release/ReleaseView.jsx
Route: /ui/{projectName}/release/{releaseValue}

New top-level navigation item: "Releases"
Only shown when FF_RELEASE_VIEW_ENABLED = true

Page layout:

HEADER:
Release 3.2  |  Sprint 44  |  ● IN PROGRESS
[Quality Gate: ⚠ WARNING — Pass rate below 95% threshold]

METRICS ROW (4 stat cards):
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│Pass Rate │ │Open P0s  │ │New Fails │ │Fixed     │
│  91.4%   │ │    2     │ │   +18    │ │  +31     │
│ ▼ target │ │ ← blocks │ │vs 3.1   │ │vs 3.1   │
└──────────┘ └──────────┘ └──────────┘ └──────────┘

BELOW:
- Table of all launches in this release with 
  pass rate, failure count, auto-analysis coverage
  per launch row
- Launches sortable by date, pass rate, failures

Quality gate status logic:
PASS:  pass rate ≥ 95% AND open P0 failures = 0
WARN:  pass rate 85-94% OR 1 P0 failure
BLOCK: pass rate < 85% OR 2+ P0 failures

Release grouping: reads launch attribute "version" 
or "release" — whichever exists on the launches.

---
FEATURE 10: LaunchComparisonDiff
---
File: src/components/comparison/LaunchComparisonDiff.jsx

Add "Compare with..." button to launch toolbar.
Opens a modal to select baseline launch from same project.

After selection, show diff page:

NEW FAILURES (12)        appeared in this run
┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄
FIXED (8)                passed this run, failed before
┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄
CONSISTENT FAILURES (23) failing in both runs
┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄
FLAKY (6)                different status each run
┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄

Each section collapsible. Each test item row clickable
to open that item detail. "New Failures" section is 
expanded by default, others collapsed.

Shareable URL: comparison params go into query string
so engineers can share the diff link directly.

---
FEATURE 11: HybridSearchIndicator
---
File: src/components/analysis/HybridSearchIndicator.jsx

Small tag shown on each ML suggestion result indicating
how the match was found:

"semantic"  — blue tag  (BGE-M3 dense match)
"keyword"   — grey tag  (BM25 keyword match)
"hybrid"    — purple tag (both signals aligned)

Shown inside RankedSuggestionsPanel (Feature 5) 
next to each suggestion's match description.

Tooltip on hover explains in plain language:
semantic: "Matched by meaning — similar error 
           even with different wording"
keyword:  "Matched by shared keywords in error text"
hybrid:   "Strong match — both meaning and keywords align"

No separate data fetch needed — matchSource field 
already included in suggestions API response (Step 2d).

=======================================================
STEP 5: DASHBOARD WIDGET REGISTRATION
=======================================================

Register Features 7 and 8 in the existing widget catalog:

Locate widget registry file in service-ui.
Add both new widgets following exact same pattern 
as existing widgets:

- Widget key: TRIAGE_AGING_HEATMAP
- Widget key: ANALYZER_COVERAGE_KPI

Each must support:
- Drag and drop on dashboard grid
- Resize handles (min 2x2, max 4x2 grid units)
- Widget settings modal (project scope only)
- Refresh button in widget header
- Loading and empty states

=======================================================
STEP 6: NAVIGATION UPDATES
=======================================================

6a. Add "Releases" to left sidebar navigation
    Below "Launches" in nav order
    Only visible when FF_RELEASE_VIEW_ENABLED = true
    Show no badge count (releases have no urgency indicator)

6b. Add "Clusters" toggle to launch detail view toolbar
    Sits alongside existing view mode buttons
    Only visible when FF_CLUSTERS_ENABLED = true
    Disabled with tooltip if launch has fewer than 
    5 failures: "Need 5+ failures for clustering"

6c. Add "Quarantine" tab to launch detail tabs
    Only visible when FF_FLAKINESS_ENABLED = true
    Shows count badge of quarantined items

=======================================================
STEP 7: UNIT AND INTEGRATION TESTS
=======================================================

Create tests for every new component:

tests/flakiness/FlakinessBadge.test.jsx
- renders correct color for each label
- renders nothing when score is null
- opens detail panel on click

tests/flakiness/FlakinessDetailPanel.test.jsx
- shows loading state while fetching
- shows insufficient data message below 10 runs
- renders timeline dots in correct colors

tests/flakiness/QuarantineTab.test.jsx
- recalculates pass rate excluding quarantined
- shows empty state correctly
- release button calls correct API

tests/analysis/ConfidenceScoreIndicator.test.jsx
- correct color for each confidence range
- shows review recommended below 70%

tests/analysis/RankedSuggestionsPanel.test.jsx
- renders max 3 suggestions
- apply button triggers defect assignment
- shows semantic vs keyword tag correctly

tests/clusters/RootCauseClusterView.test.jsx
- sorts clusters by size descending
- triage all opens bulk modal
- expand shows correct test count

tests/widgets/TriageAgingHeatmap.test.jsx
- shows SLA breach row with pulse
- clicking row opens filtered list
- empty state renders correctly

tests/pages/ReleaseView.test.jsx
- quality gate shows correct status
- BLOCK state shows red banner
- launches table sorts correctly

Mock all API calls. No network calls in tests.
All tests must pass without any backend running.

=======================================================
STEP 8: FEATURE FLAG ADMIN UI
=======================================================

Add a section to existing project settings page:
"ML Features" section

Toggle switches for each feature flag:
□ Flakiness Detection & Quarantine
□ Root Cause Clustering  
□ Confidence Score Display
□ Ranked ML Suggestions (top 3)
□ Triage Aging Heatmap
□ Release Aggregate View
□ Auto-Analysis Coverage KPI
□ Launch Comparison Diff
□ Hybrid Search Indicator

All default ON. Admins can disable per project.
Saved to project settings via existing settings API.

=======================================================
DONE WHEN
=======================================================

✓ All 11 components built and rendering correctly
✓ All feature flags toggle each feature independently
✓ All new API endpoints returning correct shape
✓ Both new dashboard widgets appear in widget catalog
✓ Releases nav item routes correctly
✓ All unit tests passing with mocked APIs
✓ No existing tests broken
✓ All components responsive at 768px
✓ All interactive elements have ARIA labels
✓ Error boundaries on all new components
✓ Loading and empty states on every component
✓ Feature flag admin UI working in project settings
✓ No console errors or warnings in production build