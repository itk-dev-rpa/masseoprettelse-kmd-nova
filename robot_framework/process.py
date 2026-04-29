"""This module contains the main process of the robot."""

import json

from OpenOrchestrator.orchestrator_connection.connection import OrchestratorConnection
from itk_dev_shared_components.graph import authentication as graph_authentication
from itk_dev_shared_components.kmd_nova.authentication import NovaAccess

from robot_framework import config
from robot_framework.subprocess import masseoprettelse_mail, masseoprettelse_nova


def process(orchestrator_connection: OrchestratorConnection, queue_element_count: tuple[int]) -> None:
    """Do the primary process of the robot."""
    orchestrator_connection.log_trace("Running process.")

    graph_credentials = orchestrator_connection.get_credential(config.GRAPH_API)
    graph_access = graph_authentication.authorize_by_username_password(graph_credentials.username, **json.loads(graph_credentials.password))
    masseoprettelse_mail.create_queue_from_emails(orchestrator_connection, graph_access)

    nova_credentials = orchestrator_connection.get_credential(config.NOVA_API)
    nova_access = NovaAccess(nova_credentials.username, nova_credentials.password)
    masseoprettelse_nova.create_notes_from_queue(orchestrator_connection, nova_access, queue_element_count)
