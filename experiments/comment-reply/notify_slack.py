"""Slack 인커밍 웹훅으로 알림 전송

환경변수:
    SLACK_WEBHOOK_URL  Slack 앱 > Incoming Webhooks 에서 만든 Webhook URL
                       (https://hooks.slack.com/services/...)
"""

import os

import requests


def send(text):
    url = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
    if not url:
        raise RuntimeError("SLACK_WEBHOOK_URL 이 필요합니다 (.env 또는 GitHub Secrets)")
    resp = requests.post(
        url,
        json={"text": text, "mrkdwn": True, "unfurl_links": False},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.text