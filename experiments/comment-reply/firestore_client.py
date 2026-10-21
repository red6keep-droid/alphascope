"""Firestore 댓글 클라이언트 (2026-10-14 블로거 댓글 → 우리 댓글(Firebase) 이전)

테마 JS 가 쓰는 구조 그대로 읽고 쓴다 — 리포 루트 firestore.rules 참고:
    posts/{postId}/comments/{commentId}
      uid · name · photo · text · created(서버 시각) · parent(답글이면 원 댓글 ID)

서비스 계정으로 REST 를 부른다. 서비스 계정은 보안 규칙을 거치지 않으므로
봇 답글은 주인 UID 로 직접 쓴다 — 화면에는 테마가 `AlphaScope` · 로고로 보여 준다.

환경변수:
    FIREBASE_SERVICE_ACCOUNT  서비스 계정 키 JSON 전체 (또는 그 파일 경로)
    FIREBASE_OWNER_UID        (선택) 블로그 주인 UID — 기본은 테마 CFG.owner 와 같은 값
"""

import json
import os

import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account

SCOPES = ["https://www.googleapis.com/auth/datastore"]
DEFAULT_OWNER_UID = "u1vln4bbDgSgWQDe2F2FaNs81D43"   # 테마 CFG.owner · firestore.rules isOwner 와 같다
OWNER_NAME = "AlphaScope"


def _service_account_info():
    raw = os.environ.get("FIREBASE_SERVICE_ACCOUNT", "").strip()
    if not raw:
        raise RuntimeError("FIREBASE_SERVICE_ACCOUNT 환경 변수가 필요합니다 (서비스 계정 키 JSON 또는 파일 경로).")
    if not raw.startswith("{") and os.path.exists(raw):
        with open(raw, "r", encoding="utf-8") as f:
            raw = f.read()
    return json.loads(raw)


class FirestoreClient:
    def __init__(self):
        info = _service_account_info()
        self.project_id = info["project_id"]
        self.creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
        self.owner_uid = os.environ.get("FIREBASE_OWNER_UID", "").strip() or DEFAULT_OWNER_UID
        self.root = f"projects/{self.project_id}/databases/(default)/documents"
        self.base = f"https://firestore.googleapis.com/v1/{self.root}"

    def _headers(self):
        if not self.creds.valid:
            self.creds.refresh(Request())
        return {"Authorization": f"Bearer {self.creds.token}", "Content-Type": "application/json"}

    def _call(self, method, url, body=None):
        resp = requests.request(method, url, headers=self._headers(), json=body, timeout=30)
        if not resp.ok:
            raise RuntimeError(f"Firestore {method} {resp.status_code}: {resp.text[:300]}")
        return resp.json() if resp.text else {}

    @staticmethod
    def _from_doc(doc):
        f = doc.get("fields", {})

        def s(k):
            return (f.get(k) or {}).get("stringValue", "")

        parts = doc["name"].split("/")   # .../documents/posts/{postId}/comments/{id}
        return {
            "id": parts[-1],
            "post_id": parts[-3],
            "uid": s("uid"),
            "name": s("name"),
            "text": s("text"),
            "parent": s("parent"),
            "created": (f.get("created") or {}).get("timestampValue") or doc.get("createTime", ""),
        }

    def list_comments(self, since=None):
        """댓글 (컬렉션 그룹 질의). since(ISO 시각)가 있으면 그 뒤에 쓰인 것만 — 실행마다 전체를 읽어 무료 읽기 한도(하루 5만)를
        갉아먹던 것을 줄인다 (2026-10-21, 운영지침 D7-4). created 범위 필터는 **컬렉션 그룹 색인**이 필요하다
        (Firestore 콘솔 → 색인 → 단일 필드 → comments.created 에 '컬렉션 그룹' 범위 켜기). 색인이 없으면 400 이 오고 — 그때는
        예전처럼 전체를 읽고 경고만 남긴다. 정렬은 여기서."""
        q = {"from": [{"collectionId": "comments", "allDescendants": True}]}
        if since:
            q["where"] = {"fieldFilter": {"field": {"fieldPath": "created"}, "op": "GREATER_THAN_OR_EQUAL", "value": {"timestampValue": since}}}
        try:
            rows = self._call("POST", f"{self.base}:runQuery", {"structuredQuery": q})
        except RuntimeError as e:
            if not since or "400" not in str(e):
                raise
            print(f"::warning::[firestore] created 필터 질의 실패 (컬렉션 그룹 색인 없음?) — 전체 읽기로 대신: {str(e)[:120]}")
            rows = self._call("POST", f"{self.base}:runQuery", {"structuredQuery": {"from": [{"collectionId": "comments", "allDescendants": True}]}})
        items = [self._from_doc(r["document"]) for r in rows if r.get("document")]
        return sorted(items, key=lambda c: c["created"])

    def add_reply(self, post_id, parent_id, text):
        """주인 이름으로 답글. 답글은 한 단계뿐이라 parent 는 항상 최상위 댓글 ID."""
        name = f"{self.root}/posts/{post_id}/comments/{os.urandom(10).hex()}"
        fields = {
            "uid": {"stringValue": self.owner_uid},
            "name": {"stringValue": OWNER_NAME},
            "photo": {"stringValue": ""},
            "text": {"stringValue": text[:2000]},
            "parent": {"stringValue": parent_id},
        }
        self._call("POST", f"{self.base}:commit", {"writes": [{
            "update": {"name": name, "fields": fields},
            "updateTransforms": [{"fieldPath": "created", "setToServerValue": "REQUEST_TIME"}],
            "currentDocument": {"exists": False},
        }]})
        return name.split("/")[-1]

    def delete_comment(self, post_id, comment_id):
        self._call("DELETE", f"{self.base}/posts/{post_id}/comments/{comment_id}")
