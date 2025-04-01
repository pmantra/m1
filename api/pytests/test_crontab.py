import pathlib
import re

from tasks.owner_utils import is_service_ns_valid, is_team_ns_valid

CRONTAB_FILE = pathlib.Path(__file__).parent.parent / "cron" / "crontab"


def test_cron_task_validate_syntax():
    with open(CRONTAB_FILE, "r") as cron_file:
        cron_tasks = cron_file.readlines()

        count = 0
        match_count = 0
        for task in cron_tasks:
            # skip comment or empty lines
            if task.startswith("#") or "/root/cron-env.sh" not in task:
                continue

            match = re.search('python3 -c "(.+?)"', task, re.RegexFlag.IGNORECASE)
            if match:
                match_count = match_count + 1
                stmt = match.group().split('python3 -c "')[1][:-1]
                # now try to execute and see if there are syntax errors
                exec(stmt)
            count = count + 1

        # make sure the counts match
        assert count == match_count


def test_cron_task_owner_info():
    # if service or team info is provided then sanity check for the correctness
    with open(CRONTAB_FILE, "r") as cron_file:
        cron_tasks = cron_file.readlines()

        for task in cron_tasks:
            # skip comment or empty lines
            if task.startswith("#") or "/root/cron-env.sh" not in task:
                continue

            match = re.search(r"delay\((.+?)\)", task, re.RegexFlag.IGNORECASE)
            if match:
                team_ns_tag_specified = False
                params = match.group().split("delay(")[1][:-1].split(",")
                for p in params:
                    parts = p.strip().split("=")
                    if len(parts) == 2:
                        if parts[0] == "team_ns":
                            assert is_team_ns_valid(eval(parts[1])) is True
                            # team_ns info should be specified
                            team_ns_tag_specified = True

                        if parts[0] == "service_ns":
                            assert is_service_ns_valid(eval(parts[1])) is True

                # going forward, we won't allow tasks without owner info
                assert team_ns_tag_specified is True
