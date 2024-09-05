''' Convert OS2 Emails to dictionaries '''
from bs4 import BeautifulSoup


def html_to_dict(html_content) -> dict:
    ''' Convert OS2 Emails to dictionaries.

    Args:
        html_content: OS2 email content containing bold headlines followed by data
    '''
    # Parse the HTML content
    soup = BeautifulSoup(html_content, 'html.parser')

    result = {}
    for p in soup.find_all('p'):
        parts = p.get_text(separator='|').split('|')
        if len(parts) == 2:
            key, value = parts
            result[key.strip()] = value.strip()

    email_tag = soup.find('a', href=True, text=lambda text: text and '@' in text)
    if email_tag:
        email = email_tag.get_text()
        az_ident = email_tag.find_next_sibling(text=True).strip().split(': ')[1]
        result['Bruger'] = f"E-mail: {email}, AZ-ident: {az_ident}"

    return result
