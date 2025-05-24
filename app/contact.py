import base64
import logging
import pathlib
from collections.abc import Iterable
from dataclasses import dataclass, field
from http import HTTPStatus

import streamlit as st
from common import CurrentUser, check_access
from config import settings
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import (
    Attachment,
    Cc,
    Content,
    Disposition,
    Email,
    FileContent,
    FileName,
    FileType,
    Header,
    Mail,
    To,
)
from validate_email import validate_email

logger = logging.getLogger(settings.LOGGER_NAME)


@dataclass(frozen=True)
class MailAttachment:
    """Class to store attached files with their mime type"""

    file_path: pathlib.Path = field(
        metadata={"description": "The path to the file to attach"}
    )
    mime_type: str = field(
        metadata={"description": "The mime type like text/plain or application/excel"}
    )


def send_email(
    sendgrid_api_key: str,
    mail_from: str,
    subject: str,
    email_to: Iterable[str],
    email_cc: Iterable[str],
    email_body: str,
    content_type: str = "text/html",
    reply_to: str | None = None,
    attachments: list[MailAttachment] | None = None,
    mail_headers: dict[str, str] | None = None,
) -> int:
    """
    Send an email with optional attachments.

    Args:
        sendgrid_api_key (str): The sendgrid API key. If None we read env variable SENDGRID_API_KEY
        mail_from (str): sender of the email
        subject (str): subject
        email_to (tuple): recipients
        email_cc (tuple): cc recipients
        email_body (str): email body
        content_type (str): Either text/html or text/plain
        reply_to (str): Optional reply to
        attachments (list[Attachment]): List of attached files
        mail_headers (dict): Dictionary of mail headers like {'Importance': 'high'}

    Returns:
        status code (202 means success)

    """
    if not sendgrid_api_key:
        sendgrid_api_key = settings.SENDGRID_API_KEY
    # See here: https://docs.sendgrid.com/for-developers/sending-email/quickstart-python
    from_email = Email(mail_from)
    to_emails = [To(to) for to in email_to]

    # Having a "to" address in cc makes the send fail with error 400
    cc_emails = [Cc(cc) for cc in email_cc if cc not in email_to]

    content = Content(content_type, email_body)
    message = Mail(
        from_email=from_email,
        to_emails=to_emails,
        subject=subject,
        plain_text_content=content,
    )
    message.add_cc(cc_emails)
    if reply_to:
        message.reply_to = reply_to
    if mail_headers:
        headers: list[Header] = []
        for k, v in mail_headers.items():
            headers.append(Header(k, v))
        message.header = headers

    if attachments is None:
        attachments = []

    for attachment in attachments:
        with attachment.file_path.open("rb") as f:
            data = f.read()
            file_name = pathlib.Path(attachment.file_path).name

        encoded_file = base64.b64encode(data).decode()
        attached_file = Attachment(
            FileContent(encoded_file),
            FileName(file_name),
            FileType(attachment.mime_type),
            Disposition("attachment"),
        )
        message.attachment = attached_file  # The setter will add it
    #    print(f'Number of attachments: {len(mail.attachments)}')
    # mail_json = message.get()

    try:
        sg = SendGridAPIClient(sendgrid_api_key)
        # response = sg.client.mail.send.post(request_body=mail_json)
        response = sg.send(message)
    except Exception as error:
        logger.exception(f"Error: {error}")
        logger.error(f"Recipients: to={';'.join(email_to)}, cc={';'.join(email_cc)}")
        raise
    else:
        logger.info(f"Email sent to: {';'.join(email_to)}, cc: {';'.join(email_cc)}")
        if response.status_code != HTTPStatus.ACCEPTED:
            logger.error(f"Response code: {response.status_code}")
            logger.error(f"Response headers: {response.headers}")
            logger.error(f"Response body: {response.body}")

    return response.status_code


def render_contact_form() -> None:
    # st.write("## Send us a message")
    current_user = CurrentUser.get_from_session_state()
    with st.form(key="contact_form"):
        email_to = st.text_input(
            label="Send To",
            value="support@acme.com",
            disabled=not check_access(st.session_state.username, "full_menu", "show"),
        )

        contact_name = st.text_input(
            label="Your Name:",
            placeholder="John Doe",
            value=current_user.display_name,
        )
        contact_email = st.text_input(
            label="Your Email:",
            placeholder="john.doe@acme.com",
            value=current_user.email,
        )
        # st.divider()
        subject = st.text_input("Subject:", max_chars=80)
        message = st.text_area("Your message:", max_chars=200)
        if st.form_submit_button("Send"):
            if contact_email and contact_name and subject and message:
                if not validate_email(contact_email):
                    st.error(f"Invalid Email: {contact_email!a}")
                else:
                    email_to = email_to or "support@acme.com"
                    full_message = f"""
--- Message send via UI from {contact_name} <{contact_email}> [{st.session_state.username}]
Click "reply" to answer the sender.

Content:
===
{message}
===
"""  # noqa: F841
                    api_key = settings.SENDGRID_API_KEY
                    if api_key is None:
                        st.error(
                            "Configuration Error. Please set env variable SENDGRID_API_KEY"
                        )
                        st.stop()

                    st.toast("Thank you for your message, but Email is not implemented")
                    # st.balloons()

            else:
                st.error("Please enter all information")
