# @See: https://www.mailersend.com/blog/send-email-with-python

import os
from dotenv import load_dotenv

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

import sys, traceback

# Load environment variables from .env file
load_dotenv()

# Set up email details from environment variables
sender_email = os.getenv("SENDER_EMAIL")
password = os.getenv("EMAIL_PASSWORD")
smtp_server = os.getenv("SMTP_SERVER")
smtp_port = int(os.getenv("SMTP_PORT"))
recipients = os.getenv("EMAIL_RECIPIENTS")

def send_report(reporter, email_config):

    # Subject using the reporter get_project_name
    subject = f"SEO Sentinel Report for: {reporter.project_name}"

    body = ""
    # Append the failed checks to the body
    log = reporter.get_check_failed_log()
    if len(log) > 0:
        body += f"<h2>Errors found in {reporter.project_name}</h2>\n"
        for issue in log:
            body += f"<p>{issue}</p>\n"

    # Append the warnings to the body
    log = reporter.get_warning_log()
    if len(log) > 0:
        body += f"<h2>Warnings found in {reporter.project_name}</h2>\n"
        for issue in log:
            body += f"<p>{issue}</p>\n"

    if email_config.get("send", "always") == "always":
        # Check passed
        log = reporter.get_check_passed_log()
        if len(log) > 0:
            body += f"<h2>Checks passed in {reporter.project_name}</h2>\n"
            for issue in log:
                body += f"<p>{issue}</p>\n"

        # Info log
        log = reporter.get_info_log()
        if len(log) > 0:
            body += f"<h2>Info found in {reporter.project_name}</h2>\n"
            for issue in log:
                body += f"<p>{issue}</p>\n"

        
    # If there is a body, send the email
    if len(body) > 0:

        # Create the email message
        message = MIMEMultipart()
        message["From"] = sender_email
        message["To"] = recipients
        message["Subject"] = subject

        # Attach the email body to the message
        message.attach(MIMEText(body, "html"))

        # Establish a connection to the SMTP server and send the email
        try:
            # Connect to the SMTP server
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()  # Secure the connection
                server.login(sender_email, password)  # Log in to the SMTP server
                server.sendmail(
                    sender_email, recipients, message.as_string()
                )  # Send the email
            print("Email sent successfully")
        except Exception:
            # Print the traceback if an error occurs
            traceback.print_exc()