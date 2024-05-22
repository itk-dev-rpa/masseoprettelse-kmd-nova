''' CaseMail class for representing data extracted from OS2 Forms emails
'''
import dataclasses


@dataclasses.dataclass
class CaseMail:
    ''' A dataclass for representing data extracted from OS2 Forms emails
    '''
    case_title: str
    kle: str
    proceeding_facet: str
    sensitivity: str
    note_title: str
    note_text: str
