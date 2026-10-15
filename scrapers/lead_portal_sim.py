from typing import List
from datetime import datetime
from models import JobLead
from scrapers.base import BaseScraper

class PortalSimulatorScraper(BaseScraper):
    """
    Simulates leads from platforms like Bark, Thumbtack, or Nextdoor.
    Useful for local offline testing and as an adapter interface for structured webhook feeds.
    """
    def __init__(self):
        super().__init__(name="Homeowner Marketplace (Bark/Thumbtack Format)")

    def search_jobs(self, trade: str, location: str, limit: int = 15) -> List[JobLead]:
        trade_lower = trade.lower()
        samples = {
            "plumbing": [
                {
                    "title": "Kitchen sink pipe leaking and garbage disposal jammed",
                    "description": "Noticed water pooling under the kitchen sink. The P-trap seems loose and garbage disposal makes a humming noise. Single-family home, looking for a repair ASAP.",
                    "budget": "$150 - $300",
                    "area": "Downtown / Suburb"
                },
                {
                    "title": "Replace 2 bathroom faucets & install shutoff valves",
                    "description": "I have purchased two new Moen faucets. Need an experienced plumber to remove the old ones, install the new ones, and replace the shutoff valves under both vanities.",
                    "budget": "$250 - $400",
                    "area": "North Hills"
                },
                {
                    "title": "Water heater pilot light won't stay lit",
                    "description": "50-gallon Rheem gas water heater. Pilot goes out every few hours. Looking for diagnosis and thermocouple replacement or repair.",
                    "budget": "$200 - $350",
                    "area": "Westside"
                }
            ],
            "painting": [
                {
                    "title": "Interior painting: Living room and hallway (approx. 450 sq ft)",
                    "description": "Walls need 2 coats of Sherwin Williams eggshell paint. Standard 9-foot ceilings. Trim and baseboards to be touched up in semi-gloss white. Paint already purchased.",
                    "budget": "$800 - $1,200",
                    "area": "Oakridge"
                },
                {
                    "title": "Exterior front porch and front door repaint",
                    "description": "Wood railing and front steps need light sanding, priming, and 2 coats of exterior deck paint. Front door to be painted navy blue.",
                    "budget": "$400 - $600",
                    "area": "Maple Heights"
                }
            ],
            "electrical": [
                {
                    "title": "Install Level 2 EV Charger in 2-car garage",
                    "description": "Main breaker panel is on the exterior wall about 15 feet from the garage mounting location. Need 50A breaker, conduit run, and NEMA 14-50 outlet installed.",
                    "budget": "$650 - $1,100",
                    "area": "Eastview"
                },
                {
                    "title": "Install 3 ceiling fans with light kits",
                    "description": "Replacing existing light fixtures in 3 bedrooms with ceiling fans. Existing ceiling boxes are fan-rated. Need someone with proper ladder.",
                    "budget": "$300 - $500",
                    "area": "South Green"
                }
            ],
            "handyman": [
                {
                    "title": "Drywall patch (door knob hole) & mount 65-inch TV",
                    "description": "Small 4-inch hole in drywall behind bedroom door needs patching and texture match. Also need to mount a 65\" Samsung TV into studs over living room fireplace.",
                    "budget": "$200 - $350",
                    "area": "Pinecrest"
                },
                {
                    "title": "Assemble IKEA Pax wardrobe system (3 units)",
                    "description": "Need an experienced handyman to assemble 3 IKEA Pax wardrobes and anchor them securely to the bedroom wall. All boxes are inside the room.",
                    "budget": "$250 - $450",
                    "area": "Midtown"
                }
            ]
        }

        # Match closest trade or use generic
        selected_trade_items = samples.get(trade_lower)
        if not selected_trade_items:
            # Fallback to general handyman
            selected_trade_items = samples.get("handyman", [])

        leads = []
        for i, item in enumerate(selected_trade_items[:limit]):
            leads.append(JobLead(
                id=f"sim-{trade_lower}-{i+1}",
                title=item["title"],
                source="Residential Lead Feed",
                url=f"https://leads.example.com/jobs/{trade_lower}-{i+1}",
                location=f"{location} ({item['area']})",
                description=item["description"],
                detected_trade=trade_lower,
                extracted_budget=item["budget"]
            ))

        return leads
