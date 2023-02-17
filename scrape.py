import lucs_tools
import pandas as pd
import argparse
import numpy as np
import tqdm
import os
import time
import urllib3
import yaml 
from selenium.webdriver.chrome.options import Options

# email stuff
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib, ssl, email
import pathlib
import datetime
import warnings
from selenium.common.exceptions import NoSuchElementException

DEFAULT_YAML_ARGS = {
    'target': "luclepot@berkeley.edu",
    'port': 465,
    'refresh_sigma': 3,
    'uname': 'bobisloaded',
    'password_file': 'drivers/app.pass',
    'headless': True,
    'locale': 'sfbay',
    'category': 'cta',
    'sublocale': None,
    'direct_link': None,
    'search_filters': {}
}
REQUIRED_YAML_ARGS = {
    'refresh_rate', 'name', 'search_filters',
    'target', 'port', 'refresh_sigma', 'uname',
    'password_file', 'headless', 'locale', 'category',
    'sublocale', 'direct_link'
}

def insert_tag(link, tag, value):
    l,r = link.split('#search')
    if not isinstance(value, list):
        value = (value,)
    
    tags = '&'.join(['{}={}'.format(tag, v) for v in value])

    if '?' not in l:
        l += '?' + tags
    else:
        l += '&' + tags

    return '#search'.join([l,r])

# def deconstruct_craigslist_link(link):
    

def construct_craigslist_link(
    locale,
    category,
    sublocale,
    link,
    **kwargs
):
    if link is not None:
        l, suffix = link.split('#search=1')
        if not suffix.startswith('~list'):
            suffix = '~list~0~0'
        link = l + '#search=1' + suffix
        return link
    
    if sublocale is not None:
        sublocale += '/'
    else:
        sublocale = ''
    link = "https://{}.craigslist.org/search/{}{}#search=1~list~0~0".format(locale, sublocale, category)
    for k,v in kwargs.items():
        link = insert_tag(link, k, v)
    return link

def parse_narrow_element(elt, sep=None):
    title = elt.find_element('class name', 'title-blob').find_element('class name', 'titlestring')
    meta = elt.find_element('class name', 'meta')
    
    try:
        loc = elt.find_element('class name', 'supertitle').text
    except NoSuchElementException:
        loc = ""
        
    date = meta.get_attribute('innerHTML').split('title="')[1].split('">')[0].split(' GMT')[0]
    price = int(meta.find_element('class name', 'priceinfo').text.strip('$').replace(',', ''))
    
    name = title.text

    
    link = title.get_attribute('href')
    code = int(link.split('/')[-1].replace('.html', ''))

    return name, link, loc, price, date, code

def parse_wide_element(elt, sep):
    meta = elt.find_element('class name', 'meta')
    title = elt.find_element('class name', 'titlestring')

    loc = meta.text.split(sep)[1].strip('+').strip()
    date = meta.get_attribute('innerHTML').split('title="')[1].split('">')[0].split(' GMT')[0]
    price = int(meta.find_element('class name', 'priceinfo').text.strip('$').replace(',', ''))
    
    name = title.text
    link = title.get_attribute('href')
    code = int(link.split('/')[-1].replace('.html', ''))

    return name, link, loc, price, date, code

SEARCH_PREFIX = "SEARCH {} :: "

def search_header(i, st):
    return (SEARCH_PREFIX + '{}').format(i, datetime.datetime.fromtimestamp(st).strftime('%m/%d/%Y, %H:%M:%S EST :'))

def result_header(i, s):
    return ' '*(len(SEARCH_PREFIX.format(i)) - 3) + ':: ' + str(s)

def scrape_list(driver, header=None):
    wide = True
    
    elements = driver.get_elements_with_param_matching_spec('class name', 'result-node-wide')

    if len(elements) == 0:
        wide = False
        elements = driver.get_elements_with_param_matching_spec('class name', 'result-node-narrow')

    columns=['name', 'link', 'location', 'price', 'date', 'code']

    if len(elements) == 0:
        for elt in tqdm.tqdm([None,], desc=header):
            pass
        return pd.DataFrame([], columns=columns)

    sep = None    
    parse_func = None
    if wide:
        sep = elements[0].find_element('class name', 'meta').text[0]
        parse_func = parse_wide_element
    else:
        parse_func = parse_narrow_element
        
    data = []
    for elt in tqdm.tqdm(elements, desc=header):        
        data.append(parse_func(elt, sep))


    return pd.DataFrame(data, columns=columns)
    
def send_email(df, server, target, sender, name='items'):

    msg = MIMEMultipart('alternative')
    msg['Subject'] = "{} NEW {} FOUND".format(len(df), name.upper())
    msg['From'] = sender
    msg['To'] = target 

    # Create the body of the message (a plain-text and an HTML version).
    html = MIMEText(df.to_html(), 'html')

    # Attach parts into message container.
    # According to RFC 2046, the last part of a multipart message, in this case
    # the HTML message, is best and preferred.
    msg.attach(html)

    # sendmail function takes 3 arguments: sender's address, recipient's address
    # and message to send - here it is sent as one string.
    server.sendmail(sender, target, msg.as_string())

    return 0

def setup_email_server(port, gmail_uname, password_file):
    if len(password_file) == 0:
        password = input('password please: ')
    else:
        with open(password_file, 'r') as f:
            password = f.read().strip().strip('\n').strip()
    return port, "{}@gmail.com".format(gmail_uname), password, ssl.create_default_context()

def update_local_index(search, path):
    old = load_saved_index(path + '.npy' if not path.endswith('.npy') else path)

    idx = ~search.code.isin(old)
    new = (search.code[idx]).values.astype(np.int64)
    new_search = search[idx]

    combined = np.concatenate([old, new])

    update_saved_index(combined, path)

    return new, new_search

def update_saved_index(d, path):
    np.save(path, d)
    return 0

def load_saved_index(path):
    try:
        return np.load(path).astype(np.int64)
    except:
        return np.array([]).astype(np.int64)

def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('parameter_file', help='YAML file specifying search critera for craigslist search')
    parser.add_argument('-m', '--mode', default=None, type=str, help='name of mode in yaml file, optional')

    args = parser.parse_args()
    return args.parameter_file, args.mode

def check_default_args(params, fname, mode):
    for arg in DEFAULT_YAML_ARGS:
        if arg not in params:
            params[arg] = DEFAULT_YAML_ARGS[arg]

    for arg in REQUIRED_YAML_ARGS:
        assert arg in params, 'yaml_file "{}" with mode "{}" missing required argument "{}"'.format(fname, mode, arg)

    for arg in params:
        assert arg in REQUIRED_YAML_ARGS, 'yaml_file "{}" with mode "{}" contains non-existing argument "{}". See all arguments:\n{}'.format(fname, mode, arg, str(REQUIRED_YAML_ARGS))
        
    if params['direct_link'] is None:
        if len(params['search_filters']) == 0:
            raise ValueError('Must specify either a search link or search filters!!')

    return params

def get_params(card, mode):
    # load parameters
    with open(card, 'r') as f:
        params = yaml.safe_load(f)

    if mode is None:
        if len(params.keys()) != 1:
            raise ValueError('Non-singular default mode in selected yaml file {}'.format(card))
        mode = list(params.keys())[0]
    
    params = check_default_args(params[mode], card, mode)
    return params, mode

def main_loop():
    # port=465, uname='bobisloaded', wait_time=3600):

    card, mode = get_args()
    params, mode = get_params(card, mode)
        
    # setup timing information
    sleep_time = -1
    i = 1

    # fire up chrome
    data_path = "data/{}_{}".format(os.path.basename(card).lower().replace('.yaml', ''), mode)
    options = Options()
    if params['headless']:
        options.add_argument('--headless')
    driver = lucs_tools.internet.internet_base_util(
        driver_path="drivers/chromedriver.exe",
        data_path=data_path,
        options=options,
    )

    link = construct_craigslist_link(params['locale'], params['category'], params['sublocale'], params['direct_link'], **params['search_filters'])
    print(' RUNNING FOR LINK "{}"'.format(link))
    print()
    if params['direct_link'] is not None:
        print(' Using direct link, parameters ignored')
    else:
        print(' SEARCH PARAMETERS:')
        

        fmt = '    {:>25} = {:<}'
        for k in ['locale', 'category']:
            print(fmt.format(k, params[k]))
        for k, v in params['search_filters'].items():
            print(fmt.format(k, str(v)))
    print()
    
    driver.open_link(link)
    
    run_loop = True
    port, myemail, password, context = setup_email_server(params['port'], params['uname'], params['password_file'])
    

    while run_loop:
        try:
            if sleep_time > 0:
                time.sleep(sleep_time)
            start_time = time.time()
            driver.driver.refresh()
            data = scrape_list(driver, header=search_header(i, start_time))
            new_idx, new_search = update_local_index(data, data_path)

            if len(new_idx) > 0:
                # setup email stuff
                with smtplib.SMTP_SSL("smtp.gmail.com", port, context=context) as server:
                    server.login(myemail, password)
                    send_email(new_search, server, params['target'], myemail, params['name'])

            end_time = time.time()
            sleep_time = (
                params['refresh_rate'] + \
                np.random.normal(loc=0, scale=params['refresh_sigma']) - \
                (end_time - start_time)
            )
            print(result_header(i, ' of type {} | {} new | {} old | took {:.1f} s | sleeping for {:.1f} s'.format(mode, len(new_idx), len(data) - len(new_idx), end_time - start_time, max([sleep_time, 0]))))
            del data
            del new_search
            del new_idx
            
            i += 1
        except urllib3.exceptions.ProtocolError:
            print('FAILED, retrying')
        except KeyboardInterrupt:
            ex = input('\rType "exit" to close program: ')
            if ex.lower() == "exit":
                run_loop = False
        except smtplib.SMTPResponseException:
            print('Disconnected from Email server, trying to re-login')
            port, myemail, password, context = setup_email_server(params['port'], params['uname'], params['password_file'])

    del driver    
    return 0

if __name__ == "__main__":
    main_loop()
# util = lucs_tools.internet.internet_base_util(
#     driver_path="drivers/chromedriver.exe",
#     data_path="data/",

# )
