"""두 실행의 불변 출처를 비교하고 보수적인 증분 분석 계획을 만든다.

같은 URL이라는 사실만으로 출처가 같다고 보지 않는다. 불변 snapshot 해시와
본문 해시를 모두 확인할 수 있을 때만 이전 주장을 유지한다. 이 비교는 현재
웹의 신선함을 인증하지 않으며 네트워크 접근도 하지 않는다.
"""
from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from . import vault


SCHEMA_VERSION = 1
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _sha(value: object) -> str | None:
    if isinstance(value, str):
        candidate = value[2:] if value.startswith("N-") else value
        if _SHA256.fullmatch(candidate):
            return candidate
    return None


def _read_json_file(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"필수 파일이 일반 파일이 아님: {path.name}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} 최상위 값이 객체가 아님")
    return value


def _notes_root(run_dir: Path) -> Path:
    resolved = run_dir.resolve()
    if resolved.parent.name != "runs":
        raise ValueError("실행 폴더는 research/runs 바로 아래여야 함")
    notes = resolved.parent.parent / "notes"
    if notes.is_symlink():
        raise ValueError("notes 경로가 심볼릭 링크임")
    return notes.resolve()


def _note_text(path: Path, front: dict) -> str:
    body = vault.note_body(path)
    heading = "# " + str(front.get("title") or front.get("url") or "")
    prefix = "\n" + heading + "\n\n"
    if not body.startswith(prefix):
        raise ValueError("노트 heading과 metadata가 다름")
    text = body[len(prefix):]
    return text[:-1] if text.endswith("\n") else text


def _source_identity(row: object, notes_root: Path) -> dict:
    if not isinstance(row, dict):
        return {"known": False, "reason": "source_not_object"}
    source_id, url = row.get("id"), row.get("url")
    base = {"source_id": source_id, "url": url}
    if not isinstance(source_id, str) or not source_id or not isinstance(url, str) or not url:
        return {**base, "known": False, "reason": "source_id_or_url_missing"}

    snapshot = next((_sha(row.get(name)) for name in ("snapshot_sha256", "snapshot_hash", "note_id")
                     if _sha(row.get(name))), None)
    text_hash = next((_sha(row.get(name)) for name in ("text_sha256", "content_sha256", "sha256")
                      if _sha(row.get(name))), None)
    raw_path = row.get("path")
    if raw_path:
        try:
            path = Path(raw_path)
            if path.is_symlink():
                raise ValueError("note symlink")
            path = path.resolve()
            path.relative_to(notes_root)
            if not path.is_file():
                raise ValueError("note missing")
            front = vault.read_front(path)
            text = _note_text(path, front)
            actual_text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
            recorded_text_hash = _sha(front.get("sha256"))
            recorded_snapshot = _sha(front.get("id"))
            if text_hash is not None and text_hash != actual_text_hash:
                raise ValueError("source row text hash mismatch")
            if recorded_text_hash != actual_text_hash:
                raise ValueError("note text hash mismatch")
            if snapshot is not None and snapshot != recorded_snapshot:
                raise ValueError("source row snapshot mismatch")
            if front.get("url") != url:
                raise ValueError("note url mismatch")
            metadata = {key: front.get(key, "") for key in
                        ("url", "final_url", "title", "domain", "via", "official", "published",
                         "published_source", "modified", "modified_source", "canonical")}
            computed = _sha(vault._snapshot_id({"text": text, **metadata}))
            if recorded_snapshot is None or computed != recorded_snapshot:
                raise ValueError("note snapshot hash mismatch")
            snapshot, text_hash = recorded_snapshot, actual_text_hash
        except (OSError, UnicodeError, ValueError, TypeError, IndexError) as error:
            return {**base, "known": False, "reason": str(error) or "note_validation_failed"}
    if snapshot is None or text_hash is None:
        return {**base, "known": False, "reason": "snapshot_or_text_hash_missing"}
    return {**base, "known": True, "snapshot_sha256": snapshot, "text_sha256": text_hash}


def _source_inventory(rows: object, notes_root: Path) -> tuple[list[dict], list[str]]:
    if isinstance(rows, dict):
        rows = rows.get("sources")
    if not isinstance(rows, list):
        return [], ["sources_not_list"]
    records = [_source_identity(row, notes_root) for row in rows]
    errors = []
    ids = [record.get("source_id") for record in records]
    urls = [record.get("url") for record in records]
    if len(ids) != len(set(ids)):
        errors.append("duplicate_source_id")
    if len(urls) != len(set(urls)):
        errors.append("duplicate_source_url")
    return records, errors


def _claims(value: object) -> tuple[list[dict], list[str]]:
    rows = value.get("claims") if isinstance(value, dict) else None
    if not isinstance(rows, list):
        return [], ["claims_not_list"]
    errors, seen, valid = [], set(), []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"]:
            errors.append("claim_id_missing")
            continue
        if row["id"] in seen:
            errors.append("duplicate_claim_id")
        seen.add(row["id"])
        if not isinstance(row.get("text"), str) or not isinstance(row.get("sources"), list) or not all(
            isinstance(source_id, str) for source_id in row.get("sources", [])
        ):
            errors.append(f"invalid_claim:{row['id']}")
            continue
        valid.append(row)
    return valid, errors


def _known_analysis_runtime(value):
    if not isinstance(value, dict) or not value: return False
    if 'config' in value:
        return (isinstance(value.get('config'), dict) and bool(value['config'])
                and isinstance(value.get('runtime'), dict)
                and all(isinstance(value['runtime'].get(k), str) and value['runtime'][k] for k in ('code_hash', 'prompt_hash'))
                and isinstance(value.get('model'), dict) and bool(value['model'])
                and isinstance(value.get('schema'), dict) and bool(value['schema'])
                and isinstance(value.get('prompt'), str) and bool(value['prompt'])
                and isinstance(value.get('backend'), str) and bool(value['backend']))
    return (all(isinstance(value.get(k), str) and value[k] for k in ('config_hash', 'prompt_hash', 'code_hash'))
            and isinstance(value.get('model'), dict) and bool(value['model']))


def _manifest_context(manifest: dict) -> dict | None:
    runtime = manifest.get("runtime")
    if not isinstance(runtime, dict):
        return None
    models = runtime.get("models")
    analyst = models.get("analyst") if isinstance(models, dict) else None
    analysis_runtime = manifest.get("analysis_runtime")
    if analysis_runtime is None:
        analysis_runtime = {
            "config_hash": runtime.get("config_hash"),
            "prompt_hash": runtime.get("prompt_hash"),
            "code_hash": runtime.get("code_hash"),
            "model": analyst,
        }
    if not _known_analysis_runtime(analysis_runtime): return None
    context = {
        "question": manifest.get("question", manifest.get("prompt")),
        "lang": manifest.get("lang"),
        "as_of": manifest.get("as_of"),
        "analysis_runtime": analysis_runtime,
    }
    if not all(context.get(name) is not None for name in ("question", "lang", "as_of", "analysis_runtime")):
        return None
    try:
        json.dumps(context, ensure_ascii=False, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError):
        return None
    return context


def _current_context(value: object) -> dict | None:
    if not isinstance(value, dict):
        return None
    context = {
        "question": value.get("question", value.get("prompt")),
        "lang": value.get("lang"),
        "as_of": value.get("as_of"),
        "analysis_runtime": value.get("analysis_runtime", value.get("runtime")),
    }
    if not _known_analysis_runtime(context["analysis_runtime"]): return None
    if not all(context.get(name) is not None for name in context):
        return None
    try:
        json.dumps(context, ensure_ascii=False, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError):
        return None
    return context


def _source_diff(previous: list[dict], current: list[dict]) -> dict:
    old_by_url = {row.get("url"): row for row in previous}
    new_by_url = {row.get("url"): row for row in current}
    added, removed, changed, unchanged, unknown = [], [], [], [], []
    for url in sorted(set(old_by_url) | set(new_by_url)):
        old, new = old_by_url.get(url), new_by_url.get(url)
        common = {"url": url, "previous_id": old.get("source_id") if old else None,
                  "current_id": new.get("source_id") if new else None}
        if old is None:
            row = {**common, "current_snapshot_sha256": new.get("snapshot_sha256"),
                   "current_text_sha256": new.get("text_sha256")}
            added.append(row)
            if not new.get("known"):
                unknown.append({**common, "reason": new.get("reason")})
        elif new is None:
            row = {**common, "previous_snapshot_sha256": old.get("snapshot_sha256"),
                   "previous_text_sha256": old.get("text_sha256")}
            removed.append(row)
            if not old.get("known"):
                unknown.append({**common, "reason": old.get("reason")})
        elif not old.get("known") or not new.get("known"):
            unknown.append({**common, "reason": old.get("reason") or new.get("reason")})
        elif (old["snapshot_sha256"], old["text_sha256"]) == (new["snapshot_sha256"], new["text_sha256"]):
            unchanged.append({**common, "snapshot_sha256": old["snapshot_sha256"],
                              "text_sha256": old["text_sha256"]})
        else:
            changed.append({**common,
                            "previous_snapshot_sha256": old["snapshot_sha256"],
                            "current_snapshot_sha256": new["snapshot_sha256"],
                            "previous_text_sha256": old["text_sha256"],
                            "current_text_sha256": new["text_sha256"]})
    return {"added": added, "removed": removed, "changed_source": changed,
            "unchanged": unchanged, "unknown": unknown}


def _claim_diff(previous: list[dict], current: list[dict], old_sources: list[dict], new_sources: list[dict]) -> dict:
    old_urls = {row.get("source_id"): (row.get("url"), row.get("snapshot_sha256"), row.get("text_sha256")) for row in old_sources}
    new_urls = {row.get("source_id"): (row.get("url"), row.get("snapshot_sha256"), row.get("text_sha256")) for row in new_sources}
    before, after = {row["id"]: row for row in previous}, {row["id"]: row for row in current}
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    changed, unchanged = [], []
    details = []
    for claim_id in sorted(set(before) & set(after)):
        old, new = before[claim_id], after[claim_id]
        old_value = {"text": old["text"], "sources": [old_urls.get(source_id) for source_id in old["sources"]]}
        new_value = {"text": new["text"], "sources": [new_urls.get(source_id) for source_id in new["sources"]]}
        if old_value == new_value:
            unchanged.append(claim_id)
        else:
            changed.append(claim_id)
            details.append({"id": claim_id, "before": old, "after": new})
    return {"added": added, "removed": removed, "changed": changed, "unchanged": unchanged,
            "details": details}


def _load_run(run_dir: Path) -> dict:
    supplied = Path(run_dir)
    if supplied.is_symlink() or not supplied.is_dir():
        raise ValueError("run directory가 일반 디렉터리가 아님")
    run = supplied.resolve()
    manifest = _read_json_file(run / "manifest.json")
    sources_json = _read_json_file(run / "sources.json")
    claims_json = _read_json_file(run / "claims.json")
    sources, source_errors = _source_inventory(sources_json, _notes_root(run))
    claims, claim_errors = _claims(claims_json)
    known_ids = {row.get("source_id") for row in sources}
    dangling = sorted({source_id for claim in claims for source_id in claim["sources"] if source_id not in known_ids})
    if dangling:
        claim_errors.append("claim_unknown_sources:" + ",".join(dangling))
    return {"dir": run, "manifest": manifest, "sources": sources, "claims": claims,
            "errors": source_errors + claim_errors}


def compare_runs(previous_dir: Path, current_dir: Path) -> dict:
    """저장된 두 실행을 비교한다. ``freshness_certified``는 항상 거짓이다."""
    reasons = []
    try:
        previous, current = _load_run(previous_dir), _load_run(current_dir)
        reasons.extend(previous["errors"] + current["errors"])
        previous_context = _manifest_context(previous["manifest"])
        current_context = _manifest_context(current["manifest"])
        if previous_context is None or current_context is None:
            context_diff = ["unknown"]
            reasons.append("analysis_context_unknown")
        else:
            context_diff = [name for name in ("question", "lang", "as_of", "analysis_runtime")
                            if previous_context[name] != current_context[name]]
            if context_diff:
                reasons.append("analysis_context_changed")
        changes = _source_diff(previous["sources"], current["sources"])
        old_affected = {row["previous_id"] for row in changes["removed"] + changes["changed_source"] + changes["unknown"] if row.get("previous_id")}
        new_affected = {row["current_id"] for row in changes["added"] + changes["changed_source"] + changes["unknown"] if row.get("current_id")}
        previous_claim_ids = sorted(claim["id"] for claim in previous["claims"] if set(claim["sources"]) & old_affected)
        current_claim_ids = sorted(claim["id"] for claim in current["claims"] if set(claim["sources"]) & new_affected)
        diff = _claim_diff(previous["claims"], current["claims"], previous["sources"], current["sources"])
        if changes["unknown"]:
            reasons.append("source_identity_unknown")
        structural_reasons = [reason for reason in reasons if reason not in {"analysis_context_changed"}]
        valid = not structural_reasons
        has_changes = bool(context_diff) or any(changes[name] for name in ("added", "removed", "changed_source"))
        status = "unknown" if not valid else "changed" if has_changes or any(diff[name] for name in ("added", "removed", "changed")) else "unchanged"
        result = {
            "schema_version": SCHEMA_VERSION,
            "status": status,
            "comparison_valid": valid,
            "freshness_certified": False,
            "context_diff": context_diff,
            "previous_run_id": previous["manifest"].get("run_id", previous["dir"].name),
            "current_run_id": current["manifest"].get("run_id", current["dir"].name),
            "changes": changes,
            "added_sources": changes["added"],
            "removed_sources": changes["removed"],
            "changed_sources": changes["changed_source"],
            "unchanged_sources": changes["unchanged"],
            "unknown_sources": changes["unknown"],
            "affected_claim_ids": {"previous": previous_claim_ids, "current": current_claim_ids},
            "claim_diff": diff,
            "requires_full_analysis": not valid or bool(context_diff),
            "reasons": sorted(set(reasons)),
        }
        return result
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
        return {"schema_version": SCHEMA_VERSION, "status": "unknown", "comparison_valid": False,
                "freshness_certified": False, "previous_run_id": Path(previous_dir).name,
                "current_run_id": Path(current_dir).name, "context_diff": ["unknown"],
                "changes": {"added": [], "removed": [],
                "changed_source": [], "unchanged": [], "unknown": []}, "added_sources": [],
                "removed_sources": [], "changed_sources": [], "unchanged_sources": [], "unknown_sources": [],
                "affected_claim_ids": {"previous": [], "current": []},
                "claim_diff": {"added": [], "removed": [], "changed": [], "unchanged": [], "details": []},
                "requires_full_analysis": True, "reasons": [str(error) or type(error).__name__]}


def plan_incremental_analysis(previous_dir: Path, current_sources: list[dict] | dict,
                              current_context: dict) -> dict:
    """이전 주장 중 안전하게 유지할 것과 다시 분석할 현재 출처를 계획한다.

    ``contradictions``와 ``gaps``는 부분 재사용하지 않는다. 호출자는 증분 분석의
    새 claims와 retained_claims를 합친 뒤 두 필드를 전체 기준으로 재평가해야 한다.
    """
    base = {
        "schema_version": SCHEMA_VERSION,
        "mode": "full",
        "requires_full_analysis": True,
        "whole_analysis_cache_eligible": False,
        "context_diff": [],
        "source_id_map": {},
        "retained_claims": [],
        "invalidated_claim_ids": [],
        "changed_source_ids": [],
        "analysis_source_ids": [],
        "recompute": ["contradictions", "gaps"],
        "freshness_certified": False,
        "reasons": [],
        "changes": {"added": [], "removed": [], "changed_source": [], "unchanged": [], "unknown": []},
    }
    try:
        previous = _load_run(previous_dir)
        current, current_errors = _source_inventory(current_sources, _notes_root(previous["dir"]))
        reasons = list(previous["errors"] + current_errors)
        previous_context = _manifest_context(previous["manifest"])
        supplied_context = _current_context(current_context)
        if previous_context is None or supplied_context is None:
            reasons.append("analysis_context_unknown")
            context_diff = ["unknown"]
        else:
            context_diff = [name for name in ("question", "lang", "as_of", "analysis_runtime")
                            if previous_context[name] != supplied_context[name]]
            if context_diff:
                reasons.append("analysis_context_changed")
        changes = _source_diff(previous["sources"], current)
        if changes["unknown"]:
            reasons.append("source_identity_unknown")
        if not current:
            reasons.append("current_sources_empty")
        base.update(context_diff=context_diff, changes=changes, reasons=sorted(set(reasons)))
        if reasons:
            return base

        source_id_map = {row["previous_id"]: row["current_id"] for row in changes["unchanged"]}
        invalid_source_ids = {row["previous_id"] for row in changes["removed"] + changes["changed_source"]}
        retained, invalidated, companion_ids = [], [], set()
        for claim in previous["claims"]:
            if set(claim["sources"]) & invalid_source_ids:
                invalidated.append(claim["id"])
                companion_ids.update(source_id_map[source_id] for source_id in claim["sources"] if source_id in source_id_map)
                continue
            remapped = deepcopy(claim)
            remapped["sources"] = [source_id_map[source_id] for source_id in claim["sources"]]
            retained.append(remapped)
        changed_ids = {row["current_id"] for row in changes["added"] + changes["changed_source"] if row.get("current_id")}
        analysis_ids = changed_ids | companion_ids
        current_order = [row["source_id"] for row in current]
        ordered_changed = [source_id for source_id in current_order if source_id in changed_ids]
        ordered_analysis = [source_id for source_id in current_order if source_id in analysis_ids]
        has_changes = any(changes[name] for name in ("added", "removed", "changed_source"))
        base.update({
            "mode": "incremental" if has_changes else "unchanged",
            "requires_full_analysis": False,
            "whole_analysis_cache_eligible": not has_changes,
            "source_id_map": source_id_map,
            "retained_claims": retained,
            "invalidated_claim_ids": sorted(invalidated),
            "changed_source_ids": ordered_changed,
            "analysis_source_ids": ordered_analysis,
            "changes": changes,
            "reasons": [],
        })
        return base
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
        base["reasons"] = [str(error) or type(error).__name__]
        return base


__all__ = ["SCHEMA_VERSION", "compare_runs", "plan_incremental_analysis"]


def verified_source_texts(run_dir: Path) -> dict[str, str]:
    """계산용 원문은 실행 notes 경계와 불변 snapshot을 확인한 뒤에만 읽는다."""
    rows = _read_json_file(Path(run_dir) / 'sources.json').get('sources')
    inventory, errors = _source_inventory(rows, _notes_root(Path(run_dir)))
    if errors or not inventory or any(not row.get('known') for row in inventory):
        raise ValueError('source snapshot integrity could not be verified')
    if not isinstance(rows, list) or any(not row.get('path') for row in rows):
        raise ValueError('verified local note paths are required')
    return {row['id']: vault.note_body(Path(row['path'])) for row in rows}
