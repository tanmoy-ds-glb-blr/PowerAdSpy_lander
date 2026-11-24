import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.append('.')
import time
import os
from PIL import Image
from helper import init

# Temporary copy of screenshot logic with the proposed fixes to validate
from helper import screenshot

def test_sparklingice():
    print("\n================ TESTING SPARKLING ICE (281900) ================")
    page, _ = init.init_dc('in')
    try:
        url = "https://www.sparklingice.com/?utm_source=DV360&utm_medium=programmatic&utm_campaign=SparklingIce_COREQ126_YT&utm_content=TKR_26_US_SICOREYT_AW_PP_PA_SELI_POSS_YOU_APL_NA_SIX_STD_15_CORE_CD_MRM&gad_source=2&gad_campaignid=23590031968&gclid=EAIaIQobChMIy5qKn67XlAMVJlRvBB1H2zGfEAEYAyAAEgIdqfD_BwE"
        page.goto(url, timeout=90000, wait_until='domcontentloaded')
        
        # Test current get()
        path = screenshot.get(page, "sparkling_current", "test_sparkling")
        img = Image.open(path)
        print(f"Sparkling Ice shot: {path} | Size: {os.path.getsize(path):,} bytes | Dim: {img.size}")
    finally:
        init.close_browser(page)

def test_mybobs():
    print("\n================ TESTING MYBOBS (281891) ================")
    page, _ = init.init_dc('in')
    try:
        url = "https://www.mybobs.com/?utm_source=hxdv360-8924156&utm_medium=progolv&utm_campaign=ps-yt-sales-34684313&utm_content=253527062&dclid=CNKevdTQk5QDFXmvpgQdSlUmYQ&gad_source=7&gad_campaignid=23749426755&gad_source=2&gad_campaignid=23804444849&gbraid=0AAAAACf1fe_lL7w5O1NjW4wZ4TyLnC0gs&gbraid=0AAAAACf1fe_lL7w5O1NjW4wZ4TyLnC0gs&gclid=EAIaIQobChMIz5vNkK7XlAMVYCCKAx3Q3AfbEAEYAiAAEgIxtfD_BwE"
        page.goto(url, timeout=90000, wait_until='domcontentloaded')
        
        path = screenshot.get(page, "mybobs_current", "test_bobs")
        img = Image.open(path)
        print(f"MyBobs shot: {path} | Size: {os.path.getsize(path):,} bytes | Dim: {img.size}")
    finally:
        init.close_browser(page)

if __name__ == '__main__':
    test_sparklingice()
    test_mybobs()
