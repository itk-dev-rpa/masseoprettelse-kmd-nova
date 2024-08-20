"""This subprocess concerns the Nova functionality of the robot."""
from datetime import datetime
import json
import uuid

from OpenOrchestrator.orchestrator_connection.connection import OrchestratorConnection
from OpenOrchestrator.database.queues import QueueStatus
from itk_dev_shared_components.kmd_nova import nova_notes, nova_cases
from itk_dev_shared_components.kmd_nova.authentication import NovaAccess
from itk_dev_shared_components.kmd_nova.nova_objects import NovaCase, CaseParty, Department
from itk_dev_shared_components.kmd_nova import cpr as nova_cpr
from requests.exceptions import HTTPError

from robot_framework import config


def create_notes_from_queue(orchestrator_connection: OrchestratorConnection, nova_access: NovaAccess):
    """ Load queue elements and write notes to KMD Nova

    Args:
        orchestrator_connection: A way to read the queue elements
        nova_access: A token to write the notes
    """
    queue_elements_processed = 0
    while (queue_element := orchestrator_connection.get_next_queue_element(config.QUEUE_NAME)) and queue_elements_processed < config.MAX_TASK_COUNT:
        data_dict = json.loads(queue_element.data)
        cases = nova_cases.get_cases(nova_access, cpr = queue_element.reference)
        name = _get_name_from_cpr(cpr = queue_element.reference, nova_access=nova_access, cases=cases)
        try:
            case = (_find_matching_case(data_dict["Sagsoverskrift"], cases)
                    if data_dict["Brug eksisterende sag"] == "Valgt"
                    else _create_case(queue_element.reference, name, data_dict, nova_access))

            caseworker = config.CASEWORKER
            nova_notes.add_text_note(
                case.uuid,
                data_dict["Notat overskrift"],
                data_dict["Notat tekst"],
                caseworker,
                True,
                nova_access)
        except LookupError:
            orchestrator_connection.set_queue_element_status(queue_element.id, QueueStatus.FAILED, f"Sagsoverskrift '{data_dict['Sagsoverskrift']}' ikke fundet.")
        except HTTPError as e:
            orchestrator_connection.set_queue_element_status(queue_element.id, QueueStatus.FAILED, json.loads(e.response.text)["title"])
        # Set status Done for this note and look for the next queue element
        else:
            orchestrator_connection.set_queue_element_status(queue_element.id, QueueStatus.DONE)


def _get_name_from_cpr(cpr: str, nova_access: NovaAccess, cases: list(NovaCase)) -> str:
    """Find name from lookup by address, and if not found (such as when using test CPRs) do a lookup in cases.

    Args:
        cpr: ÍD of the person we are looking for.
        nova_access: A token to access the KMD Nova API.

    Returns:
        The name of the person with the provided CPR.
    """
    address = nova_cpr.get_address_by_cpr(cpr, nova_access)
    if address:
        return address['name']
    for case in cases:
        for case_party in case.case_parties:
            if case_party.identification == cpr and case_party.name:
                return case_party.name
    return "No Name"


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
    caseworker = config.CASEWORKER

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
    """Make a department object from department code

    Args:
        department_code: A KMD code matching a department

    Returns:
        A Department object created from data in config
    """
    data = config.KMD_DEPARTMENTS[department_code]
    department = Department(
            id=int(data["id"]),
            name=data["name"],
            user_key=department_code
        )
    return department


def _find_matching_case(case_title: str, cases: list[NovaCase]) -> NovaCase:
    """ Lookup case match in list, based on case title.

    Args:
        cases: A list of cases to check
        data_dict: A dictionary containing the data to check for
        ident, name: The identification and name to use if we need to create a new case
        nova_access: An access token to access the KMD Nova API

    Returns:
        A NovaCase matching the arguments provided.
    """
    for case in cases:
        if case.title == case_title:
            return case
    raise LookupError("Could not find matching case")
