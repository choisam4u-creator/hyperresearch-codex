"""설정: 모델 역할표·게이트 상한·검색 제공자. research/config.json 으로 필요한 키만 덮어쓴다."""
import json
from pathlib import Path

DEFAULT_MODEL = "gpt-6-astra"

DEFAULTS = {
    "default_model": DEFAULT_MODEL,
    "report_format": "brief",
    "lang": "ko",                 # 프롬프트·보고서 언어: ko | en
    "preset": "standard",         # standard | lean (구독 계정용: 비평 2·초안 2·상한 축소)
    "presets": {
        "lean": {"light": {"max_sources": 8, "critics": ["dialectic", "instruction"], "cite_sample": 5, "target_words": 700},
                 "full": {"max_sources": 12, "loci_max": 2, "drafts": 2, "critics": ["dialectic", "depth", "instruction"], "cite_sample": 6, "target_words": 1600},
                 "models": {"synth": {"effort": "medium"}, "critic": {"effort": "low"}, "writer": {"effort": "medium"}},
                 "note_max_chars": 8000, "draft_note_chars": 5000, "excerpt_chars": 1800, "scout_max_searches": 4},
        "economy": {"light": {"max_sources": 8, "critics": ["dialectic", "instruction"], "cite_sample": 5, "target_words": 700},
                    "full": {"max_sources": 12, "loci_max": 2, "drafts": 2, "critics": ["dialectic", "depth", "instruction"], "cite_sample": 6, "target_words": 1600},
                    "models": {"scout": {"model": "gpt-5.6-luna"}, "analyst": {"model": "gpt-5.6-terra"},
                               "loci": {"model": "gpt-5.6-sol"}, "investigator": {"model": "gpt-5.6-sol"},
                               "writer": {"model": "gpt-5.6-sol"}, "synth": {"model": "gpt-5.6-sol", "effort": "medium"},
                               "critic": {"model": "gpt-5.6-terra"}, "patcher": {"model": "gpt-5.6-terra"},
                               "citecheck": {"model": "gpt-6-astra"}, "polish": {"model": "gpt-5.6-luna"}},
                    "routing": {"enabled": True},
                    "budget": {"reserve_input": True, "stop_on_unknown": True, "max_retries": 0, "max_model_calls": 24},
                    "note_max_chars": 8000, "draft_note_chars": 5000, "excerpt_chars": 1800, "scout_max_searches": 4},
        "standard": {}},
    # 역할별 모델과 추론 강도. model 이 None 이면 default_model.
    "models": {
        "scout":        {"model": None, "effort": "low"},
        "analyst":      {"model": None, "effort": "low"},
        "loci":         {"model": None, "effort": "medium"},
        "investigator": {"model": None, "effort": "medium"},
        "writer":       {"model": None, "effort": "medium"},
        "synth":        {"model": None, "effort": "high"},
        "critic":       {"model": None, "effort": "medium"},
        "patcher":      {"model": None, "effort": "low"},
        "citecheck":    {"model": None, "effort": "low"},
        "polish":       {"model": None, "effort": "low"},
    },
    "search": {
        "providers": ["codex_scout", "duckduckgo"],   # 순서대로. codex_scout 는 codex --search 로 공식 문서를 먼저 찾는다
        "preferred_domains": [],                      # 예: ["developers.openai.com", "github.com/openai"]
        "query_variants": True,
        "searxng_endpoint": None,                     # 기본 비활성. DuckDuckGo 무결과일 때만 명시 endpoint를 보조로 쓴다
    },
    "efficiency": {"packet_inputs": False, "inline_inputs": False, "evidence_selection": False, "reuse_analysis": False, "strategy": "standard"},
    "critic_policy": {"compact_inputs": True, "combine_light": False},
    "routing": {"enabled": False, "escalation_model": "gpt-6-astra", "escalation_effort": "high", "max_escalations": 1},
    "verification": {"recheck_changed": False, "require_traceability": False, "semantic": False},
    "reuse": {"enabled": False, "max_age_days": 30, "limit": 3},
    "gap_fetch": {"enabled": False, "max_gaps": 2, "max_sources": 3},
    "light": {"search_results": 12, "max_sources": 10, "critics": ["dialectic", "depth", "instruction"],
              "cite_sample": 6, "target_words": 900, "parallel": 2},
    "full":  {"search_results": 24, "max_sources": 20, "loci_max": 4, "drafts": 3,
              "critics": ["dialectic", "depth", "width", "instruction"], "cite_sample": 10, "target_words": 2500,
              "parallel": 2, "polish": True},
    "gates": {"patch_max_ratio": 0.30, "polish_max_ratio": 0.15, "hunk_max_chars": 1200, "min_note_chars": 400,
              "dup_jaccard": 0.6},
    "fetch": {"allow_private_hosts": [], "max_redirects": 5, "timeout": 20, "max_bytes": 2_000_000, "parallel": 4,
              "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"},
    "note_max_chars": 12000,      # 분석가·지점 조사에 넣는 노트 상한(자)
    "draft_note_chars": 8000,     # 초안에 넣는 노트 상한
    "excerpt_chars": 2500,        # 비평·수정에 넣는 출처 발췌 상한
    "cite_note_chars": 6000,      # 인용 검사에 넣는 인용된 노트 상한
    "scout_max_searches": 6,      # 정찰 웹 검색 횟수 상한(프롬프트로 지시)
    "budget": {"max_total_tokens": None, "output_reservation": 4096, "max_model_calls": 64, "max_retries": 1, "reserve_input": False, "stop_on_unknown": False, "max_input_tokens": None,            # 명시하면 tier 기본값보다 우선
               "default_by_tier": {"light": 1_200_000, "full": 3_500_000},   # 실행별 기본 상한(넘으면 멈춤, resume 가능)
               "price_input_per_m": 10.0, "price_output_per_m": 50.0, "price_cached_per_m": None},
    "domain_skew_warn": 0.6,      # 한 도메인이 출처의 60% 넘으면 경고
    # ignore_user_config: ~/.codex/config.toml 과 스킬 주입을 빼서 호출당 입력 토큰을 크게 줄인다(실측 119,520 → 18,781).
    "codex": {"timeout": 900, "ignore_user_config": True, "extra_args": ["--skip-git-repo-check", "--ephemeral"]},
}


def _merge(cfg: dict, user: dict) -> None:
    for key, value in user.items():
        if isinstance(value, dict) and isinstance(cfg.get(key), dict):
            for k2, v2 in value.items():
                if isinstance(v2, dict) and isinstance(cfg[key].get(k2), dict):
                    cfg[key][k2].update(v2)
                else:
                    cfg[key][k2] = v2
        else:
            cfg[key] = value


def load(root: Path, preset: str | None = None, lang: str | None = None) -> dict:
    cfg = json.loads(json.dumps(DEFAULTS))
    path = root / "research" / "config.json"
    if path.is_file():
        _merge(cfg, json.loads(path.read_text(encoding="utf-8")))
    cfg["preset"] = preset or cfg["preset"]
    _merge(cfg, cfg["presets"].get(cfg["preset"], {}))
    # economy도 사용자가 명시한 역할/예산 정책을 덮어쓰지 않는다.
    if path.is_file():
        user = json.loads(path.read_text(encoding="utf-8"))
        for key in ("models", "budget", "verification", "routing"):
            if key in user:
                _merge(cfg, {key: user[key]})
    cfg["lang"] = lang or cfg["lang"]
    for role in cfg["models"].values():
        role["model"] = role.get("model") or cfg["default_model"]
    return cfg
