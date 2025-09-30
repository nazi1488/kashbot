"""
Services package for the Telegram bot
"""

from .gmail_aliases import generate_gmail_aliases, validate_gmail_input, GmailAliasGenerator

__all__ = [
    'generate_gmail_aliases',
    'validate_gmail_input', 
    'GmailAliasGenerator'
]
