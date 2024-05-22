''' CaseMail class for representing data extracted from OS2 Forms emails
'''
import dataclasses


@dataclasses.dataclass
class CaseMail:
    ''' A dataclass for representing data extracted from OS2 Forms emails
    '''

    def __init__(self, case_title, kle, action_aspect, sensitivity, note_title, note_text):
        self.case_title = case_title
        self.kle = kle
        self.proceeding_facet = action_aspect
        self.sensitivity = _get_sensitivity_from_email(sensitivity)
        self.note_title = note_title
        self.note_text = note_text


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
