import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.append('.')
import new_lander
import logging

logger = logging.getLogger("test_regression")

class DummyCounter:
    def labels(self, **kwargs):
        return self
    def inc(self):
        pass

class DummyMetric:
    def __init__(self):
        self.processed_configured_lander_url = DummyCounter()
        self.updated_configured_lander = DummyCounter()
        self.configured_lander_get = DummyCounter()

test_ads = [
    {
        "id": 167405,
        "ad_url": "",
        "destination_url": "https://www.adflex.co.uk/",
        "iso": ["IN"],
        "country": ["India"]
    },
    {
        "id": 43138,
        "ad_url": "",
        "destination_url": "https://www.selectumhotels.com/en?utm_source=facebook&utm_medium=cpc&utm_campaign=uk-genel",
        "iso": ["IN"],
        "country": ["India"]
    }
]

metric = DummyMetric()
for ad in test_ads:
    print(f"\n>>> Running regression test for Ad ID {ad['id']} ({ad['destination_url']})")
    success = new_lander.scraping(
        single_data=ad,
        metric=metric,
        lander_logger=logger,
        port="test",
        instance_no=f"reg_{ad['id']}",
        count=0,
        error_logger=logger
    )
    print(f">>> Result for Ad ID {ad['id']}: Success = {success}")
