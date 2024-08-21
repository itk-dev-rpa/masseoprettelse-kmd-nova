"""This subprocess concerns mail functionality of the robot."""
import json
import re

from OpenOrchestrator.orchestrator_connection.connection import OrchestratorConnection
from itk_dev_shared_components.graph.authentication import GraphAccess
from itk_dev_shared_components.graph import mail as graph_mail
from itk_dev_shared_components.graph.mail import Email
from itk_dev_shared_components.smtp import smtp_util

from robot_framework import soup_mail
from robot_framework import config


def create_queue_from_emails(orchestrator_connection: OrchestratorConnection, graph_access: GraphAccess):
    """Create a queue by reading emails and delete the emails after.

    Args:
        orchestrator_connection: A way to access the orchestrator to create the queue elements
        graph_access: A token to access emails
    """
    # Check mailbox for emails to process
    emails = _get_emails(graph_access)
    emails.reverse()

    # Parse each mail and add data to KMD Nova
    for email in emails:
        # Get data from email
        data_dict = _parse_mail_text(email.body)
        user_az = _get_az_from_email(data_dict["Bruger"])
        user_email = _get_recipient_from_email(data_dict["Bruger"])
        is_user_recognized = _check_az(orchestrator_connection, user_az)
        _send_status_email(user_email, is_user_recognized, data_dict["Sagsoverskrift"])
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
    """Find az in user_data using regex"""
    pattern = r"\baz\d+\b"
    return re.findall(pattern, user_data)[0]


def _check_az(orchestrator_connection: OrchestratorConnection, email_az: str) -> bool:
    """Check AZ from email against accepted list of AZ in process arguments.

    Args:
        orchestrator_connection: Connection containing process arguments with some accepted AZs
        email_az: A user identification (AZ) read from an email
    """
    accepted_azs = json.loads(orchestrator_connection.process_arguments)["accepted_azs"]
    return email_az.lower() in [az.lower() for az in accepted_azs]


def _get_recipient_from_email(user_data: str) -> str:
    """Find email in user_data using regex"""
    pattern = r"E-mail: (\S+)"
    return re.findall(pattern, user_data)[0]


def _send_status_email(recipient: str, process_started: bool, case_name: str):
    """Send an email with variable text depending on whether the process started or not.

    Args:
        recipient: Who should receive the email.
        process_started: Checked to determine what text to add to the email.
        case_name: The case name to include in the subject of the mail.
    """
    subject = "Robotstatus for Masseoprettelse i KMD Nova: "
    text = "Robotten 'Masseoprettelse i KMD Nova' for sagen '" + case_name
    if process_started:
        subject += "STARTET"
        text += "' er startet og notater vil nu blive tilført de ønskede sagsnumre."
    else:
        subject += "BLOKERET"
        text += "' er blevet blokeret. Sagsbehandleren som aktiverede robotten har ikke fået tilladelse til at starte robotten. Kontakt venligst RPA-teamet ved at svare på denne mail, hvis I har brug for at tilføje nye brugere."
    text += "\n\nMvh. ITK RPA"
    smtp_util.send_email(
        receiver= recipient,
        sender=config.STATUS_SENDER,
        subject=subject,
        body=text,
        smtp_server=config.SMTP_SERVER,
        smtp_port=config.SMTP_PORT
    )


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
    """ From an email sent by the OS2 Forms form "Masseoprettelse i KMD Nova",
    create a new dictionary.

    Args:
        mail_text: Text from OS2 Forms that can be read by the robot.

    "Returns:
        A dictionary object, for easier access to variables.
    """
    dictionary = soup_mail.html_to_dict(mail_text)
    if dictionary["Brug eksisterende sag"] != "Valgt":
        dictionary["Følsomhed"] = _get_sensitivity_from_email(dictionary["Følsomhed"])
        dictionary["Sikkerhedsenhed"] = _get_securityunit_from_department(dictionary["Afdeling"])
    return dictionary


def _get_securityunit_from_department(email_string: str) -> str:
    """Translates the string from OS2 Department value to a security unit value

    Args:
        email_string: A string, matching the format in OS2 Forms and the emails sent to the robot.

    Returns:
        A string, matching the format expected by KMD Nova in the Security field. All options except two will return Borgerservice.
    """
    return config.KMD_DEPARTMENT_SECURITY_PAIR[email_string]


def _get_sensitivity_from_email(email_string: str) -> str:
    """Translates the string from OS2 forms to the expected KMD Nova format.

    Args:
        email_string: A string, matching the format in OS2 Forms and the emails sent to the robot.

    Returns:
        A string, matching the format expected by KMD Nova in the Sensitivity field.
    """
    return config.KMD_SENSITIVITY[email_string]


def _get_ids_from_mail(email: Email, graph_access: GraphAccess) -> list[str]:
    """ Open up attachment attached to an email and read the data contained.

    Args:
        email: An email.
        graph_access: The accesstoken required to read emails.

    Returns:
        A list of each line found in the attachments.
    """
    id_list = []
    attachments = graph_mail.list_email_attachments(email, graph_access)
    for attachment in attachments:
        email_attachment = graph_mail.get_attachment_data(attachment, graph_access)
        id_list = id_list + email_attachment.read().decode().split()

    id_list = [s.replace("-", "") for s in id_list]
    return id_list
