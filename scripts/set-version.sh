#!/usr/bin/env bash

set -euo pipefail

readonly VERSION_PATTERN='^[0-9]+\.[0-9]+\.[0-9]+([-+].*)?$'

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
readonly PYPROJECT="${root}/pyproject.toml"

fail() {
  printf '%s\n' "$1" >&2
  exit 1
}

project_version() {
  awk '
    /^\[/ { in_project = ($0 == "[project]") }
    in_project && /^version = "/ {
      match($0, /"[^"]*"/)
      print substr($0, RSTART + 1, RLENGTH - 2)
      exit
    }
  ' "${PYPROJECT}"
}

replace_project_version() {
  local wanted=$1
  local scratch
  scratch=$(mktemp "${TMPDIR:-/tmp}/fmvcore-version-XXXXXX")

  awk -v v="${wanted}" '
    /^\[/ { in_project = ($0 == "[project]") }
    in_project && /^version = "/ { print "version = \"" v "\""; done = 1; next }
    { print }
    END { if (!done) exit 1 }
  ' "${PYPROJECT}" >"${scratch}" || fail "no [project] version in ${PYPROJECT}"

  cat "${scratch}" >"${PYPROJECT}"
  rm -f "${scratch}"
}

main() {
  local wanted=${1:?version required}

  [[ ${wanted} =~ ${VERSION_PATTERN} ]] || fail "not a version: ${wanted}"
  [[ -n $(project_version) ]] || fail "no [project] version in ${PYPROJECT}"

  replace_project_version "${wanted}"

  local written
  written=$(project_version)
  [[ ${written} == "${wanted}" ]] || fail "wanted ${wanted} in ${PYPROJECT}, found ${written}"

  (cd "${root}" && uv lock)

  printf 'version set to %s\n' "${written}"
}

main "$@"
