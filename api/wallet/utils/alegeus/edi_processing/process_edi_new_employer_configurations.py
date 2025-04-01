import socket
from typing import Tuple

import paramiko
from cryptography.fernet import InvalidToken
from sqlalchemy.orm.exc import NoResultFound
from werkzeug.exceptions import HTTPException

from utils.log import logger
from wallet.utils.alegeus.edi_processing.common import (
    ERROR_CODE_MAPPING,
    check_file_availability,
    create_temp_file,
    decrypt_banking_data,
    get_client_sftp,
    get_employer_config_latest_response_filename,
    map_edi_results_header,
)
from wallet.utils.alegeus.edi_processing.edi_record_imports import create_file_list
from wallet.utils.alegeus.upload_to_ftp_bucket import upload_blob

log = logger(__name__)


def upload_new_employer_configurations(banking_information: bytes, org_id: str) -> bool:
    """
    Uploads CSV file configurations to the Alegeus SFTP server. Reviews res file for errors and reports.

    @param banking_information: A dictionary of banking information
    @param org_id: The org id of the new organization to be created in Alegeus

    @return: A bool indicating successful or unsuccessful upload attempt
    """
    client = None
    try:
        banking_info = decrypt_banking_data(org_id, banking_information)
    except InvalidToken:
        log.error(
            "upload_new_employer_configurations: Invalid token while decrypting data.",
            organization_id=org_id,
        )
        return False

    try:
        # Create a list of files with .mbi extension to upload to Alegeus.
        configuration_files_list = create_file_list([org_id], banking_info)
    except (TypeError, NoResultFound, HTTPException) as e:
        log.exception(
            "upload_new_employer_configurations: Unable to create configuration csv files.",
            error=e,
            organization_id=org_id,
        )
        return False

    # Delete banking info once files are successfully created for security purposes
    banking_info = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "Dict[Any, Any]")
    del banking_info

    try:
        # Gain access to the Alegeus SFTP server
        client, sftp = get_client_sftp()
    except (
        paramiko.AuthenticationException,
        paramiko.BadHostKeyException,
        paramiko.SSHException,
        socket.error,
    ) as e:
        log.exception(
            "upload_new_employer_configurations: Unable to connect to SFTP server.",
            error=e,
            organization_id=org_id,
        )
        if client:
            client.close()
        return False

    # Each file needs to be uploaded without errors one at a time
    for filename, file_content in configuration_files_list:
        try:
            # Get a list of current files on the Alegeus SFTP server
            files = sftp.listdir()
            # Determine if this file has been processed.
            response_file_successful, filename = process_config_file(
                filename, files, org_id, sftp
            )
        except (paramiko.SSHException, socket.error) as e:
            log.exception(
                "upload_new_employer_configurations: Exception calling SFTP to get files.",
                error=e,
                filename=filename,
                organization_id=org_id,
            )
            client.close()
            delete_file_list(configuration_files_list)
            return False
        # Continue to the next file if the file was successfully processed
        if response_file_successful:
            continue
        else:
            try:
                # Upload new file
                upload_blob(file_content, f"{filename}.mbi", client, sftp)
                # Continuously wait for the .res file to show up in the SFTP server.
                file_available = check_file_availability(
                    f"{filename}.res", sftp, client
                )
                if file_available:
                    # Process the new response file for errors
                    success = process_response_file(f"{filename}.res", sftp, org_id)
                else:
                    # We are unable to locate the latest .res file within the 5-minute limit.
                    log.error(
                        "upload_new_employer_configurations: Could not find results file within SFTP folder.",
                        filename=filename,
                        orgnization_id=org_id,
                    )
                    delete_file_list(configuration_files_list)
                    client.close()
                    return False
            except (
                paramiko.AuthenticationException,
                paramiko.BadHostKeyException,
                paramiko.SSHException,
                socket.error,
                TimeoutError,
            ) as e:
                log.exception(
                    "upload_new_employer_configurations: A connection exception was encountered.",
                    error=e,
                    filename=filename,
                    organization_id=org_id,
                )
                delete_file_list(configuration_files_list)
                client.close()
                return False
            # If we successfully processed the file move on to the next file
            if success:
                continue
            else:
                # The latest uploaded file contained errors.
                log.info(
                    f"upload_new_employer_configurations: {filename} contains errors."
                )
                delete_file_list(configuration_files_list)
                client.close()
                return False

    log.info(
        "upload_new_employer_configurations: All files processed.",
        organization_id=org_id,
    )
    delete_file_list(configuration_files_list)
    client.close()
    return True


def process_config_file(filename, files, org_id, sftp) -> Tuple[bool, str]:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    """
    Finds the latest response configuration file and processes the results if found.

    @param filename: The filename without the version or extension
    @param files: The list of all files found in the Alegeus SFTP folder
    @param org_id: The organization associated with the file upload
    @param sftp: The sftp client required to process the response file
    @return: A tuple containing a bool if the response file contains errors and a filename string
    """
    record_type = filename[6:8]
    file_prefix = f"MAVEN_{record_type}_{org_id}"
    # Find all matching file names on the Alegeus SFTP server
    matching_files = [file for file in files if file_prefix in file]
    if len(matching_files) > 0:
        # If matching files exist, find the most recent file version
        (
            latest_response_filename,
            iteration,
        ) = get_employer_config_latest_response_filename(files, file_prefix)
        #  Process the file for errors. No errors' means it was successfully uploaded
        response_successful = process_response_file(
            f"{latest_response_filename}.res", sftp, org_id
        )
        if response_successful:
            return True, latest_response_filename
        else:
            # If the latest file contains errors update the filename with a new version
            filename = f"{file_prefix}_{iteration + 1}"
            return False, filename
    else:
        # If no file was found, we will upload it for the first time
        return False, file_prefix


def process_response_file(filename, sftp, org_id) -> bool:  # type: ignore[return,no-untyped-def] # Missing return statement #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    """
    Checks the header of the response file downloaded from Alegeus to see if there were any errors reported.
    If error, map them and alert ops channel.

    @param filename: The response file name without the extension
    @param sftp: The sftp connector
    @param org_id: The organization id associated with the configuration file
    @return: A bool describing if the response file contained errors
    """
    try:
        # Download the .res file
        results_temp = create_temp_file(filename, sftp)
        results_temp.seek(0)
    except (paramiko.SSHException, socket.error) as e:
        log.exception("process_response_file: Error creating temp file.", error=e)
        raise e
    for line in results_temp:
        cleaned_line = line.decode("utf-8").strip()
        line_items = cleaned_line.split(",")
        if line_items[0] == "RA":  # Check the header to see if there are any errors
            processed_headers = map_edi_results_header(line_items)
            if processed_headers.get("total_errors") == 0:
                log.info(
                    f"process_response_file: No errors found in {processed_headers.get('file_name')}"
                )
                return True
        else:
            # Errors were found in the .res file.
            file_type = filename[6:8]
            results_dict = RESULTS_FILE_TEMPLATE_MAPPING[file_type](line_items)
            error_code = results_dict.get("detail_response_code")
            error_code_description = ERROR_CODE_MAPPING.get(int(error_code), "Unknown")
            log.error(
                "process_response_file: EDI response file contains error.",
                org_id=org_id,
                error_code=error_code,
                filename=filename,
                description=error_code_description,
            )
            return False


def results_is_dict(line_items):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return {
        "detail_response_code": line_items[1],
        "employer_id": line_items[3],
        "detail_response_message": line_items[5],
    }


def results_iv_dict(line_items):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return {"detail_response_code": line_items[1]}


def results_it_dict(line_items):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return {
        "detail_response_code": line_items[1],
        "employer_id": line_items[3],
        "detail_response_message": line_items[5],
    }


def results_iu_dict(line_items):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return {
        "detail_response_code": line_items[1],
        "employer_id": line_items[3],
        "plan_id": line_items[4],
    }


RESULTS_FILE_TEMPLATE_MAPPING = {
    "IS": results_is_dict,
    "IT": results_it_dict,
    "IV": results_iv_dict,
    "IU": results_iu_dict,
}


def delete_file_list(config_list):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    config_list = None
    del config_list
