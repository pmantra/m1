#!/usr/bin/env python3
import argparse

import yaml
from jinja2 import Environment, FileSystemLoader


def generate_code(yaml_data, template_file):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    # Configure Jinja2 environment
    env = Environment(loader=FileSystemLoader("./template"), autoescape=True)

    # Load Jinja2 template
    template = env.get_template(template_file)

    # Render template with YAML data
    rendered_code = template.render(variables=yaml_data)

    dag_file_name = yaml_data["dag_id"]
    if not dag_file_name.endswith("_dag"):
        dag_file_name = dag_file_name + "_dag"

    # Write rendered code to output file
    with open(f"../dags/{dag_file_name}.py", "w") as output_file:
        output_file.write(rendered_code)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config_file", required=True, type=str)
    args = parser.parse_args()

    # Load YAML configuration
    with open(args.config_file, "r") as config_file:
        yaml_data = yaml.safe_load(config_file)

    generate_code(yaml_data, "dag_with_kpo_template.j2")
