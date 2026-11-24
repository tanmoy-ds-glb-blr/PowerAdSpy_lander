# DO:

# DONE:
# add 'https://www.' for urls without this
# add proxy to requests
# add all iso proxies to zip files
# Limit outgoing url to 3
# Check and store outgoing URL's domain in dict and remove repeated outgoing url
# Capture redirected URL history
# Test for different URL
# API for whois
# input iso code and set that country's proxy for driver
# stop selenium from auto downloading apk, pdf etc. (NEEDS TESTING...)
# Remove ip fetching website from loading after the code is stable
# Scrape pages with source inside iframe (Not done. Not required as very few pages have iframe as the webpage)
# Change multiprocessing algorithm
# reduce page load timeout (NEEDS TESTING)

# NOTE:
# status = 0 -> data center (domain>15 months) X REMOVED X
# status = 1 -> residential (domain<15 months)
# status = 2 -> data center (domain<15 months)
# status = 3 -> error fetching domain date
import multiprocessing
import time
import json
import logging
import requests
import tempfile
import os, shutil
import subprocess
from multiprocessing_logging import install_mp_handler
from PIL import Image  # Load Pillow first for Python 3.10 compatibility
from helper import init, domaindate, screenshot, outgoing_url, redirect, text, html, scrape_ad_category
from logging.handlers import RotatingFileHandler
from prometheus_client import start_http_server, multiprocess, REGISTRY, generate_latest, Counter
from config import Config
config = Config(network="instagram")

_tempdir = tempfile.mkdtemp()
os.environ['prometheus_multiproc_dir'] = _tempdir

error_count = 0
# global post_api_error 
# post_api_error=0

# metrics for prometheus
# change variable name according to platform
class Metrics(object):
    """
    Metrics class for graphana
    """

    def __init__(self, idx):
        self._tempdir = _tempdir
        self._registry = REGISTRY
        self._multiprocess_registry = multiprocess.MultiProcessCollector(self._registry, self._tempdir)
        self.processed_insta_lander_url = Counter('processed_insta_lander_url_count',
                                                  'Number of Instagram urls processed',
                                                  ['port', 'status', 'error'], registry=None)
        self.updated_insta_lander = Counter('updated_insta_lander_count',
                                            'Updated Instagram Landers based on API response',
                                            ['port', 'message'], registry=None)
        self.insta_lander_get = Counter('insta_lander_get_count', 'get api not giving data', ['data'], registry=None)


    def shutdown(self):
        # remove the temporary directory
        shutil.rmtree(self._tempdir)

    def collect(self):
        return generate_latest(self._registry).decode()


# create logger function
def setup_logger(name, filename):
    logger = logging.getLogger(name)
    handler = RotatingFileHandler(filename, encoding="utf-8", maxBytes=104960000, backupCount=50)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s | %(message)s", "%Y-%m-%d %H:%M:%S")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


# Sending Payload with post request to insert api
def send_payload(payload, lander_logger, port, metric):
    try:
        # print(payload)
        lander_logger.error(payload)
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        # https://gramapi.poweradspy.com/insert_html_lander  # main
        # https://instaapi.poweradspy.com/insert_html_lander # dev
        post_res = requests.request("POST", config.get_api("DEV_INSERT_API" if config.dev_mode else "MAIN_INSERT_API"),
                                    data=json.dumps(payload), headers=headers)
        print(post_res.text)
        if "401" in str(post_res.text):
            print(json.dumps(payload))

        # if "200" not in post_res.text:
        #     post_api_error+=1
        #     if post_api_error>5:
        #         print(f"Please Check post_api | Sleeping for 30 min | {post_res.text}")
        #         time.sleep(1800)

        lander_logger.error(post_res.text)

        ad_ids = ""
        for ids in payload:
            ad_ids = ad_ids + " " + str(ids['ad_id'])
            ip_req = len(ids['outgoing_url']) + len(ids['redirects']) + 2
            lander_logger.error("IP hit count : " + str('-:=' * ip_req))
        post_json = json.loads(post_res.text)
        message = post_json['message']
        metric.updated_insta_lander.labels(port=port, message=message).inc()
    except Exception as e:
        metric.updated_insta_lander.labels(port=port, message="insertion error").inc()
        print("Insertion Error : " + str(e))
        lander_logger.error("Insertion Error : " + str(e))


def make_payload(ad_id, iso, instance_no, ret_redirects, final_url, ret_screenshot, ret_text, ret_outgoing,
                 ret_domain_date, ret_domain_age, ret_status, ret_html, size_logger,category_list, lander_logger):
    payload = {
        "ad_id": ad_id,
        "redirects": ret_redirects,
        "outgoing_url": ret_outgoing,
        "destinations": final_url,
        "country_iso": iso,
        "html_path": "",
        "html_content": ret_text,
        "screen_shot": "",
        "status": ret_status,
        "domain_age": ret_domain_age,
        "domain_registered_date": ret_domain_date,
        "IsDataCenterProxy": 1,
        "crawled_by": "python",
        "ad_category":category_list
    }

    # Form-data payload to send through requests
    file = open(ret_html, "rb")
    img = open(ret_screenshot, 'rb')
    form_data_payload = {
        'zip': ('file.zip', file),
        'media': ('img.png', img),
        'ad_id': (None, ad_id),
        'status': (None, ret_status),
        'country': (None, iso),
    }
    size_logger.error("image folder size in bytes, " + str(os.path.getsize(ret_screenshot)))
    size_logger.error("zip folder size in bytes, " + str(os.path.getsize(ret_html)))


    # print(form_data_payload)
    # https://gramapi.poweradspy.com/upload_file_to-server  # main
    # https://instaapi.poweradspy.com/upload_file_to-server  # dev
    post_json = requests.request("POST", config.get_api("DEV_S3_API" if config.dev_mode else "MAIN_S3_API"),
                                 files=form_data_payload)
    lander_logger.error(post_json.text)
    x = json.loads(post_json.text)
    payload["screen_shot"] = x["image_path"]
    payload["html_path"] = x["html_path"]
    file.close()
    img.close()

    folder = './images/' + instance_no
    
    for filename in os.listdir(folder):
        file_path = os.path.join(folder, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as err:
            print('Failed to delete %s. Reason: %s' % (file_path, err))

    folder = './zip/' + instance_no
    for filename in os.listdir(folder):
        file_path = os.path.join(folder, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as err:
            print('Failed to delete %s. Reason: %s' % (file_path, err))
    return payload


# calling the functions from helper to get the required data
def controller(driver, destination_url, instance_no, r_session, f_url):
    try:
        driver.get(destination_url.strip())
        final_url = driver.current_url

        ret_redirects = redirect.get(destination_url, final_url, r_session, driver)
        ret_screenshot = screenshot.get(driver, "prelander", instance_no)
        ret_html = html.get(driver, r_session, final_url, instance_no)
        ret_text = text.get(driver)
        if not ret_text:
            ret_text=""
        ret_outgoing = outgoing_url.get(driver, final_url, r_session)
        # Ad_category added here:
        category_list = scrape_ad_category.get(f_url, driver)
        driver.close()
        driver.quit()

    except Exception as err:
        driver.close()
        driver.quit()
        raise Exception(err)

    return ret_redirects, final_url, ret_screenshot, ret_text, ret_outgoing, ret_html, category_list

def scraping(single_data, metric, lander_logger, size_logger, port, instance_no, count):
    iso_list = ['ae', 'at', 'au', 'be', 'br', 'ca', 'ch', 'cn',
                'de', 'dk', 'es', 'fi', 'fr', 'gb', 'hu', 'id',
                'ie', 'il', 'in', 'it', 'jp', 'kz', 'ma', 'mx',
                'my', 'nl', 'no', 'nz', 'ph', 'pl', 'pt', 'ru',
                'se', 'sg', 'th', 'tr', 'us', 'za', 'ae', 'au']

    global error_count

    try:
        countries = [x.lower() for x in single_data['iso'] if x.lower() in iso_list]
        ad_id = single_data['id']
        destination_url = single_data['destination_url'].replace("\\", "")

        if destination_url == "":
            return 1
        # ad_url = single_data['ad_url']

        # if ad_url == destination_url or destination_url is None:
        #     # print("Destination URL same as ad_url OR destination URL is None")
        #     continue  # Write a function to fetch destination_url from cta

        if countries == [] or countries is None:
            countries = ["us"]

        payload_list = []
        driver, r_session = init.init_dc(countries[0])
        driver.get(destination_url.strip())

        f_url = driver.current_url

        ret_domain_date, ret_domain_age = domaindate.get(f_url, network="instagram")

        if ret_domain_age is None:  # ERROR fetching domain date
            # SEND status as 3 to API.
            print("ret_domain_age None. Moving to next URL.")
            driver.quit()
            return 1

        if ret_domain_age == 1:  # Domain age greater than 15 months
            # print("Checking with DC proxies...")
            ret_status = 2
                        
            ret_redirects, final_url, ret_screenshot, ret_text, ret_outgoing, ret_html,category_list = controller(driver,
                                                                                                        destination_url,
                                                                                                        instance_no,
                                                                                                        r_session, f_url)
            pay = make_payload(ad_id, countries[0], instance_no, ret_redirects, final_url, ret_screenshot, ret_text,
                                    ret_outgoing, ret_domain_date, ret_domain_age, ret_status, ret_html,size_logger,category_list, lander_logger)
            payload_list.append(pay)

        if not payload_list:
            print("No payload built; skipping empty submission.")
            driver.quit()
            return 1

        send_payload(payload_list, lander_logger, port, metric)
        metric.processed_insta_lander_url.labels(port=port, status="pass", error="None").inc()
        error_count = 0
        try:
            driver.close()
            driver.quit()
        except:
            pass
        return None

    except Exception as error:
        if "invalid argument" in str(error):
            metric.processed_insta_lander_url.labels(port=port, status="fail", error="invalid argument").inc()
        elif "Timed out receiving" in str(error):
            metric.processed_insta_lander_url.labels(port=port, status="fail", error="Timed out receiving").inc()
        elif "'NoneType' object has no attribute 'replace'" in str(error):
            metric.processed_insta_lander_url.labels(port=port, status="fail", error="None Destination URL").inc()
        elif "net::ERR" in str(error):
            metric.processed_insta_lander_url.labels(port=port, status="fail", error="Connection Error").inc()
        elif "MaxRetryError" in str(error):
            metric.processed_insta_lander_url.labels(port=port, status="fail", error="MaxRetryError").inc()
        elif "cannot determine loading status" in str(error):
            count+=1
            if count<=2:
                scraping(single_data, metric, lander_logger, size_logger, port, instance_no, count)
            else:
                metric.processed_insta_lander_url.labels(port=port, status="fail", error="Loadind Status error").inc()

        elif "The system cannot find the file specified" in str(error):
            metric.processed_insta_lander_url.labels(port=port, status="fail", error="0 byte file").inc()
            zip_bat = "zip"+instance_no+".bat" #str(error).split("zip")[1][1]
            p = subprocess.Popen(zip_bat)
            time.sleep(2)
            p.kill()
            folder = './zip/' + instance_no
            for filename in os.listdir(folder):
                file_path = os.path.join(folder, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                    print('successfully deleted')
                except Exception as err:
                    print('Failed to delete %s. Reason: %s' % (file_path, err))
        elif "Expecting value:" in str(error):
            metric.processed_insta_lander_url.labels(port=port, status="fail", error="Blank Response make payload").inc()
        elif "No space left on device" in str(error):
            metric.processed_insta_lander_url.labels(port=port, status="fail", error="No space").inc()
        else:
            metric.processed_insta_lander_url.labels(port=port, status="fail", error="other error").inc()
        error_count += 1

        if error_count > 25:
            stop_bat = "stop_process.bat" #str(error).split("zip")[1][1]
            sub = subprocess.Popen(stop_bat)
            time.sleep(2)
            sub.kill()
        try:
            driver.quit()
        except:
            pass
        print("[Multiprocessing error] ", error)
        


# get requests to fetch the data from get api
def get_input():
    try:
        # https://gramapi.poweradspy.com/get-ads-for-blackhat  # main
        # https://instaapi.poweradspy.com/get-ads-for-blackhat  # dev
        inp = requests.get(config.get_api("DEV_GET_API" if config.dev_mode else "MAIN_GET_API"))
        data = json.loads(inp.text)
        li_of_data = data['data']
        return li_of_data
    except Exception as e:
        print("[GET INPUT ERROR]", e)


# main function to loop through the process along with proxies
def main(instances):
    instance_no = instances[0]
    port = instances[1]
    metric = Metrics(idx=instance_no)
    start_http_server(int(port))
    lander_logger = setup_logger(str(instance_no) + 'lander_logger',
                                 "logs/" + str(instance_no) + "_insta_lander_logger.log")
    size_logger = setup_logger(str(instance_no) + 'size_logger',
                                 "logs/size_logger.log")
    
    time.sleep(30 * (int(instance_no) - 1))
    while True:
        get_data = get_input()
        if get_data is None or get_data == []:
            print("No data to Process wait for 1 hour")
            metric.insta_lander_get.labels(data= 'empty').inc()
            time.sleep(3600)
            continue
        for single_data in get_data:
            count = 0
            check = scraping(single_data, metric, lander_logger, size_logger, port, instance_no, count)
            if check == 1:
                continue
            # print("\n", single_data)
            
# https://www.facebook.com/login/?

# multiprocessing to start pool (instances)
def multi_chrome():
    logging.Formatter.converter = time.gmtime
    install_mp_handler()
    ins_no = [("1", "8000"), ("2", "8001"), ("3", "8002"), ("4", "8003"), ("5", "8004"), ("6", "8005"), ("7", "8006"),
              ("8", "8007"), ("9", "8008")] #, ("10", "8009")]  # main
    # ins_no = [("7", "8006")]  # dev
    p = multiprocessing.Pool(config.instances)
    p.map(main, ins_no[:config.instances])
    p.terminate()


if __name__ == '__main__':
    multi_chrome()
    # main(("9","9000"))

# BLACKHAT ADS (NATIVE):
# "https://fludies-coaticted.com/11a6648e-6f2b-433c-b381-fbfd05cad76f?pi_containertype=web&pi_adid=559107&pi_clickid=66888c01bc5e46eb945b4bab2188d750&pi_creativeid=598096"
# "https://growthadvice.info/552cbd-hempmaxlab-cad/indsfsdfjpj32j4j4oi3j2io4ji32j4j2o3ij4oij23ij42o3ij4oi23jsdfsfex.html?sxid=1pvfg32y8it7&campid=130891&creaid=2362703&siteid=9154"
# "https://safagent.com/news/en/166/?teaser_id=4814406&campaign_id=976293&widget_id=57023593&category_id=149&geo=CA&click_price=0.21&click_id=ee745908f79e35dffeb2d04f31753cbd&ee745908f79e35dffeb2d04f31753cbd&utm_medium=cpc&utm_source=mgid.com&utm_campaign=Canada+-+12542+-+Desktop&utm_term=57023593&utm_content=4814406"
# below iframe link
# "http://tracking.newsmaxfeednetwork.com/pub2/click.json?sstmsg=5e3cef1ee4b0883c54217396&iteratorId=5e3d4419e4b02abaab1a76f0$null$171712$Z-1$N-1$R-1$A-1.00$S2$EXRtrue$V-1$FISSfIIPfESSfEIPt$JEXPLOITATION$Tfalse$QI20$QU15$EXT4$CSECP$CPEXP$IPINC$P2$_CEcp:16373*151938_0_4000.00_CEcp:16340*151805_1_4000.00_CEcp:15564*148880_2_2660.69_CEcp:16351*151834_3_3089.24&clientKey=y5BvYBQPsQj6pmoTWXKayV&link=https%3A%2F%2Ftheconservativenewssource.com%2Freverses-low-t-020720%2F&itemData=AgQAAAAYGDVlM2NlZjFlZTRiMDg4M2M1NDIxNzM5NggAAAFwH1IDTQQAAD%2FUBAAAD6AEAAAAAQQAAlD9AAAEAABx%2BwQAAAAGBjE1MTgwNQQAAAABAQAAAAQAAAAVFXRoZWFtZXJpY2FubWlycm9yLmNvbQQAAAAHB01JU1NJTkcEAAAABwdBTkRST0lEBAAAAAoKU01BUlRQSE9ORQAAAAAAAAAEAAAAFRVicjEjYnVSRTAjYWtPRkYyI2FnMCMBAAEABAAAAAQEbnVsbAAABAAAAAAABAAAAAABAAQAAABQAAAABAAAD6AEAAAAGBg1ZTNkNDQxOWU0YjAyYWJhYWIxYTc4NTM%3D&request_id=5e3d4419e4b02abaab1a76f0&gdpr=false&gdpr_consent="
# "https://teachstabilize.eu/mw/02/06/btc_cz_matka.php?oid=1095&clickid=b0bc794782e27aa7d80750979a1acde4&cp=0.18&campid=996845&creaid=&teaser=5053977&widget=5750296&geo=CZ&geor=Hlavni+mesto+Praha&utm_medium=cpc&utm_source=mgid.com&utm_campaign=BTC+CZ+desk&utm_term=5750296&utm_content=5053977&sxid=w9k07551b227"
# "https://dailyweb.live/landers/bitcoinen/index.html?uclick=xi8w9r"
# "http://www.bsqs.info/?rid=-7EBNQCgQAAHDQPAMABgEBEREKEQkKEQ1CEQ0SAAF_YWRjb21ibwEx&subacc2=adru_zhuromskiy&subacc3=0919&s_trk=CggX7F81lnYwdRDv1rjIDhiWkobuBQ**&subid2=U0NCLTEwNy1zc3AtZDk4NjRmNjctMWZhYS1iZjAwLWQ0YTMtMTU2Mzk4NTY1Ni1rMmx5ajA5by0zbjI6MDoxMDEzNjI6MDo1MA**&utm_content=teasers_adru_usa.adru_cbdvape_us_g.3&subacc4=101362&sxl=2&brl=2&utm_medium=17&utm_source=59849"
# "http://paid.outbrain.com/network/redir?p=A2Diyl6LfV_pBFREOtjhTF_nOdiIxVtsYbeHOHtfv717Rky1t-ZB4VUS9ohA5qFs_vZH-ABQdz2Gsk1Zvvg-b7hp9kxEcvINtKudr12eawV9tQrXqSMRyUlPenZ4NaJ1ET57GZ68peQvhQfy2XBW_todK8ssYuUDugHtCqk4Fm-X0B2KNnbpG1KWIt6F5DDgdyiBixamLnG7nS04C23RDwZ5D-CDzFrsq4u5rri74OCed3TCPvV78bnP92mcyGARqQK4jki094Ob-bPpWTmTjFp6AAtTAE8dX7cAT97q5qqFpKmcbCmr6dxQMZMYB0J-sAnY5EL1AN1LINAfF-9r0F6kt6LrWvsos4sIPtRG83qv-oO8NwwEk77SGK4Okmilh2YKPUaeDK3xOsNwfi6MizQN3kHxJQPc-wJEakmwnadOL-mdLrr7y46IxLXbmRpKy7fbGGdUrd4xWmU0Q72XAcfkFyoZ3uTvMuh0HCDj5nM_Pd36MpRGqB9OG1k0vCQB-hHwAv2qq_K9ONnRsPgzijmcqhy-tRb94StTzOjhFPyn77dSLFUGhuJGLZ_5U_jj6U686dLROzhR8Fe_PBcSOax-Y2TnsJIA_Dh5rHdfrhp65o4JJP6fgkY7iaAyYepMuNRksSeU7ns-Kgcu_10_oJJAILr0byZi2xX5pTpFVye28D1I2dD0v-1Tj9J67lFfDvFLeHb5yNCYLzS0ZQpubIye4OfI5HzjyTYY-TGedT_09Yx36TS0_Cotd1Xdnbqg9d8gIPLsdiRmc4m35e8v-BeVXAOy00ya_Fwu0aKyzzyuNYbyFhsbdmU1mLqS5gBPmpJdxHmkhRUigtaD1jBKgyvi4ppl-yrBwJR5dxMEz8yLgSEDMGqO3nI52a3gTESL-BT4-JO_BpaAgIUbZ-f_kn8t5M3-iLbaWRg7yalJ8gZo2qHHSkaLIl_YoiUp7wuVWff-_tFEmTizSCnVzk3wbWRtnZkesbyqA0eyKsNq_o2KT4MJJ3ClK3UymlrPwEL7VGyr14SMNZnh4evPo8YAhZcOfbA_N2WjIkGWsDTKeDm7Ytqr6GgEEYqBsfTd78I3a3RhYMOf8Lwz7LqPFL4mH1IgMdRGnMLkeltA_r8qENpuoaynBLv-_GnEnvY5dG-KV88SNFepW7NG4wYYdsMav7641j7SiMPghGZFU4d_pSLXyGRW-znmNipOFrUknQPFP0T00zzEbzd7AOB0UtqDDw&c=2b63124e&v=3"
# "https://news-speaker.com/transit/in/mz7-1-andr.html?cep=fxzRFfqCr7t9I2M6ulpc_6u-8AbMNiiB6WGSSuC6M5s46z9LOL7ITtEemCGRG44XCgw39HToR6HmB7c0uuyShw6pcFqGdfwvHnQJMpjOHwHUXKzRbq-3mgxigsq-Lhp_7O-LvRaGImyZnl6YWGQQH_OcIdqcTSzJichRM22kDRcLEBMITQTob9Q7TmPZ3BOux3PyyIy0F7-55W5yepZuYG20TbfdOknPtRc2ZR81GO3EyoKAXR3CzRb2JpQk3lrkL-2XyjDiD7yxH0xd4dZMnjmWGj12_PGVLvONBR9haN0oAzpQ0Deenm_0giww5eZMCO9zOio1hgup1N54s4SUv3pEkKr_c7iHlf5CqpQvZNhJ0hDe3cMMxFQXmlP2JuqAcStojlOtOYp8byBcuKPIIUkZ2_ejEqXw4P2ceFREICgScyAnq3Z-ChlMAoJ4o_JjuElzmCRdjte9-1SSOP5wxJUTG5Mk6YGurcPNhSIu4IItyvuSbZj1fCXLQFm9zNeb&lptoken=15ec80d1953b61803127&utm_content=4025321&utm_term=5635923&utm_source=mgid&utm_campaign=572318&utm_medium=tr&category_id=149&geo=IN&ref=tr_mgid_vm_IN-572318&click_price=0.102&click_id=c211809524143f3bc361042eb157e9ef"
# "https://dailynews-finance.com/za/bitcoin/dad/8421-dnf/?device=desktop&brand=&model=&browser=Chrome&os=Mac&country=South%20Africa&isp=Permtelecom%20Ltd&carrier=Cable/DSL/WiFi&sourcename=12122&cid=2xk8hwjqs3u7&c1=&c2=South%20Africa"

# NORMAL ADS (NATIVE):
# "https://www.plus500.co.uk/Trading/CryptoCurrencies?id=102068&tags=g_sr+94682817_cpi+UKKWContent_cp+7650700857_agi+Bitcoins_agn+www.news.com.au_pl+c_de+2826_loc+UURL&gclid=EAIaIQobChMIqozdzZG05wIVBLVRCh3Obg81EAEYASAAEgK9fPD_BwE"
# "https://www.regalassets.com/?gclid=EAIaIQobChMI0OOhptPY5gIVogV9Ch3m8QL9EAEYASAAEgJCa_D_BwE"
# "https://www.findkarma.com/feals-best-cbd-2641466368.html?&utm_content=5dbc5929b40cb77ec58226ee_5db20964b4d41c1ec6508561&bcid=5db20964b4d41c1ec6508561&bhid=5dbc5929b40cb77ec58226ee&utm_campaign=OB_M_SkepticsCBD_FindKarma_PS_RON&utm_source=GeistM&utm_medium=Outbrain&campaignid=5e22390d4d8f90523c564c8d&BT=DB&dicbo=v1-7963128cc158f463e182037de52e43ef-007adfa2fbb3f30152735e113804126bef-mnrdsmrymy2daljvgrsdeljumq3dkljygezdcllche4dgyzsmzrwknzsgm"
# "https://fuerihn.com/warum-greifen-immer-mehr-maenner-zu-viagra/?utm_source=Outbrain&utm_medium=Discovery&utm_campaign=Viagra_Mobile_Traffic&utm_content=Viagra+online+bestellen+ohne+Arztbesuch%3F&utm_term=AT_Oe24.at+%28oe24+GmbH%29_Auto+-+oe24.at&dicbo=v1-be5b20212123d402d611d5e71e63b958-0051764e21d397d7d7014dbd5e47067252-ga3dkytgha2dmllegmztsljumi4tallcgazdmllegaywmobxgq2dsm3gmm"
