#!/bin/bash
# End-to-end smoke test for tamakun-saas at operation.tamakun.sa.
# Tests origin directly (--resolve to bypass Cloudflare proxy) so we
# verify the actual deployment, not the CDN cache.
#
# Run on the deployed host (or anywhere with network access to the
# server's public IP):
#   bash deploy/smoke_test.sh
#
# Override the server IP via env var if needed:
#   ORIGIN_IP=1.2.3.4 bash deploy/smoke_test.sh

set -u
BASE="https://operation.tamakun.sa"
ORIGIN_IP="${ORIGIN_IP:-37.27.130.230}"
RESOLVE="operation.tamakun.sa:443:${ORIGIN_IP}"
COOKIE_JAR="/tmp/tamakun_smoke_cookies.txt"
rm -f "$COOKIE_JAR"

PASS=0
FAIL=0

green() { printf '\033[32m%s\033[0m' "$1"; }
red()   { printf '\033[31m%s\033[0m' "$1"; }

check() {
    local name="$1" expected="$2" actual="$3"
    if [ "$actual" = "$expected" ]; then
        printf '  [%s] %-50s (got %s)\n' "$(green PASS)" "$name" "$actual"
        PASS=$((PASS+1))
    else
        printf '  [%s] %-50s expected %s, got %s\n' "$(red FAIL)" "$name" "$expected" "$actual"
        FAIL=$((FAIL+1))
    fi
}

contains() {
    local name="$1" needle="$2" file="$3"
    if grep -qF -- "$needle" "$file" 2>/dev/null; then
        printf '  [%s] %-50s (contains %s)\n' "$(green PASS)" "$name" "$(echo "$needle" | head -c 30)"
        PASS=$((PASS+1))
    else
        printf '  [%s] %-50s missing: %s\n' "$(red FAIL)" "$name" "$(echo "$needle" | head -c 30)"
        FAIL=$((FAIL+1))
    fi
}

cget() {
    curl -sk --max-time 15 --resolve "$RESOLVE" "$BASE$1" -o "$2" -b "$COOKIE_JAR" -c "$COOKIE_JAR" -w "%{http_code}"
}
cpost_form() {
    curl -sk --max-time 30 --resolve "$RESOLVE" "$BASE$1" -o "$2" -b "$COOKIE_JAR" -c "$COOKIE_JAR" \
        -w "%{http_code}" -X POST --data-urlencode "$3" --data-urlencode "$4" -H "Referer: $BASE"
}

echo "=== A. Public pages (anonymous) ==="
RC=$(cget / /tmp/r_root); check "GET /" 200 "$RC"
contains "Landing has Arabic title" "تمكّن" /tmp/r_root
contains "Landing links analysis"   "/analysis" /tmp/r_root
contains "Landing links operations" "/operations" /tmp/r_root

RC=$(cget /admin/login /tmp/r_login); check "GET /admin/login" 200 "$RC"
contains "Login form has email field" 'name="email"' /tmp/r_login
contains "Login form has password field" 'name="password"' /tmp/r_login

RC=$(cget /static/css/style.css /tmp/r_css); check "GET /static/css/style.css" 200 "$RC"
RC=$(cget /static/js/dashboard.js /tmp/r_js); check "GET /static/js/dashboard.js" 200 "$RC"

RC=$(cget /analysis /tmp/r_analysis); check "GET /analysis" 200 "$RC"
RC=$(cget /operations /tmp/r_operations); check "GET /operations" 200 "$RC"

echo
echo "=== B. Auth flow ==="
RC=$(cpost_form /admin/login /tmp/r_badlogin "email=nope@x.sa" "password=wrong")
check "POST /admin/login (bad creds)" 200 "$RC"
contains "Bad creds shows error" "غير صحيحة" /tmp/r_badlogin

rm -f "$COOKIE_JAR"
RC=$(cpost_form /admin/login /tmp/r_okhdrs "email=m.alshathri@tamakun.sa" "password=Tamakun@2024")
check "POST /admin/login (good creds)" 302 "$RC"

echo
echo "=== C. Authenticated admin pages ==="
RC=$(cget /admin /tmp/r_admin); check "GET /admin (with session)" 200 "$RC"
contains "Admin home shows links to stores" "/admin/stores" /tmp/r_admin

RC=$(cget /admin/stores /tmp/r_stores); check "GET /admin/stores" 200 "$RC"
RC=$(cget /admin/sku-rules /tmp/r_sku); check "GET /admin/sku-rules" 200 "$RC"
RC=$(cget /admin/password /tmp/r_pw); check "GET /admin/password" 200 "$RC"

RC=$(cget /dashboard/bestshield /tmp/r_bs); check "GET /dashboard/bestshield" 200 "$RC"
RC=$(cget /dashboard/shabah    /tmp/r_sh); check "GET /dashboard/shabah" 200 "$RC"
RC=$(cget /dashboard/alarabi   /tmp/r_aa); check "GET /dashboard/alarabi" 200 "$RC"

echo
echo "=== D. External DB integration (via API) ==="
for brand in bestshield shabah alarabi; do
    RC=$(curl -sk --max-time 60 --resolve "$RESOLVE" \
            -X POST "$BASE/api/fetch-db" \
            -b "$COOKIE_JAR" -F "brand_key=$brand" -F "status_values=" \
            -o "/tmp/r_fetch_$brand" -w "%{http_code}")
    check "POST /api/fetch-db ($brand)" 200 "$RC"
    if grep -q '"success":true' "/tmp/r_fetch_$brand" 2>/dev/null; then
        printf '  [%s] %-50s (success:true in body)\n' "$(green PASS)" "Body confirms success ($brand)"
        PASS=$((PASS+1))
    else
        printf '  [%s] %-50s body head: %s\n' "$(red FAIL)" "Body confirms success ($brand)" "$(head -c 200 /tmp/r_fetch_$brand)"
        FAIL=$((FAIL+1))
    fi
done

echo
echo "=== E. Logout ==="
RC=$(cget /admin/logout /tmp/r_lo); check "GET /admin/logout" 302 "$RC"
RC=$(cget /admin /tmp/r_admin_after); check "GET /admin (no session)" 302 "$RC"

echo
echo "=== F. Through Cloudflare (public DNS) ==="
PUB=$(curl -sk --max-time 15 "$BASE/" -o /tmp/r_pub -w "%{http_code}")
check "Public CF GET /" 200 "$PUB"
contains "Public response is the app" "تمكّن" /tmp/r_pub

echo
echo "=== Summary ==="
printf "  PASS: %d, FAIL: %d\n" "$PASS" "$FAIL"

# Cleanup
rm -f "$COOKIE_JAR" /tmp/r_*

[ "$FAIL" -eq 0 ]
