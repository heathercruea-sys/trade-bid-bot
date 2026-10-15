import argparse
import json
import sys
from typing import List

from models import ContractorProfile, JobLead
from scrapers.craigslist import CraigslistScraper
from scrapers.lead_portal_sim import PortalSimulatorScraper
from bid_engine import BidEngine

def run_pipeline(trade: str, location: str, source: str, profile: ContractorProfile):
    print("=" * 65)
    print(f"  RESIDENTIAL TRADE BID BOT")
    print(f"  Target Trade   : {trade.upper()}")
    print(f"  Location       : {location}")
    print(f"  Contractor     : {profile.company_name} (${profile.hourly_rate}/hr)")
    print("=" * 65)

    scrapers = []
    if source in ["craigslist", "all"]:
        scrapers.append(CraigslistScraper())
    if source in ["portal", "all"]:
        scrapers.append(PortalSimulatorScraper())

    all_raw_leads: List[JobLead] = []
    for scraper in scrapers:
        print(f"\n[*] Scanning [{scraper.name}] for open {trade} jobs in {location}...")
        try:
            leads = scraper.search_jobs(trade=trade, location=location, limit=5)
            print(f"    -> Found {len(leads)} listings.")
            all_raw_leads.extend(leads)
        except Exception as e:
            print(f"    [!] Error running scraper {scraper.name}: {e}")

    if not all_raw_leads:
        print("\n[-] No listings found matching criteria. Try another city or trade.")
        return

    # Process and price through Bid Engine
    engine = BidEngine(profile)
    evaluated_leads: List[JobLead] = []

    print(f"\n[*] Evaluating and calculating bids for {len(all_raw_leads)} leads...\n")

    for lead in all_raw_leads:
        evaluated = engine.evaluate_and_bid(lead)
        evaluated_leads.append(evaluated)

    # Display results
    qualified_count = sum(1 for l in evaluated_leads if l.is_valid_lead)
    print("=" * 65)
    print(f"  RESULTS SUMMARY: {qualified_count}/{len(evaluated_leads)} Qualified for Bidding")
    print("=" * 65)

    for i, lead in enumerate(evaluated_leads, 1):
        status = "[READY TO BID]" if lead.is_valid_lead else "[SKIPPED]"
        print(f"\n--- Job #{i}: {status} ---")
        print(f"Title     : {lead.title}")
        print(f"Source    : {lead.source} | Location: {lead.location}")
        if lead.extracted_budget:
            print(f"Homeowner Budget: {lead.extracted_budget}")
        print(f"Link      : {lead.url}")
        
        if lead.is_valid_lead:
            print(f"Est. Quote: {lead.bid_price_range}")
            print(f"Drafted Bid Message:\n  \"{lead.generated_proposal}\"")
        else:
            print(f"Reason Skipped: {lead.rejection_reason}")

    # Export to JSON
    export_file = "latest_leads.json"
    with open(export_file, "w", encoding="utf-8") as f:
        json_data = [
            {
                "id": l.id,
                "title": l.title,
                "source": l.source,
                "location": l.location,
                "url": l.url,
                "is_valid": l.is_valid_lead,
                "quote_range": l.bid_price_range,
                "proposal": l.generated_proposal
            }
            for l in evaluated_leads
        ]
        json.dump(json_data, f, indent=2)

    print(f"\n[+] Saved {len(evaluated_leads)} processed leads to {export_file}")

def main():
    parser = argparse.ArgumentParser(description="Automated Residential Trade Job Scraper & Bid Bot")
    parser.add_argument("--trade", type=str, default=None, help="Trade (e.g. plumbing, electrical, painting, handyman)")
    parser.add_argument("--location", type=str, default=None, help="City / Region (e.g. Austin, Dallas, Chicago)")
    parser.add_argument("--source", type=str, choices=["craigslist", "portal", "all"], default="all")

    args = parser.parse_args()

    # Default Contractor Profile
    profile = ContractorProfile(
        trade=args.trade or "plumbing",
        company_name="Apex Home Solutions",
        contact_name="Mike Miller",
        phone="(555) 234-5678",
        email="mike@apexhome.com",
        hourly_rate=95.0,
        min_callout_fee=150.0,
        service_radius_miles=30,
        license_number="LIC-849204"
    )

    trade = args.trade or "plumbing"
    location = args.location or "Austin"

    run_pipeline(trade=trade, location=location, source=args.source, profile=profile)

if __name__ == "__main__":
    main()
