#!/usr/bin/env bash

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

createDatabase () {
  local dbName="$1"
  local resetDB="$2"
  local dbPass="${MYSQL_ROOT_PASSWORD:-root}"
  local routinesSQLFile="${SCRIPT_DIR}/dump/default_routines.sql"
  local schemaSQLFile="${SCRIPT_DIR}/dump/default_schema.sql"
  local createStatement="CREATE DATABASE IF NOT EXISTS \`${dbName}\` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
  if [ "${resetDB}" == true ] || [ "${resetDB}" == 1 ]; then
    createStatement="DROP DATABASE IF EXISTS \`${dbName}\`; ${createStatement}"
  fi

  echo "$0: initializing database \`${dbName}\` (reset=${resetDB})"
  # shellcheck disable=SC2154
  mysql -uroot -p"${dbPass}" --execute="${createStatement}" --force
  for f in "${schemaSQLFile}" "${routinesSQLFile}"; do
    trap 'echo "$0: $f execution failed"' ERR
    # shellcheck disable=SC2154
    case "$f" in
      *.sql) echo "$0: running $f"; mysql -uroot -p"${dbPass}" --database="${dbName}" --force < "$f" ;;
      *)     echo "$0: ignoring $f" ;;
    esac
  done
}

initDatabases () {
  local numDatabases="$1"
  local resetMavenDB="$2"
  echo "$0: initializing databases"
  # Initialize the main dev database.
  createDatabase "maven" "${resetMavenDB}"
  # Initialize a simple test database
  createDatabase "test-maven" true
  echo
  for i in $(seq 0 "${numDatabases}"); do
    # Initialize test databases for when we run distributed tests.
    dbName="test-${i}-maven"
    trap 'echo "$0: error initializing \`${dbName}\`"' ERR
    createDatabase "${dbName}" true
  done
}

main () {
  local numDatabases="$1"
  local resetMavenDB="$2"
  trap 'RC=1' ERR
  initDatabases "${numDatabases}" "${resetMavenDB}"
  return "${RC:-0}"
}

main "${NUM_TEST_DATABASES:-10}" "${RESET_MAVEN_DB:-false}"
