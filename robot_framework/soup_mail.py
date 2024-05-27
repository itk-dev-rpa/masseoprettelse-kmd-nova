''' Convert OS2 Emails to dictionaries '''
from bs4 import BeautifulSoup


def html_to_dict(html_content) -> dict:
    ''' Convert OS2 Emails to dictionaries.

    Args:
        html_content: OS2 email content containing bold headlines followed by data
    '''
    # Parse the HTML content
    soup = BeautifulSoup(html_content, 'html.parser')
    bold_tags = soup.find_all('b')
    email_dict = {}

    for bold_tag in bold_tags:
        # Get the headline text
        headline = bold_tag.get_text(strip=True)

        # Find the next sibling that is not a tag (usually the text part)
        next_sibling = bold_tag.next_sibling
        values = []

        while next_sibling and next_sibling not in bold_tags:
            if isinstance(next_sibling, str):
                values.append(next_sibling.strip())

            next_sibling = next_sibling.next_sibling

        email_dict[headline] = "\n".join(values)

    return email_dict
