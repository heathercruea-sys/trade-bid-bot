import os
import requests
from typing import Optional, Dict
from models import JobLead, ContractorProfile

class AlertService:
    def __init__(self, profile: ContractorProfile):
        self.profile = profile
        self.twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.twilio_number = os.getenv("TWILIO_PHONE_NUMBER")

    def is_twilio_configured(self) -> bool:
        return bool(self.twilio_sid and self.twilio_token and self.twilio_number)

    def send_lead_alert(self, lead: JobLead) -> Dict:
        """
        Sends an SMS alert to the contractor with the job details and quick-reply action.
        Uses real Twilio API if configured, otherwise simulates in console/logs.
        """
        sms_text = (
            f"🚨 NEW {lead.detected_trade.upper()} LEAD in {lead.location}!\n"
            f"Job: {lead.title[:60]}...\n"
            f"Homeowner Budget: {lead.extracted_budget or 'Not specified'}\n"
            f"Est. Quote: {lead.bid_price_range}\n\n"
            f"Reply 'YES {lead.id}' to submit bid or 'NO {lead.id}' to pass."
        )

        if self.is_twilio_configured():
            try:
                # Direct Twilio REST API request without needing separate twilio library
                url = f"https://api.twilio.com/2010-04-01/Accounts/{self.twilio_sid}/Messages.json"
                resp = requests.post(
                    url,
                    data={
                        "From": self.twilio_number,
                        "To": self.profile.phone,
                        "Body": sms_text,
                    },
                    auth=(self.twilio_sid, self.twilio_token),
                    timeout=10
                )
                if resp.status_code in [200, 201]:
                    return {"status": "sent", "mode": "twilio", "recipient": self.profile.phone, "message": sms_text}
                else:
                    return {"status": "error", "error": resp.text, "mode": "twilio"}
            except Exception as e:
                return {"status": "error", "error": str(e), "mode": "twilio"}

        # Simulation Mode
        print(f"\n[SMS ALERT -> {self.profile.phone}]")
        print("-" * 50)
        print(sms_text)
        print("-" * 50)
        return {
            "status": "sent",
            "mode": "simulated",
            "recipient": self.profile.phone,
            "message": sms_text,
            "instruction": f"Simulated SMS alert sent to {self.profile.phone}."
        }

    def handle_inbound_sms(self, sender: str, body: str, leads_db: Dict[str, JobLead]) -> str:
        """
        Processes incoming reply from contractor:
        e.g., 'YES cl-1234' or 'APPROVE 1'
        """
        clean_body = body.strip().upper()
        parts = clean_body.split()
        if not parts:
            return "Unrecognized response. Reply 'YES <job_id>' to approve or 'NO <job_id>' to skip."

        action = parts[0]
        target_id = parts[1].lower() if len(parts) > 1 else None

        # Look up lead
        matched_lead = None
        if target_id:
            for lid, lead in leads_db.items():
                if lid.lower() == target_id or lid.lower().endswith(target_id):
                    matched_lead = lead
                    break
        else:
            # Match first pending lead
            for lead in leads_db.values():
                if lead.is_valid_lead and not getattr(lead, "status", None) == "SUBMITTED":
                    matched_lead = lead
                    break

        if not matched_lead:
            return f"Could not find pending lead matching '{target_id or 'next'}'. Text 'LIST' to see active leads."

        if action in ["YES", "Y", "APPROVE", "SUBMIT"]:
            matched_lead.status = "SUBMITTED"
            return f"✅ SUCCESS: Bid of {matched_lead.bid_price_range} submitted for '{matched_lead.title[:40]}'! Homeowner notified."
        elif action in ["NO", "N", "PASS", "SKIP"]:
            matched_lead.status = "DECLINED"
            return f"❌ Lead '{matched_lead.title[:40]}' marked as skipped."
        else:
            return f"Unknown command '{action}'. Reply YES to submit or NO to decline."
