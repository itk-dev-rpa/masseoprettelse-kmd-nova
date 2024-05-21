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

from robot_framework import config


class CaseMail:
    def __init__(self, case_title, kle, action_aspect, sensitivity, note_title, note_text):
        self.case_title = case_title
        self.kle = kle
        self.proceeding_facet = action_aspect
        self.sensitivity = _get_sensitivity_from_email(sensitivity)
        self.note_title = note_title
        self.note_text = note_text


def process(orchestrator_connection: OrchestratorConnection) -> None:
    """Do the primary process of the robot."""
    orchestrator_connection.log_trace("Running process.")

    nova_creds = orchestrator_connection.get_credential(config.NOVA_API)
    nova_access = NovaAccess(nova_creds.username, nova_creds.password)

    graph_creds = orchestrator_connection.get_credential(config.GRAPH_API)
    graph_access = graph_authentication.authorize_by_username_password(graph_creds.username, **json.loads(graph_creds.password))

    # Check mail for things to process
    emails = get_emails(graph_access)

    # Parse each mail and prepare for lookup in KMD Nova
    for email in emails:
        case_mail = _parse_mail_text(email.body)
        list_of_ids = _get_ids_from_mail(email, graph_access)
        for ident in list_of_ids:
            cases = _get_cases_from_id(nova_access, ident, case_mail.case_title)
            name = _get_name_from_cpr(cases, ident, nova_access)
            case = _find_or_create_matching_case(cases, case_mail.kle, ident, name, nova_access)
            print("Writing note: " + case_mail.note_title)
            nova_notes.add_text_note(case.uuid, case_mail.note_title, case_mail.note_text, True, nova_access)
        # Remove email

    # name = nova_cpr.get_address_by_cpr(cpr, nova_access)['name']

    # nova_cases.add_case(test_case(), nova_access)


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


def find_or_create_case(cpr: str, nova_access: NovaAccess, caseworker: Caseworker, department: Department) -> NovaCase:
    """Find a case with the correct title and kle number on the given cpr.
    If no case exists a new one is created instead.

    Args:
        cpr: The cpr of the person to get the case from.
        nova_access: The nova access object used to authenticate.

    Returns:
        The relevant nova case.
    """
    cases = nova_cases.get_cases(nova_access, cpr=cpr)

    # If a case already exists reuse it
    for case in cases:
        if case.title == "Sygesikring i almindelighed" and case.active_code == 'Active' and case.kle_number == '29.03.00':
            return case

    # Find the name of the person in one of the cases
    name = None
    for case in cases:
        for case_party in case.case_parties:
            if case_party.identification == cpr and case_party.name:
                name = case_party.name
                break
        if name:
            break

    # If the name wasn't found in a case look it up in cpr
    if not name:
        name = nova_cpr.get_address_by_cpr(cpr, nova_access)['name']

    case_party = CaseParty(
        role="Primær",
        identification_type="CprNummer",
        identification=cpr,
        name=name,
        uuid=None
    )

    # Create a new case
    case = NovaCase(
        uuid=str(uuid.uuid4()),
        title="Sygesikring i almindelighed",
        case_date=datetime.now(),
        progress_state='Opstaaet',
        case_parties=[case_party],
        kle_number="29.03.00",
        proceeding_facet="G01",
        sensitivity="Følsomme",
        caseworker=caseworker,
        responsible_department=department,
        security_unit=department
    )
    nova_cases.add_case(case, nova_access)
    return case


def _get_sensitivity_from_email(email_string: str) -> str:
    '''Translates the string from OS2 forms to the expected KMD Nova format. This is used only when creating a CaseMail

    Args:
        email_string: A string, matching the format in OS2 Forms and the emails send to the robot

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


def _get_name_from_cpr(cases: list[NovaCase], cpr: str, nova_access: NovaAccess) -> str:
    '''Find name from a matching case or lookup by address
    '''
    for case in cases:
        for case_party in case.case_parties:
            if case_party.identification == cpr and case_party.name:
                return case_party.name
    # This function does not return the expected object, nothing is returned. Maybe it's because of the test cpr?
    return nova_cpr.get_address_by_cpr(cpr, nova_access)['name']


def _write_mail_to_file(email: Email):
    with open("test/email" + str(uuid.uuid1())[:8] + ".txt", "w") as file:
        file.write(email.body)


def _read_mail_from_file(mail: str) -> str:
    with open("test/" + mail, "r") as file:
        return file.read()


def _create_case(ident: str, name: str, case_mail: CaseMail, nova_access: NovaAccess) -> NovaCase:
    """Create a Nova case based on email data.

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
    for case in cases:
        if case.kle == case_mail.kle:
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


def _parse_mail_text(mail_text: str) -> CaseMail:
    return CaseMail(
        _get_line_after("Sagsoverskrift", mail_text),
        _get_line_after("KLE-nummer", mail_text),
        _get_line_after("Handlingsfacet", mail_text),
        _get_line_after("Følsomhed", mail_text),
        _get_line_after("Notat overskrift", mail_text),
        _get_line_after("Notat tekst", mail_text)
    )


def _get_line_after(line: str, text: str) -> str:
    match = re.search("<b>" + line + r"<\/b><br>(.+?)<br>", text)
    return match.group(1)


if __name__ == '__main__':
    conn_string = os.getenv("OpenOrchestratorConnString")
    crypto_key = os.getenv("OpenOrchestratorKey")
    oc = OrchestratorConnection("Masseoprettelse KMD NOVA", conn_string, crypto_key, '')
    process(oc)
