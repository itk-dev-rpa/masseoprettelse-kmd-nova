''' For testing the functions of the robot, without using email
'''
import os
import uuid

from OpenOrchestrator.orchestrator_connection.connection import OrchestratorConnection
from itk_dev_shared_components.kmd_nova.authentication import NovaAccess

from robot_framework import process
from robot_framework import config


def test(orchestrator_connection: OrchestratorConnection) -> None:
    """Test the robot."""
    orchestrator_connection.log_trace("Running process.")

    nova_creds = orchestrator_connection.get_credential(config.NOVA_API)
    nova_access = NovaAccess(nova_creds.username, nova_creds.password)

    # Check mail for things to process
    email = _read_mail_from_file("test/email8eaae935.txt")
    case_mail = process._parse_mail_text(email)
    ident = "2307851647"
    cases = process._get_cases_from_id(nova_access, ident, case_mail.case_title)
    name = process._get_name_from_cpr(cases, ident, nova_access)
    return
    with open("test/testdata.csv", "r") as _email_attachment:
        list_of_ids = _email_attachment.read().split()
        for ident in list_of_ids:
            cases = process._get_cases_from_id(nova_access, ident, case_mail.case_title)
            name = process._get_name_from_cpr(cases, ident, nova_access)
            # case = process._find_or_create_matching_case(cases, case_mail.kle, ident, name, nova_access)
            print("Writing note: " + case_mail.note_title + " to name: " + name)
        # Remove email

    # name = nova_cpr.get_address_by_cpr(cpr, nova_access)['name']

    # nova_cases.add_case(test_case(), nova_access)


def _write_mail_to_file(email: str):
    with open("email" + str(uuid.uuid1())[:8] + ".txt", "w") as file:
        file.write(email)


def _read_mail_from_file(mail: str) -> str:
    with open(mail, "r") as file:
        return file.read()

    
if __name__ == '__main__':
    conn_string = os.getenv("OpenOrchestratorConnString")
    crypto_key = os.getenv("OpenOrchestratorKey")
    oc = OrchestratorConnection("Masseoprettelse KMD NOVA", conn_string, crypto_key, '')
    test(oc)