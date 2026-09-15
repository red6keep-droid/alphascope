"""섹터 → ETF → 종목 정적 매핑 (기획서 4-B).

AI가 아니라 mapping_rules.json이 결정한다. 이벤트에는 적용된 rule_id만 남기고,
"왜 이 종목인가"는 리포트가 규칙의 path_text를 읽어 설명한다.
"""

import json

import config

_RULES = None


def load_rules(path=config.MAPPING_RULES_PATH):
    global _RULES
    if _RULES is None:
        with open(path, "r", encoding="utf-8") as f:
            _RULES = json.load(f)["rules"]
    return _RULES


def _matches(cond, event):
    for key, want in cond.items():
        have = event.get(key)
        if isinstance(want, list):
            have_list = have if isinstance(have, list) else [have]
            if not any(h in want for h in have_list):
                return False
        elif have != want:
            return False
    return True


def apply(event):
    """event: {topic, subtopic, target_country: [...], target_sector: [...], mentioned_companies: [...]}
    → (rule_id | None, affected_companies)"""
    mentioned = [c for c in (event.get("mentioned_companies") or []) if c]
    for rule in load_rules():
        if _matches(rule["match"], event):
            companies = list(dict.fromkeys(mentioned + rule["companies"]))
            return rule["rule_id"], companies
    return None, mentioned


def rule_by_id(rule_id):
    for rule in load_rules():
        if rule["rule_id"] == rule_id:
            return rule
    return None
