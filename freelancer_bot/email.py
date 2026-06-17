"""SMTP email sender with HTML + plain text multipart messages.

Uses Gmail SMTP by default. All credentials from environment variables.
"""

from __future__ import annotations

import os
import smtplib
import ssl
from dataclasses import dataclass, field
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class EmailConfig:
    """Email configuration — all secrets from env vars."""

    smtp_host: str = field(
        default_factory=lambda: os.environ.get("EMAIL_SMTP_HOST", "smtp.gmail.com")
    )
    smtp_port: int = field(
        default_factory=lambda: int(os.environ.get("EMAIL_SMTP_PORT", "587"))
    )
    username: str = field(
        default_factory=lambda: os.environ.get("EMAIL_USERNAME", "your_email@gmail.com")
    )
    password: str = field(
        default_factory=lambda: os.environ.get("EMAIL_PASSWORD", "")
    )
    from_addr: str = field(
        default_factory=lambda: os.environ.get("EMAIL_FROM", "your_email@gmail.com")
    )
    to_addr: str = field(
        default_factory=lambda: os.environ.get("EMAIL_TO", "your_email@gmail.com")
    )
    use_tls: bool = True


@dataclass
class EmailSender:
    """Send HTML + plain text emails via SMTP."""

    config: EmailConfig = field(default_factory=EmailConfig)

    def send(
        self,
        subject: str,
        html_body: str,
        plain_body: str | None = None,
        *,
        to_addr: str | None = None,
        dry_run: bool = False,
    ) -> bool:
        """Send a multipart email (HTML + plain text).

        Returns True on success, False on failure.
        """
        if dry_run:
            logger.info(
                "email_dry_run",
                subject=subject,
                to=to_addr or self.config.to_addr,
                html_len=len(html_body),
            )
            return True

        if not self.config.password:
            logger.error("email_no_password", hint="Set EMAIL_PASSWORD environment variable")
            return False

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.config.from_addr
        msg["To"] = to_addr or self.config.to_addr

        if plain_body:
            msg.attach(MIMEText(plain_body, "plain", "utf-8"))
        else:
            # Strip HTML tags for plain text fallback
            import re
            plain = re.sub(r"<[^>]+>", "", html_body)
            plain = re.sub(r"\s+", " ", plain).strip()
            msg.attach(MIMEText(plain, "plain", "utf-8"))

        msg.attach(MIMEText(html_body, "html", "utf-8"))

        try:
            context = ssl.create_default_context() if self.config.use_tls else None
            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
                server.ehlo()
                if self.config.use_tls:
                    server.starttls(context=context)
                    server.ehlo()
                server.login(self.config.username, self.config.password)
                server.send_message(msg)
            logger.info("email_sent", subject=subject, to=msg["To"])
            return True
        except smtplib.SMTPAuthenticationError:
            logger.error("email_auth_failed", hint="Check EMAIL_PASSWORD")
            return False
        except smtplib.SMTPException as e:
            logger.error("email_send_failed", error=str(e)[:200])
            return False
        except OSError as e:
            logger.error("email_network_error", error=str(e)[:200])
            return False

    def send_report(
        self,
        subject: str,
        summary: str,
        details: list[dict[str, Any]],
        *,
        report_type: str = "bidding",
        dry_run: bool = False,
    ) -> bool:
        """Send a formatted report email with summary and details table.

        Args:
            subject: Email subject line
            summary: Plain text summary paragraph
            details: List of dicts with keys: title, link, score, bid, status
            report_type: "bidding", "contests", or "design"
            dry_run: If True, log but don't send
        """
        html = self._build_report_html(subject, summary, details, report_type)
        plain = self._build_report_plain(subject, summary, details)
        return self.send(subject, html, plain, dry_run=dry_run)

    def _build_report_html(
        self,
        subject: str,
        summary: str,
        details: list[dict[str, Any]],
        report_type: str,
    ) -> str:
        """Build HTML report email."""
        rows_html = ""
        for d in details:
            link = d.get("link", "")
            title = d.get("title", "Untitled")
            score = d.get("score", "—")
            bid = d.get("bid", "—")
            status = d.get("status", "—")
            status_color = {
                "bid": "#22c55e",
                "skipped": "#f59e0b",
                "failed": "#ef4444",
                "entered": "#22c55e",
                "discovered": "#3b82f6",
            }.get(status, "#6b7280")

            rows_html += f"""
            <tr>
                <td style="padding:8px;border-bottom:1px solid #e5e7eb">
                    <a href="{link}" style="color:#2563eb;text-decoration:none">{title}</a>
                </td>
                <td style="padding:8px;border-bottom:1px solid #e5e7eb;text-align:center">{score}</td>
                <td style="padding:8px;border-bottom:1px solid #e5e7eb;text-align:center">{bid}</td>
                <td style="padding:8px;border-bottom:1px solid #e5e7eb;text-align:center">
                    <span style="color:{status_color};font-weight:600">{status}</span>
                </td>
            </tr>"""

        return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,sans-serif;max-width:640px;margin:0 auto;padding:20px;color:#1f2937">
    <h1 style="color:#111827;font-size:24px;margin-bottom:8px">{subject}</h1>
    <p style="color:#4b5563;font-size:14px;line-height:1.6;margin-bottom:24px">{summary}</p>
    <table style="width:100%;border-collapse:collapse;font-size:14px">
        <thead>
            <tr style="background:#f3f4f6">
                <th style="padding:8px;text-align:left;border-bottom:2px solid #d1d5db">Project/Contest</th>
                <th style="padding:8px;text-align:center;border-bottom:2px solid #d1d5db">Score</th>
                <th style="padding:8px;text-align:center;border-bottom:2px solid #d1d5db">Bid/Prize</th>
                <th style="padding:8px;text-align:center;border-bottom:2px solid #d1d5db">Status</th>
            </tr>
        </thead>
        <tbody>{rows_html}
        </tbody>
    </table>
    <p style="color:#9ca3af;font-size:12px;margin-top:24px;border-top:1px solid #e5e7eb;padding-top:12px">
        Freelancer Bot v2 — Automated {report_type} report
    </p>
</body>
</html>"""

    def _build_report_plain(
        self,
        subject: str,
        summary: str,
        details: list[dict[str, Any]],
    ) -> str:
        """Build plain text report email."""
        lines = [subject, "=" * len(subject), "", summary, ""]
        for d in details:
            title = d.get("title", "Untitled")
            score = d.get("score", "—")
            bid = d.get("bid", "—")
            status = d.get("status", "—")
            link = d.get("link", "")
            lines.append(f"  [{status.upper()}] {title} (Score: {score}, Bid: {bid})")
            if link:
                lines.append(f"         {link}")
        lines.append("")
        lines.append("— Freelancer Bot v2")
        return "\n".join(lines)
