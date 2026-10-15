from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
import uvicorn
import os

from models import ContractorProfile, JobLead
from scrapers.craigslist import CraigslistScraper
from scrapers.lead_portal_sim import PortalSimulatorScraper
from bid_engine import BidEngine
from alert_service import AlertService

app = FastAPI(title="TradeBid - Automated Residential Contractor Bidding")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for contractor profile & leads
current_profile = ContractorProfile(
    trade="plumbing",
    company_name="Apex Home Solutions",
    contact_name="Mike Miller",
    phone="(555) 234-5678",
    email="mike@apexhome.com",
    hourly_rate=95.0,
    min_callout_fee=150.0,
    service_radius_miles=30,
    license_number="LIC-849204",
    auto_pilot=False,
    target_city="Austin"
)

leads_db: Dict[str, JobLead] = {}
alert_service = AlertService(current_profile)

class ProfileUpdate(BaseModel):
    trade: str
    company_name: str
    contact_name: str
    phone: str
    email: str
    hourly_rate: float
    min_callout_fee: float
    service_radius_miles: int
    license_number: Optional[str] = None
    auto_pilot: bool = False
    target_city: str = "Austin"

class BidSubmission(BaseModel):
    custom_proposal: Optional[str] = None
    custom_price: Optional[str] = None

class SMSReplySim(BaseModel):
    message: str

@app.get("/api/profile")
def get_profile():
    return current_profile.__dict__

@app.post("/api/profile")
def update_profile(data: ProfileUpdate):
    global current_profile, alert_service
    for k, v in data.model_dump().items():
        setattr(current_profile, k, v)
    alert_service = AlertService(current_profile)
    return {"status": "success", "profile": current_profile.__dict__}

@app.get("/api/leads")
def get_leads():
    return list(leads_db.values())

@app.post("/api/scan")
def scan_leads():
    trade = current_profile.trade
    city = current_profile.target_city

    scrapers = [CraigslistScraper(), PortalSimulatorScraper()]
    engine = BidEngine(current_profile)

    new_count = 0
    for scraper in scrapers:
        try:
            leads = scraper.search_jobs(trade=trade, location=city, limit=5)
            for raw_lead in leads:
                evaluated = engine.evaluate_and_bid(raw_lead)
                
                # Check auto-pilot setting
                if evaluated.is_valid_lead and current_profile.auto_pilot:
                    evaluated.status = "SUBMITTED"

                leads_db[evaluated.id] = evaluated
                new_count += 1
        except Exception as e:
            print(f"[Scan Error] {e}")

    return {
        "status": "success",
        "scanned_count": new_count,
        "total_in_db": len(leads_db),
        "leads": list(leads_db.values())
    }

@app.post("/api/leads/{lead_id}/bid")
def submit_bid(lead_id: str, payload: Optional[BidSubmission] = None):
    lead = leads_db.get(lead_id)
    if not lead:
        return JSONResponse({"error": "Lead not found"}, status_code=404)

    lead.status = "SUBMITTED"
    if payload and payload.custom_proposal:
        lead.generated_proposal = payload.custom_proposal
    if payload and payload.custom_price:
        lead.bid_price_range = payload.custom_price

    return {"status": "success", "message": f"Bid submitted for {lead.title}", "lead": lead}

@app.post("/api/leads/{lead_id}/pass")
def pass_lead(lead_id: str):
    lead = leads_db.get(lead_id)
    if not lead:
        return JSONResponse({"error": "Lead not found"}, status_code=404)
    lead.status = "DECLINED"
    return {"status": "success", "lead": lead}

@app.post("/api/leads/{lead_id}/send-sms")
def send_sms_alert(lead_id: str):
    lead = leads_db.get(lead_id)
    if not lead:
        return JSONResponse({"error": "Lead not found"}, status_code=404)
    
    result = alert_service.send_lead_alert(lead)
    return {"status": "success", "result": result}

@app.post("/api/sms/simulate-reply")
def simulate_sms_reply(payload: SMSReplySim):
    reply_response = alert_service.handle_inbound_sms(
        sender=current_profile.phone,
        body=payload.message,
        leads_db=leads_db
    )
    return {"response": reply_response, "leads": list(leads_db.values())}

@app.post("/api/sms/webhook")
async def twilio_webhook(request: Request):
    """Twilio incoming webhook endpoint for real SMS replies"""
    form_data = await request.form()
    body = form_data.get("Body", "")
    sender = form_data.get("From", "")
    reply = alert_service.handle_inbound_sms(sender=sender, body=body, leads_db=leads_db)
    
    # Twilio XML response
    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{reply}</Message>
</Response>"""
    return HTMLResponse(content=xml_content, media_type="application/xml")

@app.get("/", response_class=HTMLResponse)
def get_dashboard():
    with open(os.path.join(os.path.dirname(__file__), "templates", "index.html"), "r", encoding="utf-8") as f:
        return f.read()

if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False)
