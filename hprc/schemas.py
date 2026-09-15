"""각 단계의 최종 답 JSON 스키마(codex exec --output-schema 로 강제)."""
FINDING = {"type": "object", "additionalProperties": False,
           "properties": {"id": {"type": "string"}, "quote": {"type": "string"}, "problem": {"type": "string"},
                          "suggested_fix": {"type": "string"}, "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                          "evidence_status": {"type": "string", "enum": ["actionable", "excerpt_insufficient"]},
                          "source_ids": {"type": "array", "items": {"type": "string"}}},
           "required": ["id", "quote", "problem", "suggested_fix", "severity", "source_ids", "evidence_status"]}

ANALYST = {"type": "object", "additionalProperties": False,
           "properties": {
               "claims": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                          "properties": {"id": {"type": "string"}, "text": {"type": "string"},
                                         "sources": {"type": "array", "items": {"type": "string"}},
                                         "confidence": {"type": "string", "enum": ["high", "medium", "low"]}},
                          "required": ["id", "text", "sources", "confidence"]}},
               "contradictions": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                  "properties": {"claim_ids": {"type": "array", "items": {"type": "string"}}, "note": {"type": "string"}},
                                  "required": ["claim_ids", "note"]}},
               "gaps": {"type": "array", "items": {"type": "string"}}},
           "required": ["claims", "contradictions", "gaps"]}

WRITER = {"type": "object", "additionalProperties": False,
          "properties": {"markdown": {"type": "string"}}, "required": ["markdown"]}

CRITIC = {"type": "object", "additionalProperties": False,
          "properties": {"findings": {"type": "array", "items": FINDING}}, "required": ["findings"]}

PATCHER = {"type": "object", "additionalProperties": False,
           "properties": {
               "hunks": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                         "properties": {"find": {"type": "string"}, "replace": {"type": "string"},
                                        "finding_ids": {"type": "array", "items": {"type": "string"}}},
                         "required": ["find", "replace", "finding_ids"]}},
               "skipped": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                           "properties": {"finding_id": {"type": "string"}, "reason": {"type": "string"}},
                           "required": ["finding_id", "reason"]}}},
           "required": ["hunks", "skipped"]}

CITECHECK = {"type": "object", "additionalProperties": False,
             "properties": {"checks": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                            "properties": {"sentence": {"type": "string"}, "cites": {"type": "array", "items": {"type": "string"}},
                                           "supported": {"type": "boolean"}, "reason": {"type": "string"}},
                            "required": ["sentence", "cites", "supported", "reason"]}}},
             "required": ["checks"]}

SCOUT = {"type": "object", "additionalProperties": False,
         "properties": {"results": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                        "properties": {"url": {"type": "string"}, "title": {"type": "string"}, "official": {"type": "boolean"},
                                       "why": {"type": "string"}, "published": {"type": "string"}},
                        "required": ["url", "title", "official", "why", "published"]}}},
         "required": ["results"]}

LOCI = {"type": "object", "additionalProperties": False,
        "properties": {"loci": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                       "properties": {"id": {"type": "string"}, "question": {"type": "string"}, "why": {"type": "string"},
                                      "source_ids": {"type": "array", "items": {"type": "string"}}},
                       "required": ["id", "question", "why", "source_ids"]}}},
        "required": ["loci"]}

INVESTIGATOR = {"type": "object", "additionalProperties": False,
                "properties": {"position": {"type": "string"},
                               "evidence": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                            "properties": {"claim": {"type": "string"}, "source_ids": {"type": "array", "items": {"type": "string"}}},
                                            "required": ["claim", "source_ids"]}},
                               "open_questions": {"type": "array", "items": {"type": "string"}}},
                "required": ["position", "evidence", "open_questions"]}
