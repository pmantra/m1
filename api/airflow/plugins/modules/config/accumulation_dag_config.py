"""
Payer:
    The payer enabled for the accumulation_file_generation_job
    Job for payer must be created in the "payer_accumulator.tasks.rq_payer_accumulation_file_generation.py"
Schedule:
    Data sourcing:
        The combined job is scheduled to run every day at 4pm and 11pm UTC
        Twice daily tasks will run every day at 4pm and 11pm UTC
        Daily tasks will run every day at 4pm UTC
        Weekly tasks will run at 4pm UTC on Mondays
        Biweekly tasks will run at 4pm UTC on the 1st, 15th, and 29th
    File generation:
        The combined job is scheduled to run every day at 6pm and midnight UTC
        Twice daily tasks will run every day at midnight and 6pm UTC
        Daily tasks will run every day at 6pm UTC
        Weekly tasks will run at 6pm UTC on Mondays
        Biweekly tasks will run at 6pm UTC on the 1st, 15th, and 29th
    File transfer:
        The combined job is scheduled to run every day at 12pm, 3pm, 6pm, and 9pm UTC
        Four times daily tasks will run every day at 12pm, 3pm, 6pm, and 9pm UTC
        Twice daily tasks will run every day at 12pm and 9pm UTC
        Daily tasks will run every day at 12pm UTC
        Weekly tasks will run at 12pm UTC on Mondays
        Biweekly tasks will run at 12pm UTC on the 1st, 15th, and 29th
    Process responses:
        The combined job is scheduled to run every day at 4am and 7pm UTC
        Twice daily tasks will run every day at 4am and 7pm UTC
        Daily tasks will run every day at 7pm UTC
        Weekly tasks will run at 7pm UTC on Mondays
        Biweekly tasks will run at 7pm UTC on the 1st, 15th, and 29th
Jobs:
    List of jobs to run for the payer:
        file_generation
        data_sourcing
        process_responses
        file_transfer
"""
from modules.util.scheduling_utils import Schedule

accumulation_jobs = [
    {
        "payer": "aetna",
        "job_schedules": {
            "file_generation": Schedule.DAILY,  # Previously default: DAILY
            "data_sourcing": Schedule.DAILY,
            "file_transfer": Schedule.DAILY,
        },
        "jobs": [
            "file_generation",
            "data_sourcing",
            "file_transfer",
        ],
    },
    {
        "payer": "anthem",
        "job_schedules": {
            "file_generation": Schedule.DAILY,  # Previously default: DAILY
            "data_sourcing": Schedule.DAILY,
            "process_responses": Schedule.DAILY,
            "file_transfer": Schedule.DAILY,
        },
        "jobs": [
            "file_generation",
            "data_sourcing",
            "process_responses",
            "file_transfer",
        ],
    },
    {
        "payer": "bcbs_ma",
        "job_schedules": {
            "file_generation": Schedule.WEEKLY,
            "data_sourcing": Schedule.WEEKLY,
            "process_responses": Schedule.DAILY,
            "file_transfer": Schedule.WEEKLY,
        },
        "jobs": [
            "file_generation",
            "data_sourcing",
            "process_responses",
            "file_transfer",
        ],
    },
    {
        "payer": "cigna",
        "job_schedules": {
            "file_generation": Schedule.DAILY,  # Previously default: DAILY
            "data_sourcing": Schedule.DAILY,
            "file_transfer": Schedule.DAILY,
        },
        "jobs": [
            "file_generation",
            "data_sourcing",
            "file_transfer",
        ],
    },
    {
        "payer": "cigna_track_1_amazon",
        "job_schedules": {
            "file_generation": Schedule.DAILY,  # Previously default: DAILY
            "data_sourcing": Schedule.DAILY,
            "file_transfer": Schedule.DAILY,
        },
        "jobs": [
            "file_generation",
            "data_sourcing",
            "file_transfer",
        ],
    },
    {
        "payer": "cigna_track_1_goldman_sachs",
        "job_schedules": {
            "file_generation": Schedule.BIWEEKLY,  # Previously default: BIWEEKLY
            "data_sourcing": Schedule.BIWEEKLY,
            "file_transfer": Schedule.BIWEEKLY,
        },
        "jobs": [
            "file_generation",
            "data_sourcing",
            "file_transfer",
        ],
    },
    {
        "payer": "credence",
        "job_schedules": {
            "file_generation": Schedule.DAILY,  # Previously default: DAILY
            "data_sourcing": Schedule.DAILY,
            "process_responses": Schedule.DAILY,
            "file_transfer": Schedule.DAILY,
        },
        "jobs": [
            "file_generation",
            "data_sourcing",
            "process_responses",
            "file_transfer",
        ],
    },
    {
        "payer": "esi",
        "job_schedules": {
            "file_generation": Schedule.DAILY,  # Previously default: DAILY
            "data_sourcing": Schedule.DAILY,
            "file_transfer": Schedule.FOUR_TIMES_DAILY,
        },
        "jobs": [
            "file_generation",
            "data_sourcing",
            "file_transfer",
        ],
    },
    {
        "payer": "luminare",
        "job_schedules": {
            "file_generation": Schedule.DAILY,  # Previously default: DAILY
            "data_sourcing": Schedule.DAILY,
            "process_responses": Schedule.DAILY,
            "file_transfer": Schedule.DAILY,
        },
        "jobs": [
            "file_generation",
            "data_sourcing",
            "process_responses",
            "file_transfer",
        ],
    },
    {
        "payer": "premera",
        "job_schedules": {
            "file_generation": Schedule.TWICE_DAILY,  # Previously default: TWICE_DAILY
            "data_sourcing": Schedule.TWICE_DAILY,
            "process_responses": Schedule.TWICE_DAILY,
            "file_transfer": Schedule.TWICE_DAILY,
        },
        "jobs": [
            "file_generation",
            "data_sourcing",
            "process_responses",
            "file_transfer",
        ],
    },
    {
        "payer": "surest",
        "job_schedules": {
            "file_generation": Schedule.DAILY,  # Previously default: DAILY
            "data_sourcing": Schedule.DAILY,
            "file_transfer": Schedule.DAILY,
        },
        "jobs": [
            "file_generation",
            "data_sourcing",
            "file_transfer",
        ],
    },
    {
        "payer": "uhc",
        "job_schedules": {
            "file_generation": Schedule.DAILY,  # Previously default: DAILY
            "data_sourcing": Schedule.DAILY,
            "file_transfer": Schedule.DAILY,
        },
        "jobs": [
            "file_generation",
            "data_sourcing",
            "file_transfer",
        ],
    },
]
