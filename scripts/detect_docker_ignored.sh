#!/bin/bash

# The context and ignore are explicitly provided to avoid having to perform an
# actaual build. We simulate the the same environment that will be used for
# building by moving to the context dir and specifying the .dockerignore file,
# which may be nested in the context dir. This is often the case for monorepos
# or multi-deployment repos.

help() {
  printf "\n🐳 Usage: detect_docker_ignored.sh [context_dir] [docker_ignore_path]\n\n"
  printf "context_dir: Path to the directory that will be used as the build context\n"
  printf "If not provided, [current directory] will be used\n"
}

# print help if --help is provided
if [ "$1" == "--help" ]; then
  help
  exit 0
fi

# path that will be used as the build context
# defaults to the current directory
context_dir="${1:-.}"

tmp_on_disk_file_path=$(mktemp)
tmp_in_container_file_list=$(mktemp)

# move to the context dir
# this gives us matching relative paths for the files to be comm'ed
cd "./$context_dir" || exit

# recursivly gather a list of all files in the context dir
# ensure paths are lexically sorted so diff 
find . -type f | sed 's|^\./||' | sort > "$tmp_on_disk_file_path"

# build a dummy container containg all files that pass through the .dockerignore
# filter, if one exists. This container prints the list of files that were
# copied if run with no overrides.
docker image build --no-cache -t build-context -f - . <<EOF
FROM busybox
WORKDIR /build-context
COPY . .
CMD find .
EOF

# run the container and gather the list of files that had been copied
# rm the container after it has finished running 🧹
docker container run \
  --rm build-context \
  /bin/sh -c \
    "find -type f | sed 's|^\./||'" | sort  > "$tmp_in_container_file_list"

# files present on disk and  not in container
ignored_files=$(comm -23 "$tmp_on_disk_file_path" "$tmp_in_container_file_list" | sort)
ignored_files_count=$(echo "$ignored_files" | wc -l | tr -d ' ')

# This is a list of all files that are expected to exist within the build
# context but not in the built image. These files are not copied to the image
# because they match patterns found in the .dockerignore file located within the
# supplied context. 
# 
# If you arrived here because this script produced an error on your MR, you will
# need to review the output and likely update the .dockerignore file to reflect
# the outcome you desire. 
#
# Recommendations:
# 1. If you are adding a new python package, it is likely ignored by default.
#    Add your package path to the .dockerignore file following the same pattern
#    as the other packages. In this case you do not need to make a change in the
#    list below.
# 2. If you have added any auxiliary file that is not expected to appear in the
#    production runtime image, you must add a regex pattern to the list below
#    that matches your file(s). You must be certain that your file could never
#    be accessed during runtime before adding to this list. There are multiple
#    runtime paths that import pytest files (especially in the admin images) so
#    it cannot be assumed that all files in the */pytests/* directory are safe
#    to ignore. Until a tool is provided to ascertain that dependency information
#    for you, you can leverage `dep-tree` starting at the application roots and
#    grep for your files. Note this is also not perfect because there are
#    runtime imports littered about... These are not reachable by `dep-tree` and
#    likely must be discovered by "letting Jesus take the wheel".... godspeed...
#    https://github.com/gabotechs/dep-tree
#
# Below is the list of regex patterns that are allowed to not appear in the
# built image.
#   - Please keep in alphabetical order
#   - Each line shoud have the format `^.....$|\` where .... is the regex pattern
#     to your file(s).
#   - Please keep in alphabetical order

allowed_ignored_patterns="^$|\
^.*__pycache__.*|\
^.*\.DS_Store|\
^.*\.log$|\
^.*\.md$|\
^.*\.tmp|\
^.*report\.xml|\
^\..*$|\
^\.run\/.*\.xml$|\
^activity\/pytests\/.*$|\
^admin\/pytests\/.*$|\
^admin\/tests\/.*$|\
^application_dev\.py$|\
^appointments(.*)\/pytests\/.*$|\
^airflow(.*)\/pytests\/.*$|\
^assessments\/pytests\/.*$|\
^audit_log\/pytests\/.*$|\
^authn(.*)\/pytests\/.*$|\
^authz\/pytests\/.*$|\
^bms\/pytests\/.*$|\
^braze\/pytests\/.*$|\
^build-scripts\/.*$|\
^caching\/pytests\/.*$|\
^care_advocates\/pytests\/.*$|\
^clinical_documentation\/pytests\/.*$|\
^common\/.*\/pytests\/.*$|\
^cost_breakdown\/pytests\/.*$|\
^data_admin\/pytests\/.*$|\
^deployment\/k8s\/.*$|\
^direct_payment\/.*\/pytests\/.*$|\
^Dockerfile$|\
^docs\/.*$|\
^dosespot\/pytests\/.*$|\
^eligibility\/pytests\/.*$|\
^frosted_flakes.py$|\
^geography\/pytests\/.*$|\
^health\/pytests\/.*$|\
^incentives\/pytests\/.*$|\
^l10n\/pytests\/.*$|\
^learn\/pytests\/.*$|\
^Makefile$|\
^members\/pytests\/.*$|\
^messaging\/pytests\/.*$|\
^mpractice\/pytests\/.*$|\
^payer_accumulator\/pytests\/.*$|\
^payments\/pytests\/.*$|\
^personalization\/pytests\/.*$|\
^phone_support\/pytests\/.*$|\
^preferences\/pytests\/.*$|\
^provider_matching\/pytests\/.*$|\
^providers\/pytests\/.*$|\
^pytest.ini$|\
^pytests\/.*$|\
^scripts\/.*$|\
^select_flaky_suites.py$|\
^search\/pytests\/.*$|\
^services\/pytests\/.*$|\
^storage\/pytests\/.*$|\
^tasks\/pytests\/.*$|\
^tests\/.*$|\
^tracks\/pytests\/.*$|\
^user_locale\/pytests\/.*$|\
^views\/pytests\/.*$|\
^wallet\/pytests\/.*$|\
^$"
# Did I mention to please keep the regex list alphabetical order?

# determine the list of files that were unexpectedly ignored in the build process
unexpected_ignored_files=$(echo "$ignored_files" | grep -E -v "$allowed_ignored_patterns")
unexpected_ignored_files_count=$(echo "$unexpected_ignored_files" | grep -c . | tr -d ' ')
printf "\nFound %s total files in build context what were not copied into container.\n" "$ignored_files_count"

# if there are any unexpected ignored files, exit with an error
if [ "$unexpected_ignored_files_count" -gt 0 ]; then
  printf "\n❗❗❗\n"
  printf "The following %s files where not expected to be ignored\n" "$unexpected_ignored_files_count"
  printf "Please review the comments found in this script for\nrecommendations on how to resolve this error.\n"
  printf "❗❗❗\n\n"
  printf "\n%s\n" "$unexpected_ignored_files"
  exit 1
else
  printf "\n✅ All files present and accounted for!\n"
  exit 0
fi
