import pprint
from pathlib import Path

import click

from direct_payment.pharmacy.tasks.esi_parser import esi_converter
from direct_payment.pharmacy.tasks.esi_parser.esi_parser import ESIParser


@click.command()
@click.option("--raw_file_path", required=True, help="Path to the ESI raw input file")
@click.option(
    "--schema_file_path",
    default=f"{Path.cwd()}/direct_payment/pharmacy/tasks/esi_parser/esi_schema/esi_schema_v3.8.csv",
    help="Path to the ESI schema file",
)
def parse_esi(raw_file_path: str, schema_file_path: str) -> None:
    """
    Parsing ESI raw file
    """
    esi_parser = ESIParser(schema_file_path)
    results = esi_parser.parse(raw_file_path)
    for item in results:
        instance = esi_converter.convert(item)
        converted = esi_converter.convert_to_health_plan_ytd_spend(instance, "")
        pprint.pprint(converted)


if __name__ == "__main__":
    parse_esi()
