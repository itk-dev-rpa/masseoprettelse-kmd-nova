''' Convert OS2 Emails to dictionaries '''
from bs4 import BeautifulSoup


def html_to_dict(html_content):
    ''' Convert OS2 Emails to dictionaries '''
    # Parse the HTML content
    soup = BeautifulSoup(html_content, 'html.parser')
    bold_tags = soup.find_all('b')
    email_dict = {}

    for bold_tag in bold_tags:
        # Get the headline text
        headline = bold_tag.get_text(strip=True)

        # Find the next sibling that is not a tag (usually the text part)
        next_sibling = bold_tag.next_sibling
        value = ""

        while next_sibling and not isinstance(next_sibling, str):
            next_sibling = next_sibling.next_sibling

        if next_sibling:
            value = next_sibling.strip()

        email_dict[headline] = value

    return email_dict
