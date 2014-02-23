import urllib, urllib2, cookielib
import lxml.html as lh
import re
import zipfile
import logging
from datetime import date, timedelta
from StringIO import StringIO


USERNAME = 'username'
PASSWORD = 'password'

TARGET_URL = 'https://www.pge.com/myenergyweb/appmanager/pge/customer?_nfpb=true&_windowLabel=landingMyUsage_1&landingMyUsage_1_actionOverride=%2Fcom%2Fpge%2Fcsis%2Fmyenergy%2Fpageflows%2Fpromoplacement%2FgetEmTool&_pageLabel=Landing&usageOrWaysToSave=MyUsage'
PGE_LOGIN_URL = 'https://www.pge.com/eum/login'
PGE_DOWNLOAD_URL = 'https://pge.opower.com/ei/app/modules/customer/{}/energy/download?exportFormat=CSV_AMI&csvFrom={}&csvTo={}'


logging.basicConfig(format='%(asctime)s %(message)s', level=logging.INFO, datefmt='%H:%M:%S')

def main():
    today = date.today()
    last_week = today - timedelta(days=7)

    start_day = last_week.strftime("%m/%d/%Y")
    end_day = today.strftime("%m/%d/%Y")

    logging.info("Retrieving data from {} to {}".format(start_day, end_day))

    logging.debug("Setting up cookiejar and opener")
    cj = cookielib.CookieJar()
    opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))
    login_data = urllib.urlencode({'USER': USERNAME, 'PASSWORD': PASSWORD, 'TARGET': TARGET_URL})

    logging.info("Logging in...")
    content = opener.open(PGE_LOGIN_URL, login_data).read()
    logging.info("Logged in, redirecting...")

    doc = lh.fromstring(content)

    SAMLResponse = doc.forms[0].fields.get('SAMLResponse')
    if SAMLResponse is None:
        logging.error("Invalid credentials")
        return None
    RelayState = doc.forms[0].fields.get('RelayState')
    sso_login_url = doc.forms[0].get('action')
    login_data = urllib.urlencode({'SAMLResponse': SAMLResponse, 'RelayState': RelayState})

    logging.info("SSO Login...")
    sso_content = opener.open(sso_login_url, login_data).read()
    logging.info("SSO Logged in")

    doc = lh.fromstring(sso_content)
    opentoken = doc.forms[0].fields.get('opentoken')
    energy_url = doc.forms[0].get('action')

    logging.info("Going to Energy domain")
    content = opener.open(energy_url, urllib.urlencode({'opentoken': opentoken})).read()
    logging.info("Opened energy domain")
    match = re.search(r'/customer/(\d+)/bill_periods', content)

    if not match.groups():
        logging.error("Customer number was not found")
        return None
    else:
        customer_number = match.groups()[0]
        logging.debug("Customer number: %d", customer_number)

    request =  urllib2.Request(PGE_DOWNLOAD_URL.format(customer_number, start_day, end_day))
    logging.info("Downloading data...")
    response = opener.open(request)
    logging.info("Downloaded data")

    data = ""
    if "zip" in response.info().get('Content-disposition'):
        buf = StringIO(response.read())
        myzipfile = zipfile.ZipFile(buf)
        for name in myzipfile.namelist():
            logging.debug("Opening zip: {}".format(name))
            for line in myzipfile.open(name).readlines():
                if "usage" in line:
                  data += line
    else:
        logging.error("Something's changed!")

    return data


if __name__ == "__main__":
    data = main()
    if data is None:
        print "Request failed, check the logs"
    else:
        print "Usage Data"
        print "=========="
        print data
