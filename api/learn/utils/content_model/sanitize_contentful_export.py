"""
This script should be used after exporting the content model from contentful to remove all the fields
that are expected to be different across environments - such as, timestamps, versions, user

contentful space export --space-id $CONTENTFUL_LEARN_SPACE_ID \
    --skip-content \
    --skip-roles \
    --skip-webhooks \
    --content-file "learn/utils/content_model/content_model.json" \
    --environment-id master-or-whichever-env \
    --mt $CONTENTFUL_LEARN_MANAGEMENT_KEY
"""
import json
import os
from typing import Any


def get_code(e: dict[str, Any]) -> str:
    return e["code"]


def get_name(e: dict[str, Any]) -> str:
    return e["name"]


def get_sys_id(e: dict[str, Any]) -> str:
    return e["sys"]["id"]


def get_sys_content_type_id(e: dict[str, Any]) -> str:
    return e["sys"]["contentType"]["sys"]["id"]


def sanitize_content_json(file_name_to_sanitize: str) -> None:
    with open(file_name_to_sanitize, "r") as json_read:
        json_content = json.load(json_read)

    json_content["contentTypes"].sort(key=get_sys_id)

    for entry in json_content["contentTypes"]:
        for key in list(entry["sys"]):
            if key not in ["id", "type"]:
                entry["sys"].pop(key)
        entry["sys"]["publishedVersion"] = 1

    for entry in json_content["locales"]:
        for key in list(entry["sys"]):
            if key not in ["type"]:
                entry["sys"].pop(key)
        entry["sys"]["publishedVersion"] = 1
    json_content["locales"].sort(key=get_code)

    for entry in json_content["tags"]:
        for key in list(entry["sys"]):
            if key not in ["id", "type", "visibility"]:
                entry["sys"].pop(key)
        entry["sys"]["publishedVersion"] = 1
    json_content["tags"].sort(key=get_name)

    if "editorInterfaces" in json_content:
        # in a new space this key won't exist
        json_content["editorInterfaces"].sort(key=get_sys_content_type_id)
        for entry in json_content["editorInterfaces"]:
            for key in list(entry["sys"]):
                if key not in ["id", "type", "linkType", "contentType"]:
                    entry["sys"].pop(key)
            if entry["sys"].get("id", None) == "default":
                entry["sys"].pop("id", None)

    with open(file_name_to_sanitize, "w") as json_write:
        json.dump(json_content, json_write, indent=2)


if __name__ == "__main__":
    dirname = os.path.dirname(__file__)
    filename = os.path.join(dirname, "content_model.json")
    sanitize_content_json(filename)
