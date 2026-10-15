from abc import ABC, abstractmethod
from typing import List
from models import JobLead

class BaseScraper(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def search_jobs(self, trade: str, location: str, limit: int = 15) -> List[JobLead]:
        """
        Scrape open residential jobs for a given trade and location.
        """
        pass
