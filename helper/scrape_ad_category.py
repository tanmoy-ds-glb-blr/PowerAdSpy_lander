import tldextract
import time
import itertools

def get(url, driver):
    category_list = []
    try:
        domain = tldextract.extract(url)
#         print(domain)
        domain_short = domain.domain + "." + domain.suffix
#         print(domain_short)
    except Exception as e:
        print(e)
        return []

    sr_url = "https://sitereview.bluecoat.com/#/lookup-result/" + domain_short
    
    driver.get(sr_url)
    time.sleep(5)
    try:
        if driver.find_elements(by="xpath",
                                value = "//span[@class='ng-star-inserted']//div[@class='panel panel-default']//div[@class='panel-heading']"):
            elm = driver.find_element(by="xpath", 
                                value = "//span[@class='ng-star-inserted']//div[@class='panel panel-default']//div[@class='panel-heading']")
            if elm.text == "Current categorization:":
                categories = elm.find_elements(by='xpath', value = "./..//span[@class='clickable-category']")
                for i in categories:
                    category_list.append(i.text)
            else:
                return []
            
        return category_list
    except Exception as e:
        print(e)
        return []