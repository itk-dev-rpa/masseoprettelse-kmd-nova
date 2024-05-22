"""This module contains the main process of the robot."""

from datetime import datetime
import json
import os
import uuid
import re

from OpenOrchestrator.orchestrator_connection.connection import OrchestratorConnection
from itk_dev_shared_components.graph import authentication as graph_authentication
from itk_dev_shared_components.graph.authentication import GraphAccess
from itk_dev_shared_components.graph import mail as graph_mail
from itk_dev_shared_components.graph.mail import Email
from itk_dev_shared_components.kmd_nova import nova_notes, nova_cases
from itk_dev_shared_components.kmd_nova.authentication import NovaAccess
from itk_dev_shared_components.kmd_nova.nova_objects import NovaCase, CaseParty, Caseworker, Department
from itk_dev_shared_components.kmd_nova import cpr as nova_cpr

from robot_framework.case_mail import CaseMail
from robot_framework import config


def process(orchestrator_connection: OrchestratorConnection) -> None:
    """Do the primary process of the robot."""
    orchestrator_connection.log_trace("Running process.")

    nova_credentials = orchestrator_connection.get_credential(config.NOVA_API)
    nova_access = NovaAccess(nova_credentials.username, nova_credentials.password)

    graph_credentials = orchestrator_connection.get_credential(config.GRAPH_API)
    graph_access = graph_authentication.authorize_by_username_password(graph_credentials.username, **json.loads(graph_credentials.password))

    # Check mail for things to process
    emails = get_emails(graph_access)

    # Parse each mail and prepare for lookup in KMD Nova
    for email in emails:
        case_mail = _parse_mail_text(email.body)
        list_of_ids = _get_ids_from_mail(email, graph_access)
        for ident in list_of_ids:
            ident = ident.replace("-", "")
            cases = _get_cases_from_id(nova_access, ident, case_mail.case_title)
            name = _get_name_from_cpr(cases, ident, nova_access)
            case = _find_or_create_matching_case(cases, case_mail, ident, name, nova_access)
            nova_notes.add_text_note(case.uuid, case_mail.note_title, case_mail.note_text, True, nova_access)
        # Remove email


def get_emails(graph_access: GraphAccess) -> list[Email]:
    """Get all emails to be handled by the robot.

    Args:
        graph_access: The GraphAccess object used to authenticate against Graph.

    Returns:
        A filtered list of email objects to be handled.
    """
    # Get all emails from the 'Refusioner' folder.
    mails = graph_mail.get_emails_from_folder("itk-rpa@mkb.aarhus.dk", config.MAIL_SOURCE_FOLDER, graph_access)

    # Filter the emails on sender and subject
    mails = [mail for mail in mails if mail.sender == "noreply@aarhus.dk" and mail.subject == 'Masseoprettelser i KMD Nova (fra Selvbetjening.aarhuskommune.dk)']

    return mails


def _parse_mail_text(mail_text: str) -> CaseMail:
    ''' From an email sent by the OS2 Forms form "Masseoprettelse i KMD Nova",
    create a new CaseMail object
    '''
    return CaseMail(
        _get_line_after("Sagsoverskrift", mail_text),
        _get_line_after("KLE-nummer", mail_text),
        _get_line_after("Handlingsfacet", mail_text),
        _get_sensitivity_from_email(_get_line_after("Følsomhed", mail_text)),
        _get_line_after("Notat overskrift", mail_text),
        _get_line_after("Notat tekst", mail_text)
    )


def _get_sensitivity_from_email(email_string: str) -> str:
    '''Translates the string from OS2 forms to the expected KMD Nova format. This is used only when creating a CaseMail

    Args:
        email_string: A string, matching the format in OS2 Forms and the emails sent to the robot

    Returns:
        A string, matching the format expected by KMD Nova in the sensitivity field
    '''
    translation = {
        "Fortrolige oplysninger": "Fortrolige",
        "Ikke fortrolige oplysninger": "IkkeFortrolige",
        "Særligt følsomme oplysninger": "SærligFølsomme",
        "Følsomme oplysninger": "Følsomme"
    }
    return translation[email_string]


def _get_line_after(line: str, text: str) -> str:
    match = re.search("<b>" + line + r"<\/b><br>(.+?)<br>", text)
    return match.group(1)


def _get_name_from_cpr(cases: list[NovaCase], cpr: str, nova_access: NovaAccess) -> str:
    '''Find name from a matching case or lookup by address

    Args:
        cases: A list of NovaCases to check for existing name
        cpr: ÍD of the person we are looking for
        nova_access: A token to access the KMD Nova API

    Returns:
        A string of a name
    '''
    # Check provided cases for an existing match with a name:
    for case in cases:
        for case_party in case.case_parties:
            if case_party.identification == cpr and case_party.name:
                return case_party.name
    # If nothing was found, do a lookup in the registry:
    return nova_cpr.get_address_by_cpr(cpr, nova_access)['name']


def _create_case(ident: str, name: str, case_mail: CaseMail, nova_access: NovaAccess) -> NovaCase:
    """Create a Nova case based on email data.

    Args:
        ident: The CVR or CPR we are looking for
        name: The name of the person we are looking for
        case_mail: A CaseMail object containing the data from the case
        nova_access: An access token for accessing the KMD Nova API

    Returns:
        New NovaCase with data defined
    """
    id_type = "CprNummer"

    caseworker = Caseworker(
            name='svcitkopeno svcitkopeno',
            ident='AZX0080',
            uuid='0bacdddd-5c61-4676-9a61-b01a18cec1d5'
        )

    department = Department(
            id=818485,
            name="Borgerservice",
            user_key="4BBORGER"
        )

    case_party = CaseParty(
        role="Primær",
        identification_type=id_type,
        identification=ident,
        name=name,
        uuid=None
    )

    case = NovaCase(
        uuid=str(uuid.uuid4()),
        title=case_mail.case_title,
        case_date=datetime.now(),
        progress_state='Opstaaet',
        case_parties=[case_party],
        kle_number=case_mail.kle,
        proceeding_facet=case_mail.proceeding_facet,
        sensitivity=case_mail.sensitivity,
        caseworker=caseworker,
        responsible_department=department,
        security_unit=department
    )
    nova_cases.add_case(case, nova_access)
    return case


def _get_ids_from_mail(email: Email, graph_access: GraphAccess) -> list[str]:
    id_list = list[0]
    attachments = graph_mail.list_email_attachments(email, graph_access)
    for attachment in attachments:
        email_attachment = graph_mail.get_attachment_data(attachment, graph_access)
        id_list = email_attachment.read().decode().split()
    return id_list


def _get_cases_from_id(nova_access: NovaAccess, id: str, case_title: str) -> list[NovaCase]:
    if _is_cpr(id):
        return nova_cases.get_cases(nova_access, id, case_title = case_title)
    else:
        return nova_cases.get_cvr_cases(nova_access, id, case_title = case_title)


def _find_or_create_matching_case(cases: list[NovaCase], case_mail: CaseMail, ident: str, name: str, nova_access: NovaAccess) -> NovaCase:
    ''' Lookup case match in list, based on KLE-number and case title.

    Args:
        cases: A list of cases to check
        case_mail: A CaseMail containing the data to check for
        ident, name: The identification and name to use if we need to create a new case
        nova_access: An access token to access the KMD Nova API
    '''
    for case in cases:
        if case.kle_number == case_mail.kle and case.title == case_mail.case_title:
            return case
    return _create_case(ident, name, case_mail, nova_access)


def _is_cpr(string_to_check: str) -> bool:
    ''' An adequate check on string to see if this is a CPR
    Returns:
        Is it 10 symbols long, without a hyphen?
    '''
    pure_number_string = string_to_check.replace("-", "")
    return pure_number_string.__len__() == 10


def _is_cvr(string_to_check: str) -> bool:
    ''' An adequate test on a string to see if this is a CVR
    Returns:
        Is it 8 symbols long?
    '''
    return string_to_check.__len__() == 8


if __name__ == '__main__':
    conn_string = os.getenv("OpenOrchestratorConnString")
    crypto_key = os.getenv("OpenOrchestratorKey")
    oc = OrchestratorConnection("Masseoprettelse KMD NOVA", conn_string, crypto_key, '')
    process(oc)
