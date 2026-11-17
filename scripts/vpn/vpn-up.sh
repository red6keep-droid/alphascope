#!/usr/bin/env bash
# 집 공유기(ipTIME) L2TP/IPsec VPN에 접속하고, 집 IP 로 보낼 요청용 주소를 GITHUB_OUTPUT으로 넘긴다.
# 원본 = 유튜브 수집 저장소(red9keep/News-sub) scripts/vpn-up.sh 를 그대로 옮김 (2026-11-17). 고치면 양쪽 같이.
# swanctl 판 (11-13, 이전 ipsec(stroke) 판에서 옮김). Ubuntu 26.04 strongSwan엔 옛 `ipsec` 명령(stroke)이 없어서
# charon-systemd + swanctl(vici)로 IPsec을 연다. 24.04에서도 같은 패키지로 동작한다.
# L2TP(xl2tpd) · PPP · 정책 경로 · 집 IP 확인은 이전과 같다.
#
# 필요한 환경 변수: VPN_SERVER(호스트 이름) VPN_PSK VPN_USER VPN_PASSWORD
# 출력: ok=true, ip=<ppp0 주소>  (실패하면 ok=false, 집 IP 받기는 지난 값을 그대로 둔다)
set -uo pipefail

out() { [ -n "${GITHUB_OUTPUT:-}" ] && echo "$1" >> "$GITHUB_OUTPUT"; }
fail() { echo "::error::VPN 연결 실패 - $1"; out "ok=false"; exit 1; }

for v in VPN_SERVER VPN_PSK VPN_USER VPN_PASSWORD; do
  [ -n "${!v:-}" ] || fail "Secret $v 가 비어 있음"
done

echo "[1/6] 패키지 설치 ($(. /etc/os-release; echo "$PRETTY_NAME"))"
export DEBIAN_FRONTEND=noninteractive
# strongswan 묶음(옛 starter 포함) 대신 charon-systemd · swanctl만 깐다 (두 데몬이 UDP 500을 다투지 않게)
apt-get update -qq >/dev/null && apt-get install -y -qq charon-systemd strongswan-swanctl xl2tpd ppp >/dev/null \
  || fail "charon-systemd · swanctl · xl2tpd 설치 실패"

echo "[2/6] 공유기 주소 확인 (DDNS)"
SERVER_IP=$(getent ahostsv4 "$VPN_SERVER" | awk 'NR==1{print $1}')
[ -n "$SERVER_IP" ] || fail "호스트 이름을 IP로 바꾸지 못함 (DDNS 확인)"
echo "::add-mask::$SERVER_IP"

echo "[3/6] 설정 파일 작성"
mkdir -p /etc/swanctl/conf.d
# 비밀키는 base64(0s…)로 넣어 따옴표 · 특수문자 문제를 없앤다
PSK_B64=$(printf '%s' "$VPN_PSK" | base64 -w0)
cat > /etc/swanctl/conf.d/home.conf <<EOF
connections {
  home {
    version = 1
    remote_addrs = $SERVER_IP
    # 오래된 공유기도 받아들이도록 약한 조합까지 함께 제안한다 (이전과 같은 목록)
    proposals = aes256-sha1-modp2048,aes128-sha1-modp2048,aes256-sha1-modp1024,aes128-sha1-modp1024,3des-sha1-modp1024
    rekey_time = 8h
    keyingtries = 1
    local {
      auth = psk
    }
    remote {
      auth = psk
    }
    children {
      home {
        mode = transport
        local_ts = dynamic[udp/1701]
        remote_ts = dynamic[udp/1701]
        esp_proposals = aes256-sha1,aes128-sha1,3des-sha1
        rekey_time = 1h
        start_action = none
      }
    }
  }
}
secrets {
  ike-home {
    secret = 0s$PSK_B64
  }
}
EOF
chmod 600 /etc/swanctl/conf.d/home.conf
# 공유기가 응답하지 않을 때 8분씩 기다리지 않도록 재전송 횟수를 줄인다 (약 30초)
cat > /etc/strongswan.d/zz-retransmit.conf <<EOF
charon {
  retransmit_tries = 3
}
charon-systemd {
  retransmit_tries = 3
}
EOF

cat > /etc/xl2tpd/xl2tpd.conf <<EOF
[lac home]
lns = $SERVER_IP
ppp debug = no
pppoptfile = /etc/ppp/options.l2tpd.client
length bit = yes
EOF

cat > /etc/ppp/options.l2tpd.client <<EOF
ipcp-accept-local
ipcp-accept-remote
refuse-eap
noccp
noauth
mtu 1280
mru 1280
noipdefault
nodefaultroute
connect-delay 5000
name "$VPN_USER"
password "$VPN_PASSWORD"
# 인증 방식 · 거절 지점을 기록에 남긴다 (pppd는 debug에서도 암호를 가려서 적는다)
debug
EOF
chmod 600 /etc/ppp/options.l2tpd.client

echo "[4/6] IPsec 연결 (swanctl)"
# 재전송 설정을 읽도록 데몬을 다시 띄운다. 서비스 이름은 배포판마다 다르다
systemctl restart strongswan 2>/dev/null || systemctl restart strongswan-swanctl 2>/dev/null \
  || fail "strongSwan(charon-systemd) 서비스를 띄우지 못함"
for _ in $(seq 1 10); do
  swanctl --stats >/dev/null 2>&1 && break
  sleep 1
done
swanctl --load-all >/tmp/swanctl-load.log 2>&1 || {
  grep -vi "secret" /tmp/swanctl-load.log | tail -n 15
  fail "swanctl 설정 읽기 실패"
}
swanctl --initiate --child home --timeout 60 >/tmp/ipsec.log 2>&1
# 실패해도 0으로 끝나는 경우를 피해 실제 연결 상태로 판단한다
if ! swanctl --list-sas --ike home 2>/dev/null | grep -q "INSTALLED"; then
  echo "--- IPsec 기록 (공유기 주소는 *** 로 가려짐) ---"
  grep -vi "psk\|secret" /tmp/ipsec.log | tail -n 25
  if grep -q "received" /tmp/ipsec.log; then
    fail "IPsec 협상 실패 - 공유기가 응답은 함 (비밀키 · 암호화 방식 확인)"
  else
    fail "IPsec 협상 실패 - 공유기가 전혀 응답하지 않음 (공유기 L2TP · IPSec 실행 여부, 포트 UDP 500/4500 확인)"
  fi
fi

echo "[5/6] L2TP 로그인"
mkdir -p /var/run/xl2tpd
systemctl restart xl2tpd || service xl2tpd restart
sleep 2
echo "c home" > /var/run/xl2tpd/l2tp-control
LOCAL_IP=""
for _ in $(seq 1 30); do
  LOCAL_IP=$(ip -4 -o addr show ppp0 2>/dev/null | awk '{print $4}' | cut -d/ -f1)
  [ -n "$LOCAL_IP" ] && break
  sleep 1
done
[ -n "$LOCAL_IP" ] || {
  echo "--- pppd 기록 (계정 이름 길이: ${#VPN_USER}자, 암호 길이: ${#VPN_PASSWORD}자) ---"
  journalctl --no-pager -n 60 2>/dev/null | grep -E "pppd|xl2tpd" | grep -viE "password|secret"
  fail "L2TP 로그인 실패 (VPN 계정 · 암호 확인)"
}

# VPN 쪽 주소에서 출발하는 요청만 ppp0으로 내보낸다
ip route replace default dev ppp0 table 100
ip rule add from "$LOCAL_IP" table 100 priority 100

echo "[6/6] 집 IP로 나가는지 확인"
EGRESS=$(curl -s --max-time 20 --interface "$LOCAL_IP" https://api.ipify.org || true)
[ -n "$EGRESS" ] && echo "::add-mask::$EGRESS"
[ -n "$EGRESS" ] || fail "VPN으로 인터넷에 나가지 못함 (공유기 인터넷 · 경로 확인)"
[ "$EGRESS" = "$SERVER_IP" ] || fail "나가는 IP가 공유기 IP와 다름 (DDNS가 옛 IP를 가리키는지 확인)"

echo "VPN 연결 완료: 이 주소에 묶은 요청만 집 IP로 나갑니다"
out "ok=true"
out "ip=$LOCAL_IP"
