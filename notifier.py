import requests
import os
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

def send_slack_message(message):
    """
    Sends a message to a Slack channel via an Incoming Webhook.
    """
    load_dotenv()
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")

    if not webhook_url:
        logger.warning("SLACK_WEBHOOK_URL not set in .env. Notification skipped.")
        return

    payload = {
        "text": message
    }

    try:
        response = requests.post(webhook_url, json=payload)
        response.raise_for_status()
        logger.info("Slack notification sent successfully.")
    except Exception as e:
        logger.error(f"Failed to send Slack notification: {e}")
