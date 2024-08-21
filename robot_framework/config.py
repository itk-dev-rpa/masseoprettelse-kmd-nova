"""This module contains configuration constants used across the framework"""
from itk_dev_shared_components.kmd_nova.nova_objects import Caseworker

# The number of times the robot retries on an error before terminating.
MAX_RETRY_COUNT = 3

# Whether the robot should be marked as failed if MAX_RETRY_COUNT is reached.
FAIL_ROBOT_ON_TOO_MANY_ERRORS = True

# Process report email
SMTP_SERVER = "smtp.aarhuskommune.local"
SMTP_PORT = 25
SCREENSHOT_SENDER = "robot@friend.dk"
STATUS_SENDER = "itk-rpa@mkb.aarhus.dk"

# Constant/Credential names
ERROR_EMAIL = "Error Email"
NOVA_API = "Nova API"
GRAPH_API = "Graph API"

# Other
MAIL_SOURCE_FOLDER = "Indbakke/Masseoprettelse KMD Nova"
MAIL_INBOX_SUBJECT = "RPA - Masseoprettelse i KMD Nova (fra Selvbetjening.aarhuskommune.dk)"

# Queue specific configs
# ----------------------

# The name of the job queue (if any)
QUEUE_NAME = "Masseoprettelse i KMD Nova"

# The limit on how many queue elements to process
MAX_TASK_COUNT = 100

# ----------------------
# KMD Dictionaries
KMD_DEPARTMENTS = {
    "4BFOLKEREG": {"name": "Folkeregister og Sygesikring", "id": "70403"},
    "4BBORGER": {"name": "Borgerservice", "id": "818485"},
    "4BFRONT": {"name": "Frontbetjening", "id": "1061417"},
    "4BFRONTTEL": {"name": "Kontaktcentret", "id": "1061418"},
    "4BKONTROL": {"name": "Kontrolteamet", "id": "70363"},
    "4BOPKRÆV": {"name": "Opkrævningen", "id": "70391"},
}

KMD_DEPARTMENT_SECURITY_PAIR = {
    "4BFOLKEREG": "4BBORGER",
    "4BBORGER": "4BBORGER",
    "4BFRONT": "4BBORGER",
    "4BFRONTTEL": "4BBORGER",
    "4BKONTROL": "4BKONTROL",
    "4BOPKRÆV": "4BOPKRÆV",
}

KMD_SENSITIVITY = {
        "Fortrolige oplysninger": "Fortrolige",
        "Ikke fortrolige oplysninger": "IkkeFortrolige",
        "Særligt følsomme oplysninger": "SærligFølsomme",
        "Følsomme oplysninger": "Følsomme"
}

CASEWORKER = Caseworker(
        name='Rpabruger Rpa75 - MÅ IKKE SLETTES RITM0283472',
        ident='azrpa75',
        uuid='2382680f-58cd-4f6d-90fd-23e4ce0180ae'
    )
