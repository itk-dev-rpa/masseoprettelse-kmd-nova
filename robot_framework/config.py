"""This module contains configuration constants used across the framework"""

# The number of times the robot retries on an error before terminating.
MAX_RETRY_COUNT = 3

# Whether the robot should be marked as failed if MAX_RETRY_COUNT is reached.
FAIL_ROBOT_ON_TOO_MANY_ERRORS = True

# Error screenshot config
SMTP_SERVER = "smtp.aarhuskommune.local"
SMTP_PORT = 25
SCREENSHOT_SENDER = "robot@friend.dk"

# Email texts
SUBJECT_BASE = "Robotstatus for Masseoprettelse i KMD Nova: "
SUBJECT_SUCCESS = "OK"
SUBJECT_ERROR = "Fejl"
BODY_BASE = "Robotten 'Masseoprettelse i KMD Nova' "
BODY_SUCCESS = "er startet."
BODY_ERROR = "er blevet blokeret da du ikke har tilladelse til at køre den. Kontakt venligst RPA-teamet."

# Constant/Credential names
ERROR_EMAIL = "Error Email"
NOVA_API = "Nova API"
GRAPH_API = "Graph API"

# Other
MAIL_SOURCE_FOLDER = "Indbakke/Masseoprettelse KMD Nova"
STATUS_SENDER = "itk-rpa@mkb.aarhus.dk"

# Queue specific configs
# ----------------------

# The name of the job queue (if any)
QUEUE_NAME = "Masseoprettelse i KMD Nova"

# The limit on how many queue elements to process
MAX_TASK_COUNT = 100

# ----------------------
