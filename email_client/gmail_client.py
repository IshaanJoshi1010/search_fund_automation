"""
Gmail API client.
Handles OAuth2 authentication and email sending with attachments.
Respects SFAO_DRY_RUN environment variable.
"""
import base64
import logging
import mimetypes
import os
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

# Gmail API scopes required
SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]


class GmailClient:
    """Authenticated Gmail API client."""

    def __init__(self):
        self.credentials_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
        self.token_file = os.getenv("GOOGLE_TOKEN_FILE", "token.json")
        self.sender_email = os.getenv("SENDER_EMAIL", "")
        self.dry_run = os.getenv("SFAO_DRY_RUN", "true").lower() == "true"
        self._service = None

    def _build_service(self):
        """Build and return an authenticated Gmail API service."""
        creds = None

        if Path(self.token_file).exists():
            creds = Credentials.from_authorized_user_file(self.token_file, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not Path(self.credentials_file).exists():
                    raise FileNotFoundError(
                        f"Gmail credentials file not found: {self.credentials_file}\n"
                        "Run: python main.py auth-gmail"
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, SCOPES
                )
                creds = flow.run_local_server(port=0)

            with open(self.token_file, "w") as token:
                token.write(creds.to_json())

        return build("gmail", "v1", credentials=creds)

    @property
    def service(self):
        if self._service is None:
            self._service = self._build_service()
        return self._service

    def run_oauth_flow(self):
        """Run the one-time OAuth browser flow explicitly."""
        if not Path(self.credentials_file).exists():
            raise FileNotFoundError(
                f"credentials.json not found. Download it from Google Cloud Console."
            )
        flow = InstalledAppFlow.from_client_secrets_file(self.credentials_file, SCOPES)
        creds = flow.run_local_server(port=0)
        with open(self.token_file, "w") as f:
            f.write(creds.to_json())
        logger.info("✓ Gmail authentication complete. token.json saved.")

    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        attachments: list[Path] | None = None,
        thread_id: str | None = None,
    ) -> dict:
        """
        Send a plain-text email via Gmail API.

        Returns:
            dict with message_id and thread_id for tracking.
            In dry_run mode, returns a fake dict and only logs.
        """
        if self.dry_run:
            logger.info(
                f"[DRY RUN] Would send to: {to}\n"
                f"  Subject: {subject}\n"
                f"  Body preview: {body[:200]}...\n"
                f"  Attachments: {[str(a) for a in (attachments or [])]}"
            )
            return {"message_id": "DRY_RUN_MSG_ID", "thread_id": "DRY_RUN_THREAD_ID"}

        message = self._build_message(to, subject, body, attachments, thread_id)

        try:
            send_args: dict = {
                "userId": "me",
                "body": message,
            }
            result = self.service.users().messages().send(**send_args).execute()
            msg_id = result.get("id")
            t_id = result.get("threadId")
            logger.info(f"✓ Email sent to {to} | message_id={msg_id} thread_id={t_id}")
            return {"message_id": msg_id, "thread_id": t_id}
        except HttpError as e:
            logger.error(f"Gmail API error sending to {to}: {e}")
            raise

    def _build_message(
        self,
        to: str,
        subject: str,
        body: str,
        attachments: list[Path] | None,
        thread_id: str | None,
    ) -> dict:
        """Build the RFC 2822 MIME message and encode for Gmail API."""
        msg = MIMEMultipart()
        msg["To"] = to
        msg["From"] = self.sender_email
        msg["Subject"] = subject

        if thread_id:
            msg["References"] = thread_id
            msg["In-Reply-To"] = thread_id

        msg.attach(MIMEText(body, "plain"))

        for attachment_path in (attachments or []):
            if not attachment_path.exists():
                logger.warning(f"Attachment not found, skipping: {attachment_path}")
                continue
            mime_type, _ = mimetypes.guess_type(str(attachment_path))
            main_type, sub_type = (mime_type or "application/octet-stream").split("/", 1)
            with open(attachment_path, "rb") as f:
                part = MIMEApplication(f.read(), Name=attachment_path.name)
            part["Content-Disposition"] = f'attachment; filename="{attachment_path.name}"'
            msg.attach(part)

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
        payload: dict = {"raw": raw}
        if thread_id:
            payload["threadId"] = thread_id
        return payload

    def get_thread_replies(self, thread_id: str) -> list[dict]:
        """Return messages in a thread (for reply detection), including headers."""
        try:
            thread = self.service.users().threads().get(
                userId="me", id=thread_id, format="metadata",
                metadataHeaders=["From", "To", "Subject"],
            ).execute()
            return thread.get("messages", [])
        except HttpError as e:
            logger.error(f"Error fetching thread {thread_id}: {e}")
            return []
