from __future__ import annotations

import hashlib
import os
import sys
import json
import subprocess
import time
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses
from pathlib import Path
from typing import Protocol

from .db import RadarDB
from .transitions import ContractError


class MailTransport(Protocol):
    def find_verified(self, subject: str, recipient: str) -> str | None: ...
    def send_and_verify(self, subject: str, recipient: str, body: str) -> str: ...


def headers_match(exported: bytes, subject: str, recipient: str) -> bool:
    message = BytesParser(policy=policy.default).parsebytes(exported)
    recipients = [address.lower() for _, address in getaddresses(message.get_all("to", []))]
    return str(message.get("subject", "")) == subject and recipients == [recipient.lower()]


def subject_search_token(subject: str) -> str:
    token = subject.split()[-1].strip("[]") if subject.split() else ""
    if not token or any(character.isspace() for character in token):
        raise ContractError("mail subject needs a unique final search token")
    return token


class HimalayaTransport:
    def __init__(
        self,
        *,
        sender: str | None = None,
        sent_folder: str = "INBOX.Sent",
        markdown_helper: Path | None = None,
        markdown_python: Path | None = None,
    ) -> None:
        # Export default is closed even on a host with an existing mail account.
        if os.environ.get("OPPORTUNITY_RADAR_ENABLE_MAIL") != "1":
            raise ContractError("live mail disabled; explicit configuration required")
        sender = sender or os.environ.get("OPPORTUNITY_RADAR_SENDER")
        helper = markdown_helper or os.environ.get("OPPORTUNITY_RADAR_MARKDOWN_HELPER")
        if not sender or not helper or not Path(helper).is_file():
            raise ContractError("explicit sender and existing Markdown helper required")
        markdown_helper = Path(helper)
        markdown_python = markdown_python or Path(sys.executable)
        self.sender = sender
        self.sent_folder = sent_folder
        self.markdown_helper = markdown_helper
        self.markdown_python = markdown_python

    def _verified_message(self, message_id: str, subject: str, recipient: str) -> bool:
        exported = subprocess.run(
            ["himalaya", "message", "export", "--folder", self.sent_folder, str(message_id), "--full"],
            capture_output=True,
            check=True,
        ).stdout
        return headers_match(exported, subject, recipient)

    def find_verified(self, subject: str, recipient: str) -> str | None:
        listed = subprocess.run(
            ["himalaya", "envelope", "list", "--folder", self.sent_folder, "--page-size", "30", "--output", "json", "subject", subject_search_token(subject)],
            text=True,
            capture_output=True,
        )
        if listed.returncode != 0 or listed.stderr.strip():
            raise ContractError(f"Sent search failed: {listed.stderr.strip() or listed.returncode}")
        rows = json.loads(listed.stdout or "[]")
        for row in reversed(rows):
            if str(row.get("subject", "")) != subject:
                continue
            message_id = str(row["id"])
            if self._verified_message(message_id, subject, recipient):
                return message_id
        return None

    def send_and_verify(self, subject: str, recipient: str, body: str) -> str:
        rendered = subprocess.run(
            [str(self.markdown_python), str(self.markdown_helper), "--to", recipient, "--subject", subject, "--from", self.sender],
            input=body,
            text=True,
            capture_output=True,
        )
        if rendered.returncode != 0:
            detail = rendered.stderr.strip() or rendered.stdout.strip() or f"exit {rendered.returncode}"
            raise ContractError(f"Markdown mail render failed: {detail}")
        sent = subprocess.run(
            ["himalaya", "template", "send"],
            input=rendered.stdout,
            text=True,
            capture_output=True,
        )
        if sent.returncode != 0:
            detail = sent.stderr.strip() or sent.stdout.strip() or f"exit {sent.returncode}"
            raise ContractError(f"Himalaya send failed: {detail}")
        for delay in (0.5, 1.0, 2.0, 4.0):
            message_id = self.find_verified(subject, recipient)
            if message_id is not None:
                return message_id
            time.sleep(delay)
        raise ContractError("mail sent but exact Sent verification failed")


def mail_attempt_path(radar: RadarDB, delivery_key: str) -> Path:
    name = hashlib.sha256(delivery_key.encode("utf-8")).hexdigest() + ".pending"
    return radar.path.parent / "mail-attempts" / name


def deliver_mail_once(
    radar: RadarDB,
    transport: MailTransport,
    delivery_key: str,
    subject: str,
    recipient: str,
    body: str,
    *,
    event_ids: list[int] | None = None,
) -> dict[str, str]:
    # Event callers hold their flock through marking and pending removal.
    # Retain their pending record even after receipt commit to close that crash gap.
    body_sha256 = hashlib.sha256(body.encode("utf-8")).hexdigest()
    identity = dict(delivery_key=delivery_key, subject=subject,
                    recipient=recipient, body_sha256=body_sha256)
    if event_ids is not None and (
        not event_ids or any(type(value) is not int or value <= 0 for value in event_ids)
        or len(set(event_ids)) != len(event_ids)
    ):
        raise ContractError("event batch needs unique positive event IDs")
    attempt_path = mail_attempt_path(radar, delivery_key)
    attempt_directory = attempt_path.parent
    pending = None
    if attempt_path.exists():
        pending = json.loads(attempt_path.read_text(encoding="utf-8"))
        if not isinstance(pending, dict) or any(pending.get(k) != v for k, v in identity.items()):
            raise ContractError("prior mail attempt has different or unbound identity/body bytes; reconcile before retry")
        if pending.get("event_ids") != event_ids or (event_ids is not None and pending.get("body") != body):
            raise ContractError("prior event batch has different or unbound event IDs/body bytes")
    receipt = radar.get_mail_receipt(delivery_key)
    if receipt is not None:
        if any(receipt.get(k) != v for k, v in identity.items()):
            raise ContractError("delivery identity already belongs to different or historically unbound identity/body bytes; reconcile explicitly")
        return {"status": "already_delivered", "message_id": str(receipt["sent_message_id"])}
    if pending is not None:
        message_id = transport.find_verified(subject, recipient)
        if message_id is None:
            raise ContractError(
                "prior mail delivery attempt is unresolved; reconcile Sent before retrying SMTP"
            )
        radar.record_mail_receipt(delivery_key, subject, recipient, message_id, body_sha256)
        if event_ids is None:
            attempt_path.unlink()
        return {"status": "recovered_from_sent", "message_id": message_id}
    message_id = transport.find_verified(subject, recipient)
    if message_id is not None:
        raise ContractError("Sent header match has no bound body receipt; reconcile explicitly instead of claiming content delivery")
    status = "recovered_from_sent"
    if message_id is None:
        attempt_directory.mkdir(parents=True, exist_ok=True)
        attempt_path.write_text(
            json.dumps(
                {**identity, **({"event_ids": event_ids, "body": body} if event_ids is not None else {})},
                ensure_ascii=False,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        message_id = transport.send_and_verify(subject, recipient, body)
        status = "sent"
    radar.record_mail_receipt(delivery_key, subject, recipient, message_id, body_sha256)
    if event_ids is None and attempt_path.exists():
        attempt_path.unlink()
    return {"status": status, "message_id": message_id}
