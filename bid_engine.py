import os
import re
from typing import Optional, Tuple
from models import JobLead, ContractorProfile

class BidEngine:
    def __init__(self, profile: ContractorProfile):
        self.profile = profile
        self.gemini_client = None
        self._init_gemini()

    def _init_gemini(self):
        """Attempt to load Gemini API client if API key exists in environment."""
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            try:
                from google import genai
                self.gemini_client = genai.Client(api_key=api_key)
            except Exception as e:
                print(f"[BidEngine] Gemini init skipped: {e}")

    def evaluate_and_bid(self, lead: JobLead) -> JobLead:
        """
        1. Filters out spam or non-contractor jobs (e.g. 9-to-5 W2 hiring).
        2. Estimates hours and calculates price based on contractor profile.
        3. Formulates a personalized pitch message for the homeowner.
        """
        is_valid, reason = self._validate_lead(lead)
        lead.is_valid_lead = is_valid
        lead.rejection_reason = reason

        if not is_valid:
            return lead

        # Calculate estimated price
        est_amount, price_range = self._calculate_estimate(lead)
        lead.suggested_bid_amount = est_amount
        lead.bid_price_range = price_range

        # Generate proposal message
        lead.generated_proposal = self._generate_proposal(lead)
        return lead

    def _validate_lead(self, lead: JobLead) -> Tuple[bool, Optional[str]]:
        text = f"{lead.title} {lead.description}".lower()

        # Reject full-time employee recruitment, spam, and for-sale items
        disqualifiers = [
            "w-2", "w2", "full time position", "salary + benefits",
            "seeking full-time employee", "telemarketing", "crypto",
            "work from home data entry", "for sale", "selling", "tool set",
            "pickup only", "miles &", "miles on", "re-sale", "shipping available",
            "cash and carry"
        ]
        for dq in disqualifiers:
            if dq in text:
                return False, f"Not an active service gig (matched '{dq}')"

        # Check for service intent (homeowner wanting work done)
        intent_keywords = [
            "need", "looking for", "help", "repair", "replace", "install",
            "leak", "fix", "jammed", "clog", "patch", "troubleshoot",
            "service", "quote", "job", "broken", "contractor", "licensed"
        ]
        has_intent = any(ik in text for ik in intent_keywords)
        if not has_intent and lead.source != "Residential Lead Feed":
            return False, "No active service/hiring intent detected (likely item for sale or ad)"

        # Check if trade matches
        trade_keywords = {
            "plumbing": ["plumb", "pipe", "leak", "faucet", "drain", "water heater", "toilet", "clog", "shutoff"],
            "painting": ["paint", "drywall", "stain", "primer", "roller", "interior paint", "exterior paint"],
            "electrical": ["electric", "wire", "outlet", "switch", "breaker", "panel", "ceiling fan", "ev charger", "lighting"],
            "handyman": ["handyman", "fix", "install", "assemble", "repair", "mount", "patch", "caulk"],
            "roofing": ["roof", "shingle", "gutter", "flashing", "leak in roof"],
            "hvac": ["hvac", "ac", "air condition", "furnace", "thermostat", "heat pump"]
        }

        keywords = trade_keywords.get(self.profile.trade.lower(), [self.profile.trade.lower()])
        has_trade_keyword = any(kw in text for kw in keywords)

        if not has_trade_keyword and lead.source != "Residential Lead Feed":
            return False, f"Does not appear relevant to {self.profile.trade}"

        return True, None

    def _calculate_estimate(self, lead: JobLead) -> Tuple[float, str]:
        text = f"{lead.title} {lead.description}".lower()

        # Rule-based hour estimation heuristic
        est_hours = 2.0  # default residential small repair

        if any(w in text for w in ["large", "entire", "whole house", "multiple rooms", "panel upgrade", "re-pipe"]):
            est_hours = 8.0
        elif any(w in text for w in ["room", "assemble 3", "2 faucets", "both", "multiple"]):
            est_hours = 4.0
        elif any(w in text for w in ["quick", "small patch", "single", "one outlet", "faucet handle", "jammed"]):
            est_hours = 1.5

        raw_price = max(self.profile.min_callout_fee, est_hours * self.profile.hourly_rate)

        # Build reasonable price range (+/- 15%)
        low_bound = round(raw_price * 0.90, -1)
        high_bound = round(raw_price * 1.20, -1)
        price_range = f"${int(low_bound)} - ${int(high_bound)}"

        return raw_price, price_range

    def _generate_proposal(self, lead: JobLead) -> str:
        """Generate response message tailored for speed-to-lead."""
        if self.gemini_client:
            try:
                prompt = (
                    f"You are a friendly, professional residential contractor ({self.profile.company_name}, "
                    f"contact: {self.profile.contact_name}, phone: {self.profile.phone}).\n"
                    f"Homeowner posted this job: '{lead.title}' - '{lead.description}'.\n"
                    f"Estimated price range is {lead.bid_price_range}.\n"
                    f"Write a concise (max 3 sentences) bid proposal message to the homeowner to win this job."
                )
                response = self.gemini_client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt
                )
                if response and response.text:
                    return response.text.strip()
            except Exception as e:
                pass

        # Robust deterministic proposal generator
        lic_str = f" Fully licensed (#{self.profile.license_number}) and insured." if self.profile.license_number else " Fully insured."
        proposal = (
            f"Hi there! This is {self.profile.contact_name} with {self.profile.company_name}. "
            f"We specialize in residential {self.profile.trade} in your area and can easily take care of this for you.{lic_str} "
            f"For this scope, our typical price ranges between {lead.bid_price_range}. "
            f"We have open availability this week—let me know when is best to stop by or call {self.profile.phone} to lock in a time!"
        )
        return proposal
