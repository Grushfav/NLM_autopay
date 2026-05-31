"""Compatibility shim — see nlm_autopay.integration.email_sender."""

from nlm_autopay.integration.email_sender import EmailSender, build_email_sender

__all__ = ["EmailSender", "build_email_sender"]
