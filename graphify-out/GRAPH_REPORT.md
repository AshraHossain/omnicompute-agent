# Graph Report - .  (2026-06-20)

## Corpus Check
- Corpus is ~9,649 words - fits in a single context window. You may not need a graph.

## Summary
- 346 nodes · 467 edges · 28 communities (27 shown, 1 thin omitted)
- Extraction: 76% EXTRACTED · 24% INFERRED · 0% AMBIGUOUS · INFERRED: 114 edges (avg confidence: 0.66)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_BaselineCache  AnomalyTriager  Anomaly|BaselineCache / AnomalyTriager / Anomaly]]
- [[_COMMUNITY_errors.py  OmniComputeError  TelemetryParser|errors.py / OmniComputeError / TelemetryParser]]
- [[_COMMUNITY_conftest.py  BaselineCache  baseline_cache_empty()|conftest.py / BaselineCache / baseline_cache_empty()]]
- [[_COMMUNITY_test_baseline_cache.py  TestEdgeCases  TestGetBaseline|test_baseline_cache.py / TestEdgeCases / TestGetBaseline]]
- [[_COMMUNITY__telemetry()  TestEdgeCases  TestSafeRangesIntegration|_telemetry() / TestEdgeCases / TestSafeRangesIntegration]]
- [[_COMMUNITY_test_anomaly_triager.py  TestBaselineCacheInteraction  TestNoAnomalies|test_anomaly_triager.py / TestBaselineCacheInteraction / TestNoAnomalies]]
- [[_COMMUNITY_Baseline computation and cachi  Telemetry data parsing  Anomaly triage and classificat|Baseline computation and cachi / Telemetry data parsing / Anomaly triage and classificat]]
- [[_COMMUNITY_to_json_str()  TestCoercionAndFallbacks  .test_negative_metric_value_is|to_json_str() / TestCoercionAndFallbacks / .test_negative_metric_value_is]]
- [[_COMMUNITY_Telemetry  .normalize_timestamps_to_utc()  schemas.py|Telemetry / .normalize_timestamps_to_utc() / schemas.py]]
- [[_COMMUNITY_TestConfidenceScoring  .test_stale_baseline_penalizes  .test_redundant_indicators_boo|TestConfidenceScoring / .test_stale_baseline_penalizes / .test_redundant_indicators_boo]]
- [[_COMMUNITY_TestZScoreCalculation  .test_z_score_negative_deviati  .test_z_score_positive_deviati|TestZScoreCalculation / .test_z_score_negative_deviati / .test_z_score_positive_deviati]]
- [[_COMMUNITY_TestSchemaValidation  .test_empty_metrics_dict_is_ac  .test_extra_unknown_fields_are|TestSchemaValidation / .test_empty_metrics_dict_is_ac / .test_extra_unknown_fields_are]]
- [[_COMMUNITY_TestEdgeCases  .test_batch_with_over_one_hund  .test_duplicate_node_id_in_sam|TestEdgeCases / .test_batch_with_over_one_hund / .test_duplicate_node_id_in_sam]]
- [[_COMMUNITY_TestCriticalSeverity  .test_high_positive_z_score_is  .test_high_negative_z_score_is|TestCriticalSeverity / .test_high_positive_z_score_is / .test_high_negative_z_score_is]]
- [[_COMMUNITY_TestUnitConversion  .test_battery_soc_percent_valu  .test_rf_signal_strength_dbm_i|TestUnitConversion / .test_battery_soc_percent_valu / .test_rf_signal_strength_dbm_i]]
- [[_COMMUNITY_TestTimestampNormalization  .test_invalid_timestamp_format  .test_iso8601_timestamp_is_par|TestTimestampNormalization / .test_invalid_timestamp_format / .test_iso8601_timestamp_is_par]]
- [[_COMMUNITY_TestHappyPath  .test_parse_valid_multi_node_b  .test_parse_valid_single_node_|TestHappyPath / .test_parse_valid_multi_node_b / .test_parse_valid_single_node_]]
- [[_COMMUNITY_test_telemetry_parser.py  TestIdempotence  .test_parsing_same_batch_twice|test_telemetry_parser.py / TestIdempotence / .test_parsing_same_batch_twice]]
- [[_COMMUNITY_TestMalformedJson  .test_empty_json_object_parses  .test_invalid_json_syntax_retu|TestMalformedJson / .test_empty_json_object_parses / .test_invalid_json_syntax_retu]]
- [[_COMMUNITY_omnicompute package|omnicompute package]]

## God Nodes (most connected - your core abstractions)
1. `BaselineCache` - 29 edges
2. `AnomalyTriager` - 29 edges
3. `to_json_str()` - 25 edges
4. `_telemetry()` - 19 edges
5. `Anomaly` - 18 edges
6. `OmniComputeError` - 12 edges
7. `TestConfidenceScoring` - 9 edges
8. `TestEdgeCases` - 9 edges
9. `TelemetryParser` - 8 edges
10. `TestCriticalSeverity` - 8 edges

## Surprising Connections (you probably didn't know these)
- `Component structure and responsibilities` --cites--> `Telemetry data parsing`  [INFERRED]
  COMPONENTS.md → src/omnicompute/telemetry/parser.py
- `Data model and schema specifications` --cites--> `Telemetry data schemas`  [INFERRED]
  DATA_SCHEMAS.md → src/omnicompute/telemetry/schemas.py
- `Component structure and responsibilities` --cites--> `Baseline computation and caching`  [INFERRED]
  COMPONENTS.md → src/omnicompute/anomaly/baseline.py
- `Data model and schema specifications` --cites--> `Anomaly detection data schemas`  [INFERRED]
  DATA_SCHEMAS.md → src/omnicompute/anomaly/schemas.py
- `Component structure and responsibilities` --cites--> `Anomaly triage and classification`  [INFERRED]
  COMPONENTS.md → src/omnicompute/anomaly/triager.py

## Import Cycles
- 1-file cycle: `src/omnicompute/anomaly/triager.py -> src/omnicompute/anomaly/triager.py`
- 1-file cycle: `src/omnicompute/telemetry/parser.py -> src/omnicompute/telemetry/parser.py`
- 1-file cycle: `src/omnicompute/telemetry/schemas.py -> src/omnicompute/telemetry/schemas.py`

## Hyperedges (group relationships)
- **** — telemetry_module_collection_pipeline, parser_telemetry_data_parsing, telemetry_schemas_data_structures [INFERRED 0.85]
- **** — anomaly_module_detection_pipeline, baseline_baseline_computation, triager_anomaly_classification, anomaly_schemas_anomaly_structures [INFERRED 0.85]

## Communities (28 total, 1 thin omitted)

### Community 0 - "BaselineCache / AnomalyTriager / Anomaly"
Cohesion: 0.06
Nodes (32): Anomaly, BaselineCache, BaselineCache: Manage 30-day rolling baseline statistics for metric anomaly dete, Cache for 30-day rolling baseline statistics (mean, stddev) per node+metric., Initialize baseline cache.          Args:             data: Dict with structure:, Retrieve baseline statistics for a node+metric.          Args:             node_, Calculate z-score for a metric value.          Args:             value: Current, Update baseline cache for a node (merge semantics).          Args:             n (+24 more)

### Community 1 - "errors.py / OmniComputeError / TelemetryParser"
Cohesion: 0.07
Nodes (34): Exception, AnomalyTriageError, BaselineError, BundleError, EncryptionError, ExecutionError, OmniComputeError, PlaybookError (+26 more)

### Community 2 - "conftest.py / BaselineCache / baseline_cache_empty()"
Cohesion: 0.05
Nodes (38): BaselineCache, baseline_cache_empty(), baseline_cache_normal(), baseline_missing_metric(), baseline_normal(), baseline_stale(), baseline_zero_stddev(), batch_empty() (+30 more)

### Community 3 - "test_baseline_cache.py / TestEdgeCases / TestGetBaseline"
Cohesion: 0.07
Nodes (19): Test suite for BaselineCache (TDD - tests written before implementation).  Targe, Returns a dict containing mean, stddev, and days_samples., Unknown node_id never raises; returns None., Known node but metric not tracked in baseline returns None., Graceful degradation and freshness signaling., A baseline entry with zero stddev does not raise on z_score()., An empty cache (no baselines loaded) never raises; .get() is None., A baseline with < 7 days of history is still usable for z_score,         but cal (+11 more)

### Community 4 - "_telemetry() / TestEdgeCases / TestSafeRangesIntegration"
Cohesion: 0.08
Nodes (21): Helper: build a Telemetry instance with fixed, deterministic timestamps., Telemetry with all metrics within nominal range (|z| <= 2.0 for Sat-01)., Telemetry with a CRITICAL battery anomaly (z-score > 3) for Sat-01.      mean=65, Telemetry with a WARNING thermal anomaly (2 < z-score <= 3) for Sat-01.      mea, Telemetry with a value outside safe_ranges even though z-score is low.      Sat-, _telemetry(), telemetry_critical_battery(), telemetry_normal_values() (+13 more)

### Community 5 - "test_anomaly_triager.py / TestBaselineCacheInteraction / TestNoAnomalies"
Cohesion: 0.07
Nodes (18): Test suite for AnomalyTriager (TDD - tests written before implementation).  Targ, WARNING is assigned for 2.0 < |z| <= 3.0 within safe ranges., thermal_temp_celsius=47.5, mean=35, stddev=5 -> z=2.5 -> WARNING., value=25, mean=35, stddev=5 -> z=-2.0... use -2.5 to land squarely         in WA, NOMINAL is assigned for |z| <= 2.0 within safe ranges., All metrics within 2 sigma of baseline -> NOMINAL., Value within safe_ranges and |z| exactly at boundary (2.0) is NOMINAL., How the triager consults BaselineCache for each metric. (+10 more)

### Community 6 - "Baseline computation and cachi / Telemetry data parsing / Anomaly triage and classificat"
Cohesion: 0.20
Nodes (16): Anomaly detection and triage pipeline, Anomaly detection data schemas, System architecture and design rationale, Baseline computation and caching, Component structure and responsibilities, Configuration management, Test fixtures and configuration, Data model and schema specifications (+8 more)

### Community 7 - "to_json_str() / TestCoercionAndFallbacks / .test_negative_metric_value_is"
Cohesion: 0.21
Nodes (8): Helper: serialize a fixture dict to a JSON string for parser input., to_json_str(), Invalid metric values must be safely coerced rather than crashing., A metric with a non-numeric string value coerces to 0.0., A metric with a None value coerces to 0.0., A very large float metric value is preserved, not clamped., A negative metric value (e.g. dBm signal strength) is preserved., TestCoercionAndFallbacks

### Community 8 - "Telemetry / .normalize_timestamps_to_utc() / schemas.py"
Cohesion: 0.22
Nodes (8): BaseModel, Any, datetime, Pydantic data models for telemetry., Normalize all timestamps to UTC-aware datetime objects., Coerce all metric values to float; use 0.0 for non-numeric., Normalized telemetry reading from a single node., Telemetry

### Community 9 - "TestConfidenceScoring / .test_stale_baseline_penalizes / .test_redundant_indicators_boo"
Cohesion: 0.20
Nodes (6): Confidence reflects baseline completeness, z-score strength, and     redundant i, A complete (>=7 day) baseline plus a strong z-score signal         should produc, A baseline with days_samples < 7 should yield lower confidence         than an e, When multiple metrics on the same node are simultaneously         anomalous (cor, No baseline available for the metric -> confidence in the         AMBIGUOUS rang, TestConfidenceScoring

### Community 10 - "TestZScoreCalculation / .test_z_score_negative_deviati / .test_z_score_positive_deviati"
Cohesion: 0.20
Nodes (6): `.z_score(value, baseline)` numeric contract., value=75, mean=65, stddev=5 -> z_score ~= 2.0., value=55, mean=65, stddev=5 -> z_score ~= -2.0., Zero stddev (no variance) must not raise ZeroDivisionError.          Contract: r, Value far from mean produces a correctly scaled large z-score., TestZScoreCalculation

### Community 11 - "TestSchemaValidation / .test_empty_metrics_dict_is_ac / .test_extra_unknown_fields_are"
Cohesion: 0.20
Nodes (6): A node reading with an empty metrics dict is valid (no metrics)., Unexpected extra keys in the JSON do not break parsing., Required-field validation and tolerance for non-essential fields., Record without node_id is skipped; the valid sibling record survives., Record without a usable timestamp is skipped and logged., TestSchemaValidation

### Community 12 - "TestEdgeCases / .test_batch_with_over_one_hund / .test_duplicate_node_id_in_sam"
Cohesion: 0.20
Nodes (6): Boundary conditions: empty lists, large batches, duplicates, overflow., A batch with node_readings: [] returns an empty result list., A batch with 100+ node readings parses every record, no truncation., Two readings sharing the same node_id are both kept (no dedup)., A metric value of 1e10 is accepted without overflow or error., TestEdgeCases

### Community 13 - "TestCriticalSeverity / .test_high_positive_z_score_is / .test_high_negative_z_score_is"
Cohesion: 0.25
Nodes (5): CRITICAL is assigned for |z| > 3.0 or safe_range violations., z-score > 3.0 (e.g., far above mean) -> CRITICAL., z-score < -3.0 -> CRITICAL. battery_soc_percent=14.2, mean=65,         stddev=8, A metric value outside safe_ranges is CRITICAL, overriding         whatever the, TestCriticalSeverity

### Community 14 - "TestUnitConversion / .test_battery_soc_percent_valu / .test_rf_signal_strength_dbm_i"
Cohesion: 0.25
Nodes (5): Metric values pass through with correct, realistic units., thermal_temp_celsius stays in Celsius (no spurious conversion)., battery_soc_percent is treated as a percent value (0-100 nominal)., rf_signal_strength_dbm falls within a realistic negative dBm range., TestUnitConversion

### Community 15 - "TestTimestampNormalization / .test_invalid_timestamp_format / .test_iso8601_timestamp_is_par"
Cohesion: 0.25
Nodes (5): Timestamps must normalize consistently to UTC., A standard ISO 8601 'Z' timestamp parses into a datetime field., A timestamp with a +00:00 offset normalizes to the same UTC instant         as t, An unparseable timestamp string causes the record to be skipped., TestTimestampNormalization

### Community 16 - "TestHappyPath / .test_parse_valid_multi_node_b / .test_parse_valid_single_node_"
Cohesion: 0.25
Nodes (5): Parsing well-formed batches should produce correct Telemetry objects., A batch with exactly one node reading yields exactly one Telemetry., A batch with 3 node readings yields 3 Telemetry objects, in order., node_id, timestamp, received_at, and metrics all reflect input data., TestHappyPath

### Community 17 - "test_telemetry_parser.py / TestIdempotence / .test_parsing_same_batch_twice"
Cohesion: 0.33
Nodes (4): Test suite for TelemetryParser (TDD - tests written before implementation).  Tar, Parsing the same input must always yield identical output., Calling parse() twice with the same JSON string is deterministic., TestIdempotence

### Community 18 - "TestMalformedJson / .test_empty_json_object_parses / .test_invalid_json_syntax_retu"
Cohesion: 0.33
Nodes (4): Top-level JSON parse failures must never raise out of parse()., Unparseable JSON text is caught; parse() returns [] without raising., A bare '{}' JSON object parses successfully to an empty list., TestMalformedJson

## Knowledge Gaps
- **5 isolated node(s):** `omnicompute package`, `Test fixtures and configuration`, `Telemetry parser unit tests`, `Baseline caching unit tests`, `Anomaly triager unit tests`
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `to_json_str()` connect `to_json_str() / TestCoercionAndFallbacks / .test_negative_metric_value_is` to `conftest.py / BaselineCache / baseline_cache_empty()`, `TestSchemaValidation / .test_empty_metrics_dict_is_ac / .test_extra_unknown_fields_are`, `TestEdgeCases / .test_batch_with_over_one_hund / .test_duplicate_node_id_in_sam`, `TestUnitConversion / .test_battery_soc_percent_valu / .test_rf_signal_strength_dbm_i`, `TestTimestampNormalization / .test_invalid_timestamp_format / .test_iso8601_timestamp_is_par`, `TestHappyPath / .test_parse_valid_multi_node_b / .test_parse_valid_single_node_`, `test_telemetry_parser.py / TestIdempotence / .test_parsing_same_batch_twice`, `TestMalformedJson / .test_empty_json_object_parses / .test_invalid_json_syntax_retu`?**
  _High betweenness centrality (0.311) - this node is a cross-community bridge._
- **Why does `BaselineCache` connect `BaselineCache / AnomalyTriager / Anomaly` to `errors.py / OmniComputeError / TelemetryParser`, `conftest.py / BaselineCache / baseline_cache_empty()`, `test_baseline_cache.py / TestEdgeCases / TestGetBaseline`, `_telemetry() / TestEdgeCases / TestSafeRangesIntegration`, `test_anomaly_triager.py / TestBaselineCacheInteraction / TestNoAnomalies`, `TestConfidenceScoring / .test_stale_baseline_penalizes / .test_redundant_indicators_boo`, `TestZScoreCalculation / .test_z_score_negative_deviati / .test_z_score_positive_deviati`, `TestCriticalSeverity / .test_high_positive_z_score_is / .test_high_negative_z_score_is`?**
  _High betweenness centrality (0.295) - this node is a cross-community bridge._
- **Why does `AnomalyTriager` connect `BaselineCache / AnomalyTriager / Anomaly` to `errors.py / OmniComputeError / TelemetryParser`, `conftest.py / BaselineCache / baseline_cache_empty()`, `_telemetry() / TestEdgeCases / TestSafeRangesIntegration`, `test_anomaly_triager.py / TestBaselineCacheInteraction / TestNoAnomalies`, `TestConfidenceScoring / .test_stale_baseline_penalizes / .test_redundant_indicators_boo`, `TestCriticalSeverity / .test_high_positive_z_score_is / .test_high_negative_z_score_is`?**
  _High betweenness centrality (0.280) - this node is a cross-community bridge._
- **Are the 22 inferred relationships involving `BaselineCache` (e.g. with `Anomaly` and `AnomalyTriager`) actually correct?**
  _`BaselineCache` has 22 INFERRED edges - model-reasoned connections that need verification._
- **Are the 20 inferred relationships involving `AnomalyTriager` (e.g. with `BaselineCache` and `Anomaly`) actually correct?**
  _`AnomalyTriager` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Are the 23 inferred relationships involving `to_json_str()` (e.g. with `.test_negative_metric_value_is_accepted_when_semantically_valid()` and `.test_none_metric_value_is_coerced_to_zero()`) actually correct?**
  _`to_json_str()` has 23 INFERRED edges - model-reasoned connections that need verification._
- **Are the 13 inferred relationships involving `_telemetry()` (e.g. with `.test_zero_stddev_baseline_handled_gracefully()` and `.test_redundant_indicators_boost_confidence()`) actually correct?**
  _`_telemetry()` has 13 INFERRED edges - model-reasoned connections that need verification._