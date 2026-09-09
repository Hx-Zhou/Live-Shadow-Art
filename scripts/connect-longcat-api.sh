#!/usr/bin/env bash
set -euo pipefail

ssh_host="${LONGCAT_SSH_HOST:-dev-modelarts.cn-southwest-2.huaweicloud.com}"
ssh_port="${LONGCAT_SSH_PORT:-32584}"
ssh_user="${LONGCAT_SSH_USER:-ma-user}"
key_file="${LONGCAT_SSH_KEY:-${1:-}}"
local_port="${LONGCAT_LOCAL_API_PORT:-8010}"
remote_port="${LONGCAT_REMOTE_API_PORT:-8010}"
remote_ensure="${LONGCAT_REMOTE_ENSURE_SCRIPT:-/home/ma-user/work/longcat_deploy/ensure_api.sh}"
known_hosts_file="${LONGCAT_SSH_KNOWN_HOSTS_FILE:-/dev/null}"

if [[ -z "${key_file}" || ! -r "${key_file}" ]]; then
  printf 'Usage: %s /absolute/path/to/KeyPair-2133.pem\n' "$0" >&2
  printf 'Or set LONGCAT_SSH_KEY to the readable private-key path.\n' >&2
  exit 2
fi

ssh_options=(
  -o StrictHostKeyChecking=no
  -o "UserKnownHostsFile=${known_hosts_file}"
  -o ConnectTimeout=15
  -i "${key_file}"
  -p "${ssh_port}"
)
destination="${ssh_user}@${ssh_host}"

printf 'Ensuring the persistent LongCat LoRA API is ready on the powered-on server...\n'
ssh "${ssh_options[@]}" "${destination}" "bash ${remote_ensure}"

printf 'Opening http://127.0.0.1:%s -> remote LoRA API. Keep this terminal open.\n' \
  "${local_port}"
exec ssh "${ssh_options[@]}" \
  -N \
  -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -L "${local_port}:127.0.0.1:${remote_port}" \
  "${destination}"
