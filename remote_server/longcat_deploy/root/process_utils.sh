#!/usr/bin/env bash

read_service_pid() {
  local pid_file="$1"
  if [[ ! -r "${pid_file}" ]]; then
    return 1
  fi
  local pid
  pid="$(<"${pid_file}")"
  if [[ ! "${pid}" =~ ^[0-9]+$ ]]; then
    return 1
  fi
  printf '%s' "${pid}"
}

service_pid_matches() {
  local pid="$1"
  local expected="$2"
  if ! kill -0 "${pid}" 2>/dev/null || [[ ! -r "/proc/${pid}/cmdline" ]]; then
    return 1
  fi
  local command_line
  command_line="$(tr '\0' ' ' < "/proc/${pid}/cmdline")"
  [[ "${command_line}" == *"${expected}"* ]]
}
