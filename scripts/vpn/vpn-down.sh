#!/usr/bin/env bash
# 집 공유기 VPN 연결 끊기. 실패해도 작업 결과에는 영향이 없다.
# 이전 ipsec 판 · 지금 swanctl 판 둘 다 끊는다. 없는 명령은 조용히 넘어간다
echo "d home" > /var/run/xl2tpd/l2tp-control 2>/dev/null
ipsec down home >/dev/null 2>&1
swanctl --terminate --ike home --timeout 10 >/dev/null 2>&1
exit 0
