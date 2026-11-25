"""Behavior tests with synthetic agent responses. No model account or actual model is used."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/council_run.py"
spec = importlib.util.spec_from_file_location("council_run", SCRIPT)
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


def request(profile="balanced", kind="architecture", binding="tool-model"):
    req = {key: "Fictional " + key for key in c.FIELDS}
    req.update({"analysis_type": kind, "framing_reply": "Use the displayed scope and Balanced roster.",
                "binding": {"mode": binding, "host": "synthetic-test", "verified_by": "test double, not live execution", "grounding_tools": ["read", "search"], "supports_effort": True},
                "model_selection": {"profile": profile, "confirmed": True, "checked_at": "2026-10-10", "availability_source": "synthetic test catalog",
                                    "catalog": [{"model": name, "efforts": ["deep"]} for name in ("Reader-X", "Worker-Y", "Reasoner-Z", "Alternative-W")],
                                    "roles": {"grounding": {"model": "Reader-X"}, "workers": {"model": "Worker-Y"}, "outflanker": {"model": "Reasoner-Z"}, "chair": {"model": "Reasoner-Z"}}}})
    return req


def output(role):
    if role == "grounding":
        return {"is_clarification": False, "brief": "A fictional migration has three known constraints.", "facts": [
            {"fact": "FACT_SENTINEL_" + str(i), "source": "SOURCE_SENTINEL_" + str(i), "status": "VERIFIED", "as_of": "2026-10-10"} for i in (1, 2, 3)]}
    if role == "outflanker":
        return {key: "Outflanker " + key for key in ("shared_blind_spot", "strongest_attack", "evidence", "falsification", "reframe", "survives")} | {"sources": [1, 3]}
    if role == "chair":
        return {"verdict_short": "Gather missing evidence first.", "confidence": "medium", "sources": [1, 2],
                "brief": {"one_line": "Check before migrating.", "premise": "This is a fictional migration.", "walkthrough": "Hypothetical illustration: an item goes from A to B."},
                "mechanism": "If operational constraints are not met, the migration may lose required behavior.",
                "frame_break": "The framing holds.", "gap": "Operational uncertainty.", "verdict": "Delay the migration until the missing operational checks have established the necessary conditions.",
                "forced_dissent": {"strongest": "Evidence for A.", "weakest": "Unsupported B.", "overlooked_conflict": "Conflict C."}, "off_scope": []}
    return {"lens": role, "found": True, "claim": "CLAIM_SENTINEL_" + role, "confidence": "medium", "sources": [1, 2], "core_frame": "Limited assumption.", "if_then": "If A, then B.", "blind_spot": "Unobserved condition C."}


def envelope(job, result=None):
    return {"execution": {"call_id": job["role"] + "-" + str(job["attempt"]), "binding_mode": job["binding_mode"],
                          "requested_model": job["model"], "requested_effort": job.get("effort"), "agent_name": job.get("agent_name")},
            "output": output(job["role"]) if result is None else result}


class RunTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="council-test-")
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def init(self, req=None):
        return Path(c.initialize(self.root, req or request())["run"])

    def jobs(self, run):
        state = c.load(run)
        return c.next_step(run, state, c.phase(state)[1] or None)["jobs"]

    def ground(self, run):
        result = c.submit(run, "grounding", envelope(self.jobs(run)[0]))
        self.assertTrue(result["accepted"])
        return result

    def approve(self, run):
        state = c.load(run)
        return c.approve(run, state["factbase_digest"], "I reviewed these exact facts; continue.")

    def through_workers(self, run):
        self.ground(run); self.approve(run)
        for job in self.jobs(run):
            self.assertTrue(c.submit(run, job["role"], envelope(job))["accepted"])

    def finish(self, run):
        self.through_workers(run)
        for _ in range(2):
            job = self.jobs(run)[0]
            self.assertTrue(c.submit(run, job["role"], envelope(job))["accepted"])

    def test_all_profiles_keep_seven_roles(self):
        for profile in ("economy", "balanced", "thorough", "custom"):
            with self.subTest(profile=profile):
                run = self.init(request(profile=profile)); self.finish(run)
                state = c.load(run)
                self.assertEqual(c.phase(state)[0], "complete")
                self.assertEqual(len(state["receipts"]), 7)
                self.assertEqual(len({r["execution"]["call_id"] for r in state["receipts"]}), 7)
                self.assertIn("Workers: 4/4 returned", (run / "report.md").read_text())

    def test_compact_status_and_selective_fetch_preserve_dispatch_guards(self):
        run = self.init()
        summary = c.next_step(run, c.load(run))
        self.assertNotIn('prompt', summary['jobs'][0])
        with self.assertRaises(c.Invalid):
            c.next_step(run, c.load(run), ['chair'])
        self.ground(run)
        with self.assertRaises(c.Invalid):
            c.next_step(run, c.load(run), ['failure_first'])
        self.approve(run)
        selected = ['failure_first', 'subtraction']
        jobs = c.next_step(run, c.load(run), selected)['jobs']
        self.assertEqual([job['role'] for job in jobs], selected)
        for job in jobs:
            for i in (1, 2, 3):
                self.assertIn('FACT_SENTINEL_' + str(i), job['prompt'])
                self.assertIn('SOURCE_SENTINEL_' + str(i), job['prompt'])
        result = c.submit(run, jobs[0]['role'], envelope(jobs[0]))
        self.assertTrue(all('prompt' not in job for job in result['jobs']))
        with self.assertRaises(c.Invalid):
            c.next_step(run, c.load(run), ['failure_first'])
        with self.assertRaises(c.Invalid):
            c.next_step(run, c.load(run), ['subtraction', 'subtraction'])

    def test_all_lenses_and_individual_override(self):
        for kind in c.LENSES:
            with self.subTest(kind=kind):
                req = request(kind=kind)
                lens = list(c.LENSES[kind])[2]
                req["model_selection"]["worker_overrides"] = {lens: {"model": "Alternative-W"}}
                run = self.init(req); self.ground(run); self.approve(run)
                jobs = self.jobs(run)
                self.assertEqual([j["role"] for j in jobs], list(c.LENSES[kind]))
                self.assertEqual(jobs[2]["model"], "Alternative-W")
                self.assertTrue(all("CLAIM_SENTINEL" not in j["prompt"] for j in jobs))

    def test_invalid_choice_creates_no_run(self):
        cases = [lambda r: r["model_selection"].update(confirmed=False),
                 lambda r: r["model_selection"]["roles"]["chair"].update(model="unavailable"),
                 lambda r: r["model_selection"]["roles"]["chair"].update(effort="unsupported"),
                 lambda r: r.update(framing_reply=""),
                 lambda r: r["binding"].update(verified_by="")]
        for change in cases:
            req = request(); change(req)
            with self.assertRaises(c.Invalid):
                self.init(req)
        self.assertFalse((self.root / "runs").exists())

    def test_auto_catalog_ok_but_auto_assignment_rejected(self):
        req = request(); req["model_selection"]["catalog"].append({"model": "Auto"})
        self.assertEqual(len(c.roster(req)), 7)
        req["model_selection"]["roles"]["chair"]["model"] = "Auto"
        with self.assertRaises(c.Invalid): c.roster(req)

    def test_one_model_still_seven_calls(self):
        req = request()
        for role in req["model_selection"]["roles"]: req["model_selection"]["roles"][role] = {"model": "Reader-X"}
        run = self.init(req); self.finish(run)
        self.assertTrue(all(r["requested"]["model"] == "Reader-X" for r in c.load(run)["receipts"]))

    def test_fact_review_blocks_workers_and_binds_digest(self):
        run = self.init(); result = self.ground(run)
        self.assertEqual(result["status"], "awaiting-fact-review")
        self.assertEqual(self.jobs(run), [])
        with self.assertRaises(c.Invalid): c.approve(run, "wrong", "yes")
        with self.assertRaises(c.Invalid): c.approve(run, result["digest"], "")
        with self.assertRaises(c.Invalid): c.submit(run, "chair", {})
        self.assertEqual(len(self.approve(run)["jobs"]), 4)

    def test_runner_writes_exact_factbase_without_wrote_file_claim(self):
        run = self.init(); self.ground(run)
        state = c.load(run)
        self.assertEqual(c.read_json(run / "factbase.json"), state["results"]["grounding"])
        self.assertEqual(c.digest(run / "factbase.json"), state["factbase_digest"])
        self.assertIn("SOURCE_SENTINEL_3", (run / "factbase.md").read_text())

    def test_changed_displayed_or_machine_factbase_is_rejected(self):
        for name in ("factbase.json", "factbase.md"):
            run = self.init(); self.ground(run)
            (run / name).write_text("changed")
            with self.assertRaises(c.Invalid): c.load(run)

    def test_changed_saved_report_cannot_be_claimed_complete(self):
        run = self.init(); self.finish(run)
        (run / "report.md").write_text("Truncated or externally changed report")
        with self.assertRaises(c.Invalid): c.load(run)

    def test_one_user_revision_retains_upstream_and_original_report(self):
        run = self.init(); self.finish(run)
        before = c.load(run)
        result = c.revise(run, "Explain the trigger more clearly.")
        self.assertEqual([job["role"] for job in result["jobs"]], ["chair"])
        self.assertIn("Explain the trigger more clearly.", result["jobs"][0]["prompt"])
        self.assertEqual(len(c.load(run)["results"]), 6)
        self.assertIn("Status: **complete**", (run / "history/report-before-revision.md").read_text())
        self.assertEqual(c.submit(run, "chair", envelope(result["jobs"][0]))["status"], "complete")
        after = c.load(run)
        self.assertEqual(after["results"]["outflanker"], before["results"]["outflanker"])
        self.assertEqual(len(after["receipts"]), 8)
        with self.assertRaises(c.Invalid): c.revise(run, "A second revision")

    def test_revision_after_validation_retry_has_one_attempt(self):
        run = self.init(); self.through_workers(run)
        c.submit(run, "outflanker", envelope(self.jobs(run)[0]))
        invalid = output("chair"); invalid["mechanism"] = "short"
        c.submit(run, "chair", envelope(self.jobs(run)[0], invalid)); c.retry(run, "chair")
        c.submit(run, "chair", envelope(self.jobs(run)[0]))
        revised = c.revise(run, "Reconsider the conclusion.")["jobs"][0]
        self.assertEqual(revised["attempt"], 3)
        self.assertEqual(c.submit(run, "chair", envelope(revised, invalid))["status"], "failed")
        with self.assertRaises(c.Invalid): c.retry(run, "chair")

    def test_weak_worker_evidence_is_explicitly_signaled_to_chair(self):
        run = self.init(); self.ground(run); self.approve(run)
        for job in self.jobs(run):
            data = output(job["role"]); data["confidence"] = "low"
            c.submit(run, job["role"], envelope(job, data))
        c.submit(run, "outflanker", envelope(self.jobs(run)[0]))
        self.assertIn("EVIDENCE SIGNAL", self.jobs(run)[0]["prompt"])

    def test_empty_duplicate_or_insufficient_facts_fail(self):
        for kind in ("empty", "duplicate", "two", "clarification"):
            run = self.init(); job = self.jobs(run)[0]; data = output("grounding")
            if kind == "empty": data["facts"][0]["fact"] = " "
            if kind == "duplicate": data["facts"][1] = dict(data["facts"][0])
            if kind == "two": data["facts"] = data["facts"][:2]
            if kind == "clarification": data["is_clarification"] = True
            result = c.submit(run, "grounding", envelope(job, data))
            self.assertFalse(result["accepted"])
            self.assertEqual(result["status"], "failed")
            self.assertFalse((run / "factbase.json").exists())

    def test_missing_workers_never_look_good(self):
        run = self.init(); self.ground(run); self.approve(run)
        jobs = self.jobs(run)
        c.submit(run, jobs[0]["role"], envelope(jobs[0]))
        report = (run / "report.md").read_text()
        self.assertIn("Workers: 1/4 returned · quality: INCOMPLETE", report)
        self.assertNotIn("quality: GOOD", report)

    def test_parallel_siblings_can_be_recorded_after_one_fails(self):
        run = self.init(); self.ground(run); self.approve(run); jobs = self.jobs(run)
        bad = envelope(jobs[0]); bad["output"] = None
        c.submit(run, jobs[0]["role"], bad)
        for job in jobs[1:]: self.assertTrue(c.submit(run, job["role"], envelope(job))["accepted"])
        state = c.load(run)
        self.assertEqual(c.phase(state)[0], "failed")
        self.assertEqual(len(state["results"]), 4)
        self.assertIn("Workers: 3/4 returned · quality: INCOMPLETE", (run / "report.md").read_text())

    def test_outflanker_and_chair_receive_all_sources(self):
        run = self.init(); self.through_workers(run)
        job = self.jobs(run)[0]
        self.assertIn("SOURCE_SENTINEL_3", job["prompt"])
        self.assertIn('"sources": [', job["prompt"])
        c.submit(run, "outflanker", envelope(job))
        chair = self.jobs(run)[0]
        for phrase in ("SOURCE_SENTINEL_3", "FACT_SENTINEL_1", "CLAIM_SENTINEL_prior_art", '"sources": [', "OUTFLANKER"):
            self.assertIn(phrase, chair["prompt"])

    def test_unknown_fact_reference_rejected(self):
        run = self.init(); self.ground(run); self.approve(run); job = self.jobs(run)[0]
        data = output(job["role"]); data["sources"] = [999]
        self.assertFalse(c.submit(run, job["role"], envelope(job, data))["accepted"])

    def test_missing_outflanker_stops_chair(self):
        run = self.init(); self.through_workers(run); job = self.jobs(run)[0]
        response = envelope(job); response["output"] = None
        result = c.submit(run, "outflanker", response)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["jobs"], [])
        self.assertNotIn("chair", c.load(run)["results"])

    def test_two_invalid_chairs_never_complete(self):
        run = self.init(); self.through_workers(run)
        job = self.jobs(run)[0]; c.submit(run, "outflanker", envelope(job))
        first = self.jobs(run)[0]; data = output("chair"); data["mechanism"] = "short"
        c.submit(run, "chair", envelope(first, data)); c.retry(run, "chair")
        second = self.jobs(run)[0]
        self.assertEqual(first["model"], second["model"])
        self.assertEqual(second["attempt"], 2)
        self.assertEqual(c.submit(run, "chair", envelope(second, data))["status"], "failed")
        with self.assertRaises(c.Invalid): c.retry(run, "chair")
        self.assertIn("does not contain a completed council verdict", (run / "report.md").read_text())

    def test_completed_roles_not_rerun_on_worker_replacement(self):
        run = self.init(); self.ground(run); self.approve(run); jobs = self.jobs(run)
        for job in jobs[:3]: c.submit(run, job["role"], envelope(job))
        failed = jobs[3]; response = envelope(failed); response["error"] = "Model unavailable"; response["output"] = None
        c.submit(run, failed["role"], response)
        changed = copy.deepcopy(c.load(run)["request"]["model_selection"])
        changed["worker_overrides"] = {failed["role"]: {"model": "Alternative-W"}}
        with self.assertRaises(c.Invalid): c.retry(run, failed["role"], changed, "")
        new = c.retry(run, failed["role"], changed, "Use Alternative-W for the failed worker.")
        self.assertEqual(len(new["jobs"]), 1)
        self.assertEqual(new["jobs"][0]["model"], "Alternative-W")
        self.assertEqual(len(c.load(run)["results"]), 4)

    def test_silent_model_fallback_and_reused_call_id_rejected(self):
        for kind in ("requested", "observed", "call"):
            run = self.init(); self.ground(run); self.approve(run); job = self.jobs(run)[0]
            response = envelope(job)
            if kind == "requested": response["execution"]["requested_model"] = "wrong"
            if kind == "observed": response["execution"].update(observed_model="wrong", model_evidence="host test metadata")
            if kind == "call": response["execution"]["call_id"] = "grounding-1"
            self.assertFalse(c.submit(run, job["role"], response)["accepted"])

    def test_custom_agents_have_exact_models_and_no_analysis_tools(self):
        run = self.init(request(binding="custom-agent"))
        result = c.export_agents(run, self.root / "agents")
        self.assertEqual(len(result["files"]), 7)
        for filename in result["files"]:
            body = Path(filename).read_text()
            self.assertIn('model: "', body)
            self.assertIn("agents: []", body)
            if "-grounding-" not in filename: self.assertIn("tools: []", body)
        self.finish(run)
        removed = c.clean_agents(run)
        self.assertEqual(len(removed["removed"]), 7)
        self.assertEqual(c.phase(c.load(run))[0], "complete")

    def test_custom_binding_must_exist_and_match(self):
        for mode in ("missing", "changed"):
            run = self.init(request(binding="custom-agent"))
            if mode == "changed":
                files = c.export_agents(run, self.root / "agents")["files"]
                Path(next(p for p in files if "-grounding-" in p)).write_text("changed")
            self.assertFalse(c.submit(run, "grounding", envelope(self.jobs(run)[0]))["accepted"])

    def test_custom_agent_effort_is_not_faked(self):
        req = request(binding="custom-agent"); req["model_selection"]["roles"]["chair"]["effort"] = "deep"
        with self.assertRaises(c.Invalid): self.init(req)

    def test_tool_model_effort_requires_explicit_capability(self):
        req = request(); req["model_selection"]["roles"]["workers"]["effort"] = "deep"
        for value in (None, False):
            req["binding"]["supports_effort"] = value
            with self.assertRaisesRegex(c.Invalid, "supports_effort"):
                c.roster(req)
        req["binding"]["supports_effort"] = True
        self.assertEqual(c.roster(req)["prior_art"]["effort"], "deep")

    def test_no_finding_workers_complete_without_invented_claim_metadata(self):
        for positive_count in (0, 2):
            with self.subTest(positive_count=positive_count):
                run = self.init(); self.ground(run); self.approve(run)
                for index, job in enumerate(self.jobs(run)):
                    data = output(job["role"]) if index < positive_count else {
                        "lens": job["role"], "found": False,
                        "reason": "The supplied evidence does not establish a finding for this lens."}
                    self.assertTrue(c.submit(run, job["role"], envelope(job, data))["accepted"])
                    saved = c.read_json(run / "responses" / (job["role"] + "-1.json"))
                    self.assertEqual(saved["output"], data)
                    if not data["found"]:
                        result = c.load(run)["results"][job["role"]]
                        self.assertNotIn("confidence", result)
                        self.assertNotIn("claim", result)
                c.submit(run, "outflanker", envelope(self.jobs(run)[0]))
                chair = self.jobs(run)[0]
                self.assertEqual("EVIDENCE SIGNAL" in chair["prompt"], positive_count == 0)
                self.assertEqual(c.submit(run, "chair", envelope(chair))["status"], "complete")
                self.assertIn("Workers: 4/4 returned", (run / "report.md").read_text())

    def test_no_finding_still_rejects_claims_missing_reason_and_bad_sources(self):
        for extra in ({"claim": "A hidden positive finding"}, {"reason": " "}, {"sources": [999]}):
            run = self.init(); self.ground(run); self.approve(run); job = self.jobs(run)[0]
            data = {"lens": job["role"], "found": False, "reason": "No supported finding.", **extra}
            self.assertFalse(c.submit(run, job["role"], envelope(job, data))["accepted"])
            self.assertEqual(c.phase(c.load(run))[0], "failed")

    def test_grounding_summary_is_retained_for_review_but_not_analysis(self):
        req = self.source_request(); run = self.init(req)
        data = self.grounded_sources(req)
        data["brief"] = "PREMATURE_VERDICT_SENTINEL: choose the proposed option now."
        data["source_coverage"][1].update(status="partial", detail="Comments not accessible.")
        result = c.submit(run, "grounding", envelope(self.jobs(run)[0], data))
        self.assertIn("PREMATURE_VERDICT_SENTINEL", result["brief"])
        self.assertIn("PREMATURE_VERDICT_SENTINEL", (run / "factbase.md").read_text())
        self.approve(run)
        for job in self.jobs(run):
            self.assertNotIn("PREMATURE_VERDICT_SENTINEL", job["prompt"])
            self.assertIn("SOURCE_SENTINEL_3", job["prompt"])
            self.assertIn("Comments not accessible.", job["prompt"])
            c.submit(run, job["role"], envelope(job))
        for _ in range(2):
            job = self.jobs(run)[0]
            self.assertNotIn("PREMATURE_VERDICT_SENTINEL", job["prompt"])
            self.assertIn("FACT_SENTINEL_1", job["prompt"])
            self.assertIn("Comments not accessible.", job["prompt"])
            c.submit(run, job["role"], envelope(job))
        self.assertEqual(c.phase(c.load(run))[0], "complete")

    def test_readonly_next_and_persistent_reopen(self):
        run = self.init(); self.ground(run); before = (run / "state.json").read_bytes()
        c.next_step(run, c.load(run))
        self.assertEqual((run / "state.json").read_bytes(), before)
        self.approve(run)
        result = subprocess.run([sys.executable, str(SCRIPT), "next", "--run", str(run)], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(len(json.loads(result.stdout)["jobs"]), 4)

    def test_private_root_and_config_preserve_existing_kb(self):
        repo = self.root / "repo"; (repo / ".git").mkdir(parents=True)
        with self.assertRaises(c.Invalid): c.initialize(repo / "personal", request())
        personal = self.root / "personal"; personal.mkdir()
        (personal / "council_kb.md").write_text("Existing lesson")
        c.configure(personal, self.root / "config.json")
        self.assertEqual((personal / "council_kb.md").read_text(), "Existing lesson")
        self.assertEqual(c.read_json(self.root / "config.json")["root"], str(personal.resolve()))

    def test_runs_cannot_redirect_private_cases_or_enter_nested_git(self):
        for in_git in (False, True):
            with self.subTest(in_git=in_git), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp); personal = base / "personal"; personal.mkdir()
                shared = base / "shared"; shared.mkdir()
                if in_git: (shared / ".git").mkdir()
                (personal / "runs").symlink_to(shared, target_is_directory=True)
                with self.assertRaises(c.Invalid): c.initialize(personal, request())
                self.assertEqual({p.name for p in shared.iterdir()}, {".git"} if in_git else set())
        (self.root / "runs/.git").mkdir(parents=True)
        with self.assertRaises(c.Invalid): self.init()
        self.assertEqual({p.name for p in (self.root / "runs").iterdir()}, {".git"})

    def test_run_subdirectories_cannot_redirect_private_writes(self):
        for directory in ("responses", "history", "learning"):
            for in_git in (False, True):
                with self.subTest(directory=directory, in_git=in_git), tempfile.TemporaryDirectory() as tmp:
                    shared = Path(tmp)
                    if in_git: (shared / ".git").mkdir()
                    run = self.init()
                    if directory != "responses": self.finish(run)
                    before = (run / "state.json").read_bytes()
                    (run / directory).symlink_to(shared, target_is_directory=True)
                    with self.assertRaises(c.Invalid):
                        if directory == "responses": c.submit(run, "grounding", envelope(self.jobs(run)[0]))
                        elif directory == "history": c.revise(run, "Clarify the explanation.")
                        else: c.learn(run, self.lesson())
                    self.assertEqual({p.name for p in shared.iterdir()}, {".git"} if in_git else set())
                    self.assertEqual((run / "state.json").read_bytes(), before)
                    self.assertFalse((self.root / "council_kb.md").exists())

    def test_relocated_run_cannot_resume_through_an_external_symlink(self):
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            run = self.init(); moved = Path(tmp) / run.name
            shutil.move(run, moved)
            run.symlink_to(moved, target_is_directory=True)
            with self.assertRaises(c.Invalid): c.load(run)
            with self.assertRaises(c.Invalid): c.load(moved)

    def test_receipt_change_and_concurrent_write_are_detected(self):
        run = self.init(); self.ground(run)
        with c.locked(run):
            with self.assertRaises(c.Invalid): self.approve(run)
        (run / "responses/grounding-1.json").write_text("changed")
        with self.assertRaises(c.Invalid): c.load(run)

    def test_changed_generated_agent_is_not_deleted(self):
        run = self.init(request(binding="custom-agent")); files = c.export_agents(run, self.root / "agents")["files"]
        self.finish(run)
        Path(files[0]).write_text("User edited this")
        with self.assertRaises(c.Invalid): c.clean_agents(run)
        self.assertTrue(all(Path(p).exists() for p in files))

    def test_cli_complete_flow_saves_report_without_live_models(self):
        def cli(*args, success=True):
            proc = subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], text=True, capture_output=True)
            self.assertEqual(proc.returncode, 0 if success else 2, proc.stdout + proc.stderr)
            return json.loads(proc.stdout)
        req = self.root / "request.json"; req.write_text(json.dumps(request()))
        state = cli("init", "--root", self.root, "--request", req); run = state["run"]
        calls = 0
        while state["status"] != "complete":
            if state["status"] == "awaiting-fact-review":
                state = cli("approve-facts", "--run", run, "--digest", state["digest"], "--reply", "Reviewed and accepted.")
            else:
                for job in state["jobs"]:
                    self.assertIn("prompt", job)
                    path = self.root / (job["role"] + ".json"); path.write_text(json.dumps(envelope(job)))
                    state = cli("submit", "--run", run, "--role", job["role"], "--response", path); calls += 1
        self.assertEqual(calls, 7)
        report = Path(state["report"]).read_text()
        self.assertIn("Status: **complete**", report)
        self.assertIn("SOURCE_SENTINEL_3", report)
        self.assertIn("not exposed", report)

    def source_request(self):
        req = request()
        req["source_targets"] = [
            {"kind": "workspace", "ref": "/example/workspace"},
            {"kind": "jira", "ref": "https://issues.example.invalid/browse/DEMO-1"},
            {"kind": "bitbucket_pr", "ref": "https://code.example.invalid/projects/DEMO/repos/app/pull-requests/7"}]
        return req

    def grounded_sources(self, req):
        result = output("grounding")
        result["source_coverage"] = [{**target, "status": "read", "as_of": "2026-10-10", "detail": "Synthetic source read at revision example-a."} for target in req["source_targets"]]
        return result

    def test_skill_learning_reaches_agents_separately_from_case_evidence(self):
        req = self.source_request()
        req["skill_lessons"] = [{"purpose": "skill_improvement", "lesson": "LESSON_SENTINEL: explain uncertainty before showing the fact table.", "context": "Fact review", "limits": "Presentation guidance only", "source": "personal KB entry example"}]
        run = self.init(req)
        prompt = self.jobs(run)[0]["prompt"]
        for target in req["source_targets"]: self.assertIn(target["ref"], prompt)
        self.assertIn("LESSON_SENTINEL", prompt)
        data = self.grounded_sources(req)
        c.submit(run, "grounding", envelope(self.jobs(run)[0], data)); self.approve(run)
        self.assertNotIn("LESSON_SENTINEL", (run / "factbase.json").read_text())
        for job in self.jobs(run):
            self.assertIn("LESSON_SENTINEL", job["prompt"])
            self.assertIn("never case evidence or fact references", job["prompt"])
            self.assertIn(req["source_targets"][2]["ref"], job["prompt"])
            c.submit(run, job["role"], envelope(job))
        for _ in range(2):
            job = self.jobs(run)[0]
            self.assertIn("LESSON_SENTINEL", job["prompt"])
            c.submit(run, job["role"], envelope(job))
        self.assertNotIn("LESSON_SENTINEL", (run / "report.md").read_text())

    def test_invalid_source_and_lesson_context_creates_no_run(self):
        for kind in ("unknown", "duplicate", "empty_lesson"):
            req = self.source_request()
            if kind == "unknown": req["source_targets"][0]["kind"] = "invented"
            if kind == "duplicate": req["source_targets"].append(req["source_targets"][0])
            if kind == "empty_lesson": req["skill_lessons"] = [{"lesson": "", "context": "x", "limits": "x", "source": "x"}]
            with self.assertRaises(c.Invalid): self.init(req)
        self.assertFalse((self.root / "runs").exists())

    def test_missing_duplicate_or_unknown_source_coverage_fails(self):
        for kind in ("missing", "duplicate", "unknown", "bad_status"):
            req = self.source_request(); run = self.init(req); data = self.grounded_sources(req)
            if kind == "missing": data["source_coverage"].pop()
            if kind == "duplicate": data["source_coverage"].append(data["source_coverage"][0])
            if kind == "unknown": data["source_coverage"][0]["ref"] = "invented"
            if kind == "bad_status": data["source_coverage"][0]["status"] = "empty_because_fetch_failed"
            self.assertFalse(c.submit(run, "grounding", envelope(self.jobs(run)[0], data))["accepted"])

    def test_access_gaps_survive_fact_review_handoff_and_final_report(self):
        req = self.source_request(); run = self.init(req); data = self.grounded_sources(req)
        data["source_coverage"][1].update(status="partial", detail="IssueTracker comments unavailable; description inspected.")
        data["source_coverage"][2].update(status="unavailable", detail="PR connection unavailable; diff and checks not read.")
        result = c.submit(run, "grounding", envelope(self.jobs(run)[0], data))
        self.assertTrue(result["accepted"])
        self.assertEqual(result["source_coverage"], data["source_coverage"])
        self.assertIn("IssueTracker comments unavailable", (run / "factbase.md").read_text())
        self.approve(run)
        for job in self.jobs(run): c.submit(run, job["role"], envelope(job))
        for _ in range(2):
            job = self.jobs(run)[0]
            self.assertIn("PR connection unavailable", job["prompt"])
            c.submit(run, job["role"], envelope(job))
        report = (run / "report.md").read_text()
        self.assertIn("2/3 requested sources are partial or unavailable", report)
        self.assertIn(req["source_targets"][1]["ref"], report)
        self.assertIn("PR connection unavailable", report)
        self.assertEqual(c.phase(c.load(run))[0], "complete")

    def test_no_source_access_stops_run_and_preserves_gaps_without_invented_facts(self):
        req = self.source_request(); run = self.init(req); data = self.grounded_sources(req)
        data.update(is_clarification=True, facts=[])
        for item in data["source_coverage"]:
            item.update(status="unavailable", detail="Read access unavailable; no source contents inspected.")
        result = c.submit(run, "grounding", envelope(self.jobs(run)[0], data))
        self.assertFalse(result["accepted"])
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["source_coverage"], data["source_coverage"])
        self.assertFalse((run / "factbase.json").exists())
        report = (run / "report.md").read_text()
        self.assertIn("3/3 requested sources are partial or unavailable", report)
        self.assertIn("no source contents inspected", report)
        self.assertNotIn("Status: **complete**", report)

    def lesson(self):
        return {"purpose": "skill_improvement", "confirmed": True, "lesson": "Decision Council should ask for the stop criterion when framing a rollout review.", "context": "Framing a rollout review", "limits": "A framing question; it does not prescribe the rollout decision.", "confirmation": "Yes, save that improvement to how Decision Council frames the question."}

    def test_learn_preserves_kb_and_deduplicates_across_runs(self):
        kb = self.root / "council_kb.md"; kb.write_text("Existing personal note.\n")
        packaged = SCRIPT.parents[1] / "kb/council_kb.md"; before = packaged.read_bytes()
        run = self.init(); self.finish(run)
        report_before = (run / "report.md").read_bytes()
        saved = c.learn(run, self.lesson())
        self.assertTrue(saved["saved"])
        self.assertEqual(saved["knowledge_base"], str(kb.resolve()))
        contents = kb.read_text()
        for phrase in ("Existing personal note.", self.lesson()["lesson"], self.lesson()["limits"], run.name):
            self.assertIn(phrase, contents)
        self.assertEqual((run / "report.md").read_bytes(), report_before)
        other = self.init(); self.finish(other)
        self.assertTrue(c.learn(other, self.lesson())["already_present"])
        self.assertEqual(kb.read_text(), contents)
        self.assertEqual(packaged.read_bytes(), before)

    def test_kb_rejects_result_fields_and_keeps_confirmation_in_run(self):
        run = self.init(); self.finish(run)
        for changes in ({"purpose": "case_result"}, {"verdict": "Approve this PR"}, {"facts": ["Case fact"]}):
            with self.assertRaises(c.Invalid): c.learn(run, {**self.lesson(), **changes})
        self.assertFalse((self.root / "council_kb.md").exists())
        entry = {**self.lesson(), "confirmation": "CASE_RESULT_SENTINEL was the result. Yes, save only the proposed method improvement."}
        saved = c.learn(run, entry)
        kb = Path(saved["knowledge_base"]).read_text()
        for sentinel in ("CASE_RESULT_SENTINEL", "FACT_SENTINEL", "CLAIM_SENTINEL", "Gather missing evidence first."):
            self.assertNotIn(sentinel, kb)
        receipt = run / "learning" / (saved["lesson_id"] + ".json")
        self.assertEqual(json.loads(receipt.read_text())["confirmation"], entry["confirmation"])

    def test_case_memory_cannot_be_loaded_as_skill_learning(self):
        base = {"purpose": "skill_improvement", "lesson": "Ask for the review boundary first.", "context": "Framing", "limits": "Process only", "source": "KB entry"}
        for changes in ({"purpose": "case_result"}, {"results": ["Old verdict"]}):
            req = request(); req["skill_lessons"] = [{**base, **changes}]
            with self.assertRaises(c.Invalid): self.init(req)
        self.assertFalse((self.root / "runs").exists())

    def test_learning_requires_confirmation_and_a_finished_run(self):
        run = self.init(); entry = self.lesson()
        with self.assertRaises(c.Invalid): c.learn(run, entry)
        self.finish(run)
        for key,value in (("confirmed", False), ("confirmation", ""), ("limits", "")):
            invalid = {**entry, key: value}
            with self.assertRaises(c.Invalid): c.learn(run, invalid)
        self.assertFalse((self.root / "council_kb.md").exists())

    def test_kb_lock_and_symlink_preserve_other_files(self):
        run = self.init(); self.finish(run)
        with c.locked(self.root):
            with self.assertRaises(c.Invalid): c.learn(run, self.lesson())
        existing = self.root / "other.md"; existing.write_text("Preserve this")
        (self.root / "council_kb.md").symlink_to(existing)
        with self.assertRaises(c.Invalid): c.learn(run, self.lesson())
        self.assertEqual(existing.read_text(), "Preserve this")

    def test_cli_records_confirmed_lesson_and_can_reopen_it(self):
        run = self.init(); self.finish(run)
        entry = self.root / "lesson.json"; entry.write_text(json.dumps(self.lesson()))
        proc = subprocess.run([sys.executable, str(SCRIPT), "learn", "--run", str(run), "--entry", str(entry)], text=True, capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        result = json.loads(proc.stdout)
        self.assertTrue(result["saved"])
        self.assertIn(self.lesson()["context"], Path(result["knowledge_base"]).read_text())
        self.assertEqual(c.phase(c.load(run))[0], "complete")


if __name__ == "__main__":
    unittest.main()
