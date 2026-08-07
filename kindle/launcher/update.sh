#!/bin/sh
set -eu

UPDATE_SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd -P)
. "$UPDATE_SCRIPT_DIR/common.sh"

display_result=0
if [ "${1:-}" = "--display" ]; then
    display_result=1
elif [ "$#" -ne 0 ]; then
    kb_log "usage: update.sh [--display]"
    exit 2
fi

finish() {
    message=$1
    code=$2
    kb_log "$message"
    if [ "$display_result" -eq 1 ]; then
        kb_show_message "$message" || true
    fi
    exit "$code"
}

base_url_file=$KB_APP_ROOT/config/base-url
if [ ! -r "$base_url_file" ]; then
    finish "Update URL is not configured" 2
fi
IFS= read -r base_url < "$base_url_file" || finish "Update URL is unreadable" 2
case "$base_url" in
    https://*) ;;
    *) finish "Update URL must use HTTPS" 2 ;;
esac
case "$base_url" in
    *[!A-Za-z0-9._~:/?#\[\]@!$\&\'\(\)*+,\;=%-]*)
        finish "Update URL contains unsupported characters" 2
        ;;
esac
base_url=${base_url%/}

download() {
    download_url=$1
    download_path=$2
    download_limit=$3
    download_raw "$download_url" "$download_path" "$download_limit" || return 1
    [ -f "$download_path" ] && [ ! -L "$download_path" ] || return 1
    download_size=$(wc -c < "$download_path" | tr -d ' ')
    case "$download_size" in
        ''|*[!0-9]*) return 1 ;;
    esac
    if [ "$download_size" -gt "$download_limit" ]; then
        rm -f "$download_path"
        return 1
    fi
    return 0
}

sha256_file() {
    sha_tool=$(kb_find_command sha256sum 2>/dev/null || true)
    if [ -n "$sha_tool" ]; then
        "$sha_tool" "$1" | awk '{print $1}'
        return
    fi
    if [ -x /bin/busybox ]; then
        /bin/busybox sha256sum "$1" | awk '{print $1}'
        return
    fi
    return 1
}

valid_sha256() {
    [ "${#1}" -eq 64 ] || return 1
    case "$1" in
        *[!0-9a-f]*) return 1 ;;
    esac
    return 0
}

json_string() {
    json_key=$1
    json_file=$2
    tr -d '\r\n' < "$json_file" |
        sed -n "s/.*\"$json_key\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/p"
}

json_integer() {
    json_key=$1
    json_file=$2
    tr -d '\r\n' < "$json_file" |
        sed -n "s/.*\"$json_key\"[[:space:]]*:[[:space:]]*\([0-9][0-9]*\).*/\1/p"
}

literal_count() {
    literal=$1
    literal_file=$2
    awk -v needle="$literal" '
        { text = text $0 }
        END {
            count = 0
            while ((position = index(text, needle)) > 0) {
                count++
                text = substr(text, position + length(needle))
            }
            print count
        }
    ' "$literal_file"
}

manifest_page_size() {
    manifest_page_id=$1
    manifest_page_path=$2
    manifest_page_sha=$3
    sed -n \
        "s|.*{\"byte_size\":\([0-9][0-9]*\),\"height\":1448,\"page_id\":\"$manifest_page_id\",\"path\":\"$manifest_page_path\",\"sha256\":\"$manifest_page_sha\",\"width\":1072}.*|\1|p" \
        "$stage/.manifest-compact"
}

png_metadata() {
    png_file=$1
    od_tool=$(kb_find_command od 2>/dev/null || true)
    [ -n "$od_tool" ] || return 1
    png_octets=$("$od_tool" -An -tu1 -N26 "$png_file" 2>/dev/null) || return 1
    set -- $png_octets
    [ "$#" -eq 26 ] || return 1
    [ "$1" -eq 137 ] && [ "$2" -eq 80 ] && [ "$3" -eq 78 ] && \
        [ "$4" -eq 71 ] && [ "$5" -eq 13 ] && [ "$6" -eq 10 ] && \
        [ "$7" -eq 26 ] && [ "$8" -eq 10 ] || return 1
    [ "$9" -eq 0 ] && [ "${10}" -eq 0 ] && [ "${11}" -eq 0 ] && \
        [ "${12}" -eq 13 ] && [ "${13}" -eq 73 ] && [ "${14}" -eq 72 ] && \
        [ "${15}" -eq 68 ] && [ "${16}" -eq 82 ] || return 1
    png_width=$((${17} * 16777216 + ${18} * 65536 + ${19} * 256 + ${20}))
    png_height=$((${21} * 16777216 + ${22} * 65536 + ${23} * 256 + ${24}))
    printf '%s %s %s %s\n' "$png_width" "$png_height" "${25}" "${26}"
}

cache_root=$KB_APP_ROOT/cache
stage=$cache_root/.stage-$$
promotion_active=0
[ ! -L "$cache_root" ] || finish "Cache root may not be a symlink" 5
[ ! -L "$cache_root/current" ] || finish "Current cache may not be a symlink" 5
[ ! -L "$cache_root/previous" ] || finish "Previous cache may not be a symlink" 5
for cache_release in "$cache_root/current" "$cache_root/previous"; do
    if [ -d "$cache_release" ] && \
       [ "$(sed -n '1p' "$cache_release/.kindle-brief-cache" 2>/dev/null || true)" != \
           kindle-brief-cache-v1 ]; then
        finish "Refusing unowned cache release" 5
    fi
done
mkdir -p "$cache_root"
if [ ! -e "$cache_root/current" ] && kb_owned_cache_dir "$cache_root/previous"; then
    mv "$cache_root/previous" "$cache_root/current" || \
        finish "Could not recover previous dashboard cache" 6
fi
[ ! -e "$stage" ] || finish "Update staging path collision" 5
mkdir -p "$stage/pages"
cleanup_update() {
    if [ "$promotion_active" -eq 1 ] && [ ! -e "$cache_root/current" ] && \
       [ -d "$cache_root/previous" ]; then
        mv "$cache_root/previous" "$cache_root/current" 2>/dev/null || true
    fi
    rm -rf "$stage" 2>/dev/null || true
}
trap cleanup_update EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

download_tool=
if download_tool=$(kb_find_command curl 2>/dev/null); then
    download_raw() {
        "$download_tool" -fL --proto '=https' --proto-redir '=https' \
            --connect-timeout 15 --max-time 90 \
            --max-filesize "$3" -o "$2" "$1"
    }
elif download_tool=$(kb_find_command wget 2>/dev/null); then
    finish "Refusing wget because HTTPS-only redirects cannot be enforced" 3
else
    finish "No HTTPS-safe curl downloader found" 3
fi

current_url=$base_url/profiles/kt5/current.json
download "$current_url" "$stage/current.json" 262144 || \
    finish "Could not download bounded update pointer" 4

current_schema=$(json_integer schema_version "$stage/current.json")
profile_id=$(json_string profile_id "$stage/current.json")
model_code=$(json_string model_code "$stage/current.json")
release_id=$(json_string release_id "$stage/current.json")
manifest_sha=$(json_string manifest_sha256 "$stage/current.json")
sums_sha=$(json_string sha256sums_sha256 "$stage/current.json")
[ "$(literal_count '"schema_version"' "$stage/current.json")" -eq 1 ] && \
    [ "$current_schema" = 1 ] || finish "Unsupported update pointer schema" 5
[ "$profile_id" = "kt5" ] || finish "Update profile is not kt5" 5
[ "$model_code" = "KT5" ] || finish "Update model is not KT5" 5
valid_sha256 "$release_id" || finish "Invalid release identifier" 5
valid_sha256 "$manifest_sha" || finish "Missing manifest checksum" 5
valid_sha256 "$sums_sha" || finish "Missing page-checksum digest" 5

release_url=$base_url/profiles/kt5/releases/$release_id
download "$release_url/manifest.json" "$stage/manifest.json" 1048576 || \
    finish "Could not download bounded release manifest" 4
download "$release_url/SHA256SUMS" "$stage/SHA256SUMS" 65536 || \
    finish "Could not download bounded page checksums" 4

actual_manifest_sha=$(sha256_file "$stage/manifest.json") || \
    finish "No SHA-256 implementation found" 3
[ "$actual_manifest_sha" = "$manifest_sha" ] || finish "Manifest checksum mismatch" 5
actual_sums_sha=$(sha256_file "$stage/SHA256SUMS") || \
    finish "No SHA-256 implementation found" 3
[ "$actual_sums_sha" = "$sums_sha" ] || finish "Page-checksum digest mismatch" 5

manifest_profile=$(json_string profile_id "$stage/manifest.json")
manifest_model=$(json_string model_code "$stage/manifest.json")
manifest_schema=$(json_integer schema_version "$stage/manifest.json")
manifest_release=$(json_string release_id "$stage/manifest.json")
[ "$(literal_count '"schema_version"' "$stage/manifest.json")" -eq 1 ] && \
    [ "$manifest_schema" = 1 ] || finish "Unsupported manifest schema" 5
[ "$(literal_count '"release_id"' "$stage/manifest.json")" -eq 1 ] && \
    [ "$manifest_release" = "$release_id" ] || finish "Manifest release mismatch" 5
[ "$manifest_profile" = "kt5" ] || finish "Manifest profile is not kt5" 5
[ "$manifest_model" = "KT5" ] || finish "Manifest model is not KT5" 5
tr -d '\r\n\t ' < "$stage/manifest.json" > "$stage/.manifest-compact"
[ "$(literal_count '"profile":' "$stage/.manifest-compact")" -eq 1 ] || \
    finish "Manifest must contain one device profile" 5
manifest_profile_contract=$(sed -n \
    's|.*"profile":{"grayscale_bits":4,"height":1448,"model":"[^"]*","model_code":"KT5","profile_id":"kt5","rotation":0,"width":1072}.*|valid|p' \
    "$stage/.manifest-compact")
[ "$manifest_profile_contract" = valid ] || \
    finish "Manifest device profile is unsupported" 5
[ "$(literal_count '"page_id":' "$stage/.manifest-compact")" -eq 5 ] || \
    finish "Manifest must describe exactly five pages" 5

seen_pages=' '
page_total=0
while IFS= read -r checksum_line || [ -n "$checksum_line" ]; do
    checksum=${checksum_line%%  *}
    relative_path=${checksum_line#*  }
    [ "$relative_path" != "$checksum_line" ] || finish "Malformed SHA256SUMS" 5
    valid_sha256 "$checksum" || finish "Malformed page checksum" 5
    case "$relative_path" in
        pages/home.png) page_id=home ;;
        pages/weather.png) page_id=weather ;;
        pages/f1.png) page_id=f1 ;;
        pages/morning-brief.png) page_id=morning-brief ;;
        pages/headlines.png) page_id=headlines ;;
        *) finish "Unsafe or unexpected page path" 5 ;;
    esac
    case "$seen_pages" in
        *" $relative_path "*) finish "Duplicate page checksum" 5 ;;
    esac
    seen_pages="$seen_pages$relative_path "
    page_total=$((page_total + 1))
    expected_page_bytes=$(manifest_page_size "$page_id" "$relative_path" "$checksum")
    case "$expected_page_bytes" in
        ''|*[!0-9]*|0) finish "Invalid manifest page metadata" 5 ;;
    esac
    [ "$expected_page_bytes" -le 8388608 ] || finish "Manifest page is too large" 5
    download "$release_url/$relative_path" "$stage/$relative_path" 8388608 || \
        finish "Could not download bounded $relative_path" 4
    actual_page_sha=$(sha256_file "$stage/$relative_path") || \
        finish "No SHA-256 implementation found" 3
    [ "$actual_page_sha" = "$checksum" ] || finish "Page checksum mismatch" 5
    actual_page_bytes=$(wc -c < "$stage/$relative_path" | tr -d ' ')
    [ "$actual_page_bytes" = "$expected_page_bytes" ] || \
        finish "Page byte size does not match manifest" 5
    page_png_metadata=$(png_metadata "$stage/$relative_path") || \
        finish "Page is not a supported PNG" 5
    set -- $page_png_metadata
    [ "$#" -eq 4 ] && [ "$1" -eq 1072 ] && [ "$2" -eq 1448 ] && \
        [ "$3" -eq 8 ] && [ "$4" -eq 0 ] || \
        finish "Page PNG dimensions or type are unsupported" 5
done < "$stage/SHA256SUMS"
[ "$page_total" -eq 5 ] || finish "Release must contain exactly five pages" 5
rm -f "$stage/.manifest-compact"

printf '%s\n' "$release_id" > "$stage/RELEASE_ID"
printf '%s\n' kindle-brief-cache-v1 > "$stage/.kindle-brief-cache"
if [ -d "$cache_root/previous" ]; then
    rm -rf "$cache_root/previous"
fi
if [ -d "$cache_root/current" ]; then
    promotion_active=1
    if ! mv "$cache_root/current" "$cache_root/previous"; then
        promotion_active=0
        finish "Could not rotate current dashboard cache" 5
    fi
fi
if ! mv "$stage" "$cache_root/current"; then
    if [ "$promotion_active" -eq 1 ] && [ ! -e "$cache_root/current" ]; then
        if mv "$cache_root/previous" "$cache_root/current"; then
            promotion_active=0
        else
            finish "Update promotion failed and rollback was unsuccessful" 6
        fi
    fi
    finish "Could not promote verified dashboard update" 5
fi
promotion_active=0
trap - EXIT HUP INT TERM

finish "Dashboard update installed" 0
