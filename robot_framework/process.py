"""This module contains the main process of the robot."""

from datetime import datetime
import json
import os
import uuid
import re

from OpenOrchestrator.orchestrator_connection.connection import OrchestratorConnection
from OpenOrchestrator.database.queues import QueueStatus
from itk_dev_shared_components.graph import authentication as graph_authentication
from itk_dev_shared_components.graph.authentication import GraphAccess
from itk_dev_shared_components.graph import mail as graph_mail
from itk_dev_shared_components.graph.mail import Email
from itk_dev_shared_components.kmd_nova import nova_notes, nova_cases
from itk_dev_shared_components.kmd_nova.authentication import NovaAccess
from itk_dev_shared_components.kmd_nova.nova_objects import NovaCase, CaseParty, Caseworker, Department
from itk_dev_shared_components.kmd_nova import cpr as nova_cpr
from itk_dev_shared_components.smtp import smtp_util
from requests.exceptions import HTTPError

from robot_framework.soup_mail import html_to_dict
from robot_framework import config


def process(orchestrator_connection: OrchestratorConnection) -> None:
    """Do the primary process of the robot."""
    orchestrator_connection.log_trace("Running process.")

    graph_credentials = orchestrator_connection.get_credential(config.GRAPH_API)
    graph_access = graph_authentication.authorize_by_username_password(graph_credentials.username, **json.loads(graph_credentials.password))
    _create_queue_from_emails(orchestrator_connection, graph_access)

    nova_credentials = orchestrator_connection.get_credential(config.NOVA_API)
    nova_access = NovaAccess(nova_credentials.username, nova_credentials.password)
    _create_notes_from_queue(orchestrator_connection, nova_access)


def _create_queue_from_emails(orchestrator_connection: OrchestratorConnection, graph_access: GraphAccess):
    ''' Create a queue by reading emails and delete the emails after.

    Args:
        orchestrator_connection: A way to access the orchestrator to create the queue elements
        graph_access: A token to access emails
    '''
    # Check mailbox for emails to process
    emails = _get_emails(graph_access)
    emails.reverse()

    # Parse each mail and add data to KMD Nova
    for email in emails:
        # Get data from email
        data_dict = _parse_mail_text(email.body)
        user_az = _get_az_from_email(data_dict["Bruger"])
        is_user_recognized = _check_az(orchestrator_connection, user_az)
        _send_status_email(_get_recipient_from_email(data_dict["Bruger"]), is_user_recognized, data_dict["Sagsoverskrift"])
        # If user is not allowed to send this data, stop the process.
        if not is_user_recognized:
            continue
        list_of_ids = _get_ids_from_mail(email, graph_access)
        orchestrator_connection.bulk_create_queue_elements(
            config.QUEUE_NAME,
            references = list_of_ids,
            data=[json.dumps(data_dict, ensure_ascii=False)] * len(list_of_ids),
            created_by="Robot")
        graph_mail.delete_email(email, graph_access)


def _get_az_from_email(user_data: str) -> str:
    '''Find az in user_data using regex'''
    pattern = r"\baz\d+\b"
    return re.findall(pattern, user_data)[0]


def _get_recipient_from_email(user_data: str) -> str:
    '''Find email in user_data using regex'''
    pattern = r"E-mail: (\S+)"
    return re.findall(pattern, user_data)[0]


def _check_az(orchestrator_connection: OrchestratorConnection, email_az: str) -> bool:
    '''Check AZ from email against accepted list of AZ in process arguments.

    Args:
        orchestrator_connection: Connection containing process arguments with some accepted AZs
        email_az: A user identification (AZ) read from an email
    '''
    accepted_azs = json.loads(orchestrator_connection.process_arguments)["accepted_azs"]
    return email_az.lower() in [az.lower() for az in accepted_azs]


def _send_status_email(recipient: str, process_started: bool, case_name: str):
    '''Send an email with variable text depending on whether the process started or not.

    Args:
        recipient: Who should receive the email
        process_started: Did the process start?
        case_name: Which case does this concern?
    '''
    subject = config.SUBJECT_BASE
    text = config.BODY_BASE + case_name
    if process_started:
        subject += config.SUBJECT_SUCCESS
        text += config.BODY_SUCCESS
    else:
        subject += config.SUBJECT_ERROR
        text += config.BODY_ERROR
    smtp_util.send_email(
        receiver= recipient,
        sender=config.STATUS_SENDER,
        subject=subject,
        body=text,
        smtp_server=config.SMTP_SERVER,
        smtp_port=config.SMTP_PORT
    )


def _create_notes_from_queue(orchestrator_connection: OrchestratorConnection, nova_access: NovaAccess):
    ''' Load queue elements and write notes to KMD Nova

    Args:
        orchestrator_connection: A way to read the queue elements
        nova_access: A token to write the notes
    '''
    queue_elements_processed = 0
    while (queue_element := orchestrator_connection.get_next_queue_element(config.QUEUE_NAME)) and queue_elements_processed < config.MAX_TASK_COUNT:
        # Find a case to add note to
        data_dict = json.loads(queue_element.data)
        cases = nova_cases.get_cases(nova_access, cpr = queue_element.reference)
        name = _get_name_from_cpr(cpr = queue_element.reference, nova_access = nova_access)
        try:
            case = _find_or_create_matching_case(cases, data_dict, queue_element.reference, name, nova_access)
            caseworker = _get_process_caseworker()
            nova_notes.add_text_note(
                case.uuid,
                data_dict["Notat overskrift"],
                data_dict["Notat tekst"],
                caseworker,
                True,
                nova_access)
        except LookupError:
            orchestrator_connection.set_queue_element_status(queue_element.id, QueueStatus.FAILED, f"Sagsoverskrift '{data_dict["Sagsoverskrift"]}' ikke fundet.")
        except HTTPError as e:
            orchestrator_connection.set_queue_element_status(queue_element.id, QueueStatus.FAILED, json.loads(e.response.text)["title"])
        # Set status Done for this note and look for the next queue element
        else:
            orchestrator_connection.set_queue_element_status(queue_element.id, QueueStatus.DONE)


def _get_emails(graph_access: GraphAccess) -> list[Email]:
    """Get all emails to be handled by the robot.

    Args:
        graph_access: The GraphAccess object used to authenticate against Graph.

    Returns:
        A filtered list of email objects to be handled.
    """
    # Get all emails from the relevant folder.
    mails = graph_mail.get_emails_from_folder("itk-rpa@mkb.aarhus.dk", config.MAIL_SOURCE_FOLDER, graph_access)

    # Filter the emails on sender and subject
    mails = [mail for mail in mails if mail.sender == "noreply@aarhus.dk" and mail.subject == config.MAIL_INBOX_SUBJECT]

    return mails


def _parse_mail_text(mail_text: str) -> dict:
    ''' From an email sent by the OS2 Forms form "Masseoprettelse i KMD Nova",
    create a new dictionary.

    Args:
        mail_text: Text from OS2 Forms that can be read by the robot.

    "Returns:
        A dictionary object, for easier access to variables.
    '''
    dictionary = html_to_dict(mail_text)
    if dictionary["Brug eksisterende sag"] != "Valgt":
        dictionary["Følsomhed"] = _get_sensitivity_from_email(dictionary["Følsomhed"])
        dictionary["Sikkerhedsenhed"] = _get_securityunit_from_department(dictionary["Afdeling"])
    return dictionary


def _get_sensitivity_from_email(email_string: str) -> str:
    '''Translates the string from OS2 forms to the expected KMD Nova format.

    Args:
        email_string: A string, matching the format in OS2 Forms and the emails sent to the robot.

    Returns:
        A string, matching the format expected by KMD Nova in the Sensitivity field.
    '''
    return config.KMD_SENSITIVITY[email_string]


def _get_securityunit_from_department(email_string: str) -> str:
    '''Translates the string from OS2 Department value to a security unit value

    Args:
        email_string: A string, matching the format in OS2 Forms and the emails sent to the robot.

    Returns:
        A string, matching the format expected by KMD Nova in the Security field. All options except two will return Borgerservice.
    '''
    return config.KMD_DEPARTMENT_SECURITY_PAIR[email_string]


def _get_name_from_cpr(cpr: str, nova_access: NovaAccess) -> str:
    '''Find name from a matching case or lookup by address.

    Args:
        cases: A list of NovaCases to check for existing name.
        cpr: ÍD of the person we are looking for.
        nova_access: A token to access the KMD Nova API.

    Returns:
        The name of the person with the provided CPR.
    '''
    cases = nova_cases.get_cases(nova_access, cpr = cpr, limit=1)
    # Check provided cases for an existing match with a name:
    for case in cases:
        for case_party in case.case_parties:
            if case_party.identification == cpr and case_party.name:
                return case_party.name
    # If nothing was found, do a lookup in the registry:
    return nova_cpr.get_address_by_cpr(cpr, nova_access)['name']


def _create_case(ident: str, name: str, data_dict: dict, nova_access: NovaAccess) -> NovaCase:
    """Create a Nova case based on email data.

    Args:
        ident: The CPR we are looking for
        name: The name of the person we are looking for
        data_dict: A dictionary object containing the data from the case
        nova_access: An access token for accessing the KMD Nova API

    Returns:
        New NovaCase with data defined
    """

    case_party = CaseParty(
        role="Primær",
        identification_type="CprNummer",
        identification=ident,
        name=name,
        uuid=None
    )

    department = _get_department(data_dict["Afdeling"])
    security_unit = _get_department(config.KMD_DEPARTMENT_SECURITY_PAIR[data_dict["Afdeling"]])
    caseworker = _get_process_caseworker()

    case = NovaCase(
        uuid=str(uuid.uuid4()),
        title=data_dict["Sagsoverskrift"],
        case_date=datetime.now(),
        progress_state='Opstaaet',
        case_parties=[case_party],
        kle_number=data_dict["KLE-nummer"],
        proceeding_facet=data_dict["Handlingsfacet"],
        sensitivity=data_dict["Følsomhed"],
        caseworker=caseworker,
        responsible_department=department,
        security_unit=security_unit
    )

    nova_cases.add_case(case, nova_access)
    return case


def _get_department(department_code: str) -> Department:
    '''Make a department object from department code

    Args:
        department_code: A KMD code matching a department

    Returns:
        A Department object created from data in config
    '''
    data = config.KMD_DEPARTMENTS[department_code]
    department = Department(
            id=int(data["id"]),
            name=data["name"],
            user_key=department_code
        )
    return department


def _get_ids_from_mail(email: Email, graph_access: GraphAccess) -> list[str]:
    ''' Open up attachment attached to an email and read the data contained.

    Args:
        email: An email.
        graph_access: The accesstoken required to read emails.

    Returns:
        A list of each line found in the attachments.
    '''
    id_list = []
    attachments = graph_mail.list_email_attachments(email, graph_access)
    for attachment in attachments:
        email_attachment = graph_mail.get_attachment_data(attachment, graph_access)
        id_list = id_list + email_attachment.read().decode().split()

    id_list = [s.replace("-", "") for s in id_list]
    return id_list


def _find_or_create_matching_case(cases: list[NovaCase], data_dict: dict, ident: str, name: str, nova_access: NovaAccess) -> NovaCase:
    ''' Lookup case match in list, based on case title.

    Args:
        cases: A list of cases to check
        data_dict: A dictionary containing the data to check for
        ident, name: The identification and name to use if we need to create a new case
        nova_access: An access token to access the KMD Nova API

    Returns:
        A NovaCase matching the arguments provided.
    '''
    if data_dict["Brug eksisterende sag"] == "Valgt":
        for case in cases:
            if case.title == data_dict["Sagsoverskrift"]:
                return case
        raise LookupError("Could not find matching case")
    else:
        return _create_case(ident, name, data_dict, nova_access)


def _get_process_caseworker() -> Caseworker:
    return Caseworker(
        name='Rpabruger Rpa75 - MÅ IKKE SLETTES RITM0283472',
        ident='azrpa75',
        uuid='2382680f-58cd-4f6d-90fd-23e4ce0180ae'
    )


if __name__ == '__main__':
    conn_string = os.getenv("OpenOrchestratorConnString")
    crypto_key = os.getenv("OpenOrchestratorKey")
    oc = OrchestratorConnection("Masseoprettelse KMD NOVA", conn_string, crypto_key, '{"accepted_azs":["az77820","az68933"]}')
    process(oc)
