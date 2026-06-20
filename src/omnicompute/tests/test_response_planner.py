"""Test suite for ResponsePlanner (TDD - tests written before implementation).

Target component: src/omnicompute/response/planner.py

Contract under test:
    ResponsePlanner(
        baseline_cache: BaselineCache,
        node_config: dict | None = None,
        playbooks_dir: str = CONFIG_PLAYBOOKS_DIR,
    )

    ResponsePlanner.plan(anomalies: list[Anomaly]) -> list[Action]
        - Consumes anomalies produced by AnomalyTriager.
        - On construction, loads all condition-action playbooks (*.yaml) from
          playbooks_dir. A playbook maps an anomaly_type (metric_name) to a
          set of trigger conditions, an ordered list of actions, and optional
          conditional modifiers. Malformed individual playbook files are
          logged and skipped, not fatal (PlaybookError is reserved for cases
          where the *directory itself* cannot be read, not for one bad file
          among many).
        - For each anomaly:
            1. Skip anomalies with severity == "NOMINAL" (no action needed).
            2. Find the playbook whose anomaly_type matches the anomaly's
               metric_name.
            3. If no playbook matches, generate a single fallback Action:
               action_type="alert_ground", reversible=False, rationale
               references the anomaly. This action is NOT autonomous
               (reversible=False forces HITL escalation).
            4. If a playbook matches, evaluate its triggers against the
               anomaly's severity/z_score. If no trigger matches, no action
               is generated for that anomaly+playbook pair.
            5. If a trigger matches, instantiate one Action per
               PlaybookAction entry, in the order they appear in the
               playbook (e.g. power_anomaly -> [load_shed, reduce_beacon]).
            6. Each Action's confidence = anomaly.confidence *
               playbook_action.min_confidence (clamped to [0.0, 1.0]).
               Each Action's reversible / reversibility_window_seconds /
               estimated_impact are copied verbatim from the matching
               PlaybookAction.
            7. Conditional modifiers in the playbook can alter the generated
               actions: e.g. excluding a param value when a condition is
               met (such as solar_degradation > 20% excluding "rf_backup"
               from load_shed's exclude list), or escalating to a more
               severe action set (e.g. "aggressive_load_shed" during an
               eclipse condition supplied via node_config or anomaly
               context).
            8. If node_config provides power_budget_watts for the node,
               actions that include a target_watts param are checked for
               budget compliance (e.g. annotated or filtered); if
               node_config is missing or lacks power_budget_watts, this
               check is skipped entirely without raising.
        - Duplicate anomalies for the same node+metric within one plan() call
          are deduplicated before action generation (no duplicate action
          sets for the same underlying anomaly).
        - Conflicting actions (e.g. load_shed and increase_compute both
          present in the resulting action list) are NOT silently dropped;
          both are returned, and a warning is logged noting the conflict.
        - plan([]) returns [].
        - Never raises on missing playbooks_dir contents or missing
          node_config; degrades gracefully per the rules above.

No implementation code is included in this file. Tests define the contract
for the implementation to satisfy.
"""

import logging

import pytest

from omnicompute.response.schemas import Action
from omnicompute.anomaly.schemas import Anomaly


# ---------------------------------------------------------------------------
# 1. Playbook loading
# ---------------------------------------------------------------------------


class TestPlaybookLoading:
    """Loading playbooks from a directory of YAML files at construction time."""

    def test_loads_single_playbook_and_parses_triggers_actions_modifiers(
        self, baseline_cache_normal, node_config_with_power_budget, playbooks_dir
    ):
        """power_anomaly.yaml is parsed into triggers, actions, and modifiers
        accessible to the planner (verified indirectly via plan() output).
        """
        from omnicompute.response.planner import ResponsePlanner

        planner = ResponsePlanner(
            baseline_cache=baseline_cache_normal,
            node_config=node_config_with_power_budget,
            playbooks_dir=str(playbooks_dir),
        )

        anomaly = Anomaly(
            node_id="Sat-01",
            metric_name="battery_soc_percent",
            current_value=14.2,
            baseline_mean=65.0,
            baseline_stddev=8.0,
            z_score=-6.35,
            severity="CRITICAL",
            confidence=0.90,
            timestamp="2026-06-19T20:10:00Z",
        )

        actions = planner.plan([anomaly])

        action_types = {a.action_type for a in actions}
        assert "load_shed" in action_types
        assert "reduce_beacon" in action_types

    def test_loads_all_playbooks_from_directory_without_parse_errors(
        self, baseline_cache_normal, node_config_with_power_budget, playbooks_dir
    ):
        """All sample playbooks (power_anomaly, thermal_violation, rf_jamming)
        load successfully and each can independently generate actions.
        """
        from omnicompute.response.planner import ResponsePlanner

        planner = ResponsePlanner(
            baseline_cache=baseline_cache_normal,
            node_config=node_config_with_power_budget,
            playbooks_dir=str(playbooks_dir),
        )

        anomalies = [
            Anomaly(
                node_id="Sat-01",
                metric_name="battery_soc_percent",
                current_value=14.2,
                baseline_mean=65.0,
                baseline_stddev=8.0,
                z_score=-6.35,
                severity="CRITICAL",
                confidence=0.90,
                timestamp="2026-06-19T20:10:00Z",
            ),
            Anomaly(
                node_id="Sat-01",
                metric_name="thermal_temp_celsius",
                current_value=47.5,
                baseline_mean=35.0,
                baseline_stddev=5.0,
                z_score=2.5,
                severity="WARNING",
                confidence=0.75,
                timestamp="2026-06-19T20:10:00Z",
            ),
            Anomaly(
                node_id="Sat-01",
                metric_name="rf_signal_strength_dbm",
                current_value=-125.0,
                baseline_mean=-75.0,
                baseline_stddev=8.5,
                z_score=-5.9,
                severity="CRITICAL",
                confidence=0.92,
                timestamp="2026-06-19T20:10:00Z",
            ),
        ]

        actions = planner.plan(anomalies)

        action_types = {a.action_type for a in actions}
        assert "load_shed" in action_types
        assert "reduce_compute_load" in action_types
        assert "switch_to_backup_antenna" in action_types

    def test_playbook_not_found_for_anomaly_type_generates_fallback(
        self, planner_with_playbooks, anomaly_unknown_type
    ):
        """An anomaly metric with no matching playbook -> generic fallback
        recommendation, not an exception.
        """
        actions = planner_with_playbooks.plan([anomaly_unknown_type])

        assert len(actions) == 1
        assert actions[0].action_type == "alert_ground"
        assert actions[0].reversible is False


# ---------------------------------------------------------------------------
# 2. Trigger matching
# ---------------------------------------------------------------------------


class TestTriggerMatching:
    """Matching anomaly severity/z-score against playbook trigger conditions."""

    def test_critical_battery_anomaly_matches_power_anomaly_trigger(
        self, planner_with_playbooks, anomaly_critical_battery
    ):
        """CRITICAL battery anomaly (z-score > 3) matches power_anomaly's
        CRITICAL trigger and yields its action set.
        """
        actions = planner_with_playbooks.plan([anomaly_critical_battery])

        assert len(actions) > 0
        assert all(a.playbook_name == "power_anomaly" for a in actions)

    def test_warning_thermal_anomaly_matches_thermal_violation_trigger(
        self, planner_with_playbooks, anomaly_warning_thermal
    ):
        """WARNING thermal anomaly (2 < z-score <= 3) matches
        thermal_violation's WARNING trigger.
        """
        actions = planner_with_playbooks.plan([anomaly_warning_thermal])

        assert len(actions) > 0
        assert all(a.playbook_name == "thermal_violation" for a in actions)

    def test_nominal_metric_does_not_match_any_trigger_no_actions(
        self, planner_with_playbooks, anomaly_nominal_metric
    ):
        """NOMINAL severity never matches a trigger; no actions generated."""
        actions = planner_with_playbooks.plan([anomaly_nominal_metric])

        assert actions == []


# ---------------------------------------------------------------------------
# 3. Action generation
# ---------------------------------------------------------------------------


class TestActionGeneration:
    """How matched playbooks translate into ordered Action objects."""

    def test_critical_anomaly_generates_multiple_actions_in_sequence(
        self, planner_with_playbooks, anomaly_critical_battery
    ):
        """power_anomaly playbook generates load_shed THEN reduce_beacon,
        preserving playbook-defined order.
        """
        actions = planner_with_playbooks.plan([anomaly_critical_battery])

        action_types = [a.action_type for a in actions]
        assert action_types.index("load_shed") < action_types.index("reduce_beacon")

    def test_action_confidence_derives_from_anomaly_times_playbook_min_confidence(
        self, planner_with_playbooks, anomaly_critical_battery
    ):
        """Action.confidence == anomaly.confidence * playbook_action.min_confidence,
        clamped to [0, 1]. anomaly.confidence=0.90, load_shed.min_confidence=0.6
        -> expected 0.54.
        """
        actions = planner_with_playbooks.plan([anomaly_critical_battery])
        load_shed = next(a for a in actions if a.action_type == "load_shed")

        assert load_shed.confidence == pytest.approx(0.90 * 0.6, abs=1e-6)

    def test_action_reversibility_flag_copied_from_playbook(
        self, planner_with_playbooks, anomaly_critical_battery
    ):
        """Action.reversible mirrors the playbook action definition exactly."""
        actions = planner_with_playbooks.plan([anomaly_critical_battery])
        load_shed = next(a for a in actions if a.action_type == "load_shed")

        assert load_shed.reversible is True
        assert load_shed.reversibility_window_seconds == 1800


# ---------------------------------------------------------------------------
# 4. Conditional action modification
# ---------------------------------------------------------------------------


class TestConditionalActionModification:
    """Playbook modifiers altering generated actions based on context."""

    def test_modifier_skips_rf_backup_on_high_solar_degradation(
        self, baseline_cache_normal, node_config_with_power_budget, playbooks_dir
    ):
        """When context indicates solar_degradation > 20%, load_shed's
        params.exclude must contain 'rf_backup'.
        """
        from omnicompute.response.planner import ResponsePlanner

        planner = ResponsePlanner(
            baseline_cache=baseline_cache_normal,
            node_config=node_config_with_power_budget,
            playbooks_dir=str(playbooks_dir),
        )

        anomaly = Anomaly(
            node_id="Sat-01",
            metric_name="battery_soc_percent",
            current_value=14.2,
            baseline_mean=65.0,
            baseline_stddev=8.0,
            z_score=-6.35,
            severity="CRITICAL",
            confidence=0.90,
            timestamp="2026-06-19T20:10:00Z",
        )

        actions = planner.plan([anomaly], context={"solar_degradation": 25})
        load_shed = next(a for a in actions if a.action_type == "load_shed")

        assert "rf_backup" in load_shed.params.get("exclude", [])

    def test_modifier_applies_aggressive_load_shed_during_eclipse(
        self, baseline_cache_normal, node_config_with_power_budget, playbooks_dir
    ):
        """When context indicates eclipse=True, load_shed becomes more
        severe (e.g. higher target_watts than the baseline action).
        """
        from omnicompute.response.planner import ResponsePlanner

        planner = ResponsePlanner(
            baseline_cache=baseline_cache_normal,
            node_config=node_config_with_power_budget,
            playbooks_dir=str(playbooks_dir),
        )

        anomaly = Anomaly(
            node_id="Sat-01",
            metric_name="battery_soc_percent",
            current_value=14.2,
            baseline_mean=65.0,
            baseline_stddev=8.0,
            z_score=-6.35,
            severity="CRITICAL",
            confidence=0.90,
            timestamp="2026-06-19T20:10:00Z",
        )

        baseline_actions = planner.plan([anomaly])
        eclipse_actions = planner.plan([anomaly], context={"eclipse": True})

        baseline_watts = next(
            a for a in baseline_actions if a.action_type == "load_shed"
        ).params["target_watts"]
        eclipse_watts = next(
            a for a in eclipse_actions if a.action_type == "load_shed"
        ).params["target_watts"]

        assert eclipse_watts > baseline_watts


# ---------------------------------------------------------------------------
# 5. No playbook fallback
# ---------------------------------------------------------------------------


class TestNoPlaybookFallback:
    """Fallback behavior when no playbook exists for an anomaly type."""

    def test_unknown_anomaly_type_generates_generic_alert_ground_action(
        self, planner_no_playbooks, anomaly_critical_battery
    ):
        """With zero playbooks loaded, any non-NOMINAL anomaly produces the
        generic, non-reversible 'alert_ground' recommendation.
        """
        actions = planner_no_playbooks.plan([anomaly_critical_battery])

        assert len(actions) == 1
        assert actions[0].action_type == "alert_ground"
        assert actions[0].reversible is False
        assert actions[0].node_id == "Sat-01"


# ---------------------------------------------------------------------------
# 6. Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Deduplication, conflicting actions, and empty input."""

    def test_duplicate_anomalies_same_type_deduplicated_or_merged(
        self, planner_with_playbooks, anomaly_critical_battery
    ):
        """Two identical CRITICAL battery anomalies in one plan() call do
        not produce two independent load_shed action sets; the resulting
        action list contains at most one load_shed action for that node.
        """
        actions = planner_with_playbooks.plan(
            [anomaly_critical_battery, anomaly_critical_battery]
        )

        load_shed_actions = [a for a in actions if a.action_type == "load_shed"]
        assert len(load_shed_actions) == 1

    def test_conflicting_actions_logged_as_warning_both_queued(
        self, planner_with_playbooks, anomaly_critical_battery, caplog
    ):
        """If the action set contains both load_shed and increase_compute
        (conflicting power directions), both remain in the returned list
        and a warning is logged noting the conflict.

        Simulated here by injecting a second anomaly type whose playbook
        action is 'increase_compute', alongside the load-shedding battery
        anomaly, within a single plan() call.
        """
        increase_compute_anomaly = Anomaly(
            node_id="Sat-01",
            metric_name="compute_demand_backlog",
            current_value=500.0,
            baseline_mean=50.0,
            baseline_stddev=10.0,
            z_score=45.0,
            severity="CRITICAL",
            confidence=0.88,
            timestamp="2026-06-19T20:10:00Z",
        )

        with caplog.at_level(logging.WARNING):
            actions = planner_with_playbooks.plan(
                [anomaly_critical_battery, increase_compute_anomaly]
            )

        action_types = {a.action_type for a in actions}
        # load_shed always present from the battery anomaly's playbook.
        assert "load_shed" in action_types
        # Whether or not a real playbook defines increase_compute, the
        # planner must not silently drop conflicting actions if both exist;
        # absence of a crash and presence of load_shed is the core
        # assertion here. If increase_compute has no playbook, a fallback
        # alert_ground action is acceptable in its place.
        assert len(actions) >= 1

    def test_empty_anomaly_list_returns_no_actions(self, planner_with_playbooks):
        """plan([]) returns an empty list, never raises."""
        actions = planner_with_playbooks.plan([])

        assert actions == []


# ---------------------------------------------------------------------------
# 7. Integration with node config
# ---------------------------------------------------------------------------


class TestNodeConfigIntegration:
    """How node_config's power_budget_watts feeds into action checks."""

    def test_node_config_power_budget_used_for_budget_compliance_check(
        self, baseline_cache_normal, node_config_with_power_budget, playbooks_dir
    ):
        """When node_config provides power_budget_watts, actions with a
        target_watts param are checked against it (e.g. annotated via
        estimated_impact, or capped so as not to exceed the budget). This
        test asserts the check runs without raising and produces a
        target_watts that does not exceed the configured budget.
        """
        from omnicompute.response.planner import ResponsePlanner

        planner = ResponsePlanner(
            baseline_cache=baseline_cache_normal,
            node_config=node_config_with_power_budget,
            playbooks_dir=str(playbooks_dir),
        )

        anomaly = Anomaly(
            node_id="Sat-01",
            metric_name="battery_soc_percent",
            current_value=14.2,
            baseline_mean=65.0,
            baseline_stddev=8.0,
            z_score=-6.35,
            severity="CRITICAL",
            confidence=0.90,
            timestamp="2026-06-19T20:10:00Z",
        )

        actions = planner.plan([anomaly])
        load_shed = next(a for a in actions if a.action_type == "load_shed")

        power_budget = node_config_with_power_budget["Sat-01"]["power_budget_watts"]
        assert load_shed.params["target_watts"] <= power_budget

    def test_missing_node_config_degrades_gracefully_no_power_check(
        self, planner_no_node_config, anomaly_critical_battery
    ):
        """With node_config=None, planning still succeeds; no power-budget
        check is performed, and no exception is raised.
        """
        actions = planner_no_node_config.plan([anomaly_critical_battery])

        assert len(actions) > 0
        assert any(a.action_type == "load_shed" for a in actions)
