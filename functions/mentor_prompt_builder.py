from constants.mentor_message import mentor_prompt
from toon import encode


def get_system_prompt(financial_summary: dict) -> str:
    data = encode(financial_summary)
    return mentor_prompt.format(
        financial_data=data
    )
