from googleapiclient.discovery import build
from google.oauth2 import service_account
from bs4 import BeautifulSoup
import requests
import re
from urllib.parse import urlparse
from datetime import datetime
import pytz
import statistics
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from time import sleep

SERVICE_ACCOUNT_FILE = '//home//ec2-user//scraping_beauty//creds.json'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
print(datetime.now())
creds = None
creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)

# The ID and range of a sample spreadsheet.
SPREADSHEET_ID = '11BpReLHjk-2hq6QJm3FHOi6JGv9GETuvG9dfKo5fYiU'

service = build('sheets', 'v4', credentials=creds)

sheet = service.spreadsheets()

result = sheet.values().get(spreadsheetId=SPREADSHEET_ID,
							range=f'BASE ENV 2!C3:R').execute()
values = result.get('values', [])

request_body = {}

response = sheet.values().clear(
	spreadsheetId=SPREADSHEET_ID,
	range='REPORTE AJ!I3:U',
	body=request_body
).execute()


def get_page_source(url):
	webdriver_service = Service('//home//ec2-user//scraping_beauty//chromedriver')

	chrome_options = Options()
	chrome_options.add_argument("--headless")
	chrome_options.add_argument("--disable-gpu")
	chrome_options.add_argument("--window-size=1920,1080")
	chrome_options.add_argument("--no-sandbox")
	chrome_options.binary_location = '/bin/google-chrome'

	driver = webdriver.Chrome(service=webdriver_service, options=chrome_options)

	driver.get(url)
	page_source = driver.page_source

	driver.quit()
	return page_source
	

def scrape_product(url):
	response = requests.get(url)
	soup = BeautifulSoup(response.text, 'html.parser')

	selectors_and_functions = {
		'beauty.plus': ('.product-price__current-price', None),
		'dbs': ('.price', None),
		'blush': ('', lambda prices: prices[0].text + prices[1].text),
		'sokobox': ('.product__price--regular', None),
		'preunic': ('.original-price', None),
		'salcobrand': ('', lambda soup: soup.find('meta', itemprop="price")['content'] if soup.find('meta', itemprop="price") else soup.select_one('.normal-price').text),
		'beautycreation': ('.actual-price', None),
		'pinklady': ('.product-price-final', None),
		'paris': ('', lambda soup: next(
			(
				re.sub(r'[a-zA-Z\s,.$:]', '', re.search(r'\$\d+.\d+', tag.parent.text).group())
				for tag in soup.find_all(string=re.compile("price", re.IGNORECASE))
				if re.search(r'\$\d+.\d+', tag.parent.text)
			),
			None
		)),
		'falabella': (
		'.price', lambda price_tag: re.sub(r'[a-zA-Z\s,.$:]', '', re.search(r'\d+[,.]?\d*', price_tag.text).group())),
		'default': ('.price', None),
	}

	site_key = next((key for key in selectors_and_functions if key in url), 'default')
	selector, special_function = selectors_and_functions[site_key]
	print(special_function)
	try:
		if site_key == 'paris':  # Caso especial para 'paris'
			page_source = get_page_source(url)  # Reemplaza 'get_page_source' con tu función actual
			soup = BeautifulSoup(page_source, 'html.parser')

		if special_function:
			if selector:
				price_tag = soup.select_one(selector)
				price_text = special_function(price_tag)
				price_meta = soup.find('meta', itemprop="price")
				if price_meta:
					price = price_meta['content']
				else:
					price = soup.select_one('.normal-price').text
			else:
				price_text = special_function(soup)
		elif site_key == 'beauty.plus':
			price_text = soup.select_one(selector).string.strip() if selector else None
		else:
			price_text = soup.select_one(selector).text if selector else None

		if price_text:
			price = re.sub(r'[a-zA-Z\s,.$:]', '', price_text)
		else:
			price = 'Sin Stock'

	except AttributeError:
		price = 'Sin Stock'

	return price


for row in values:
	brand = row[1]
	competitors = 9
	all_competitors = 8
	date = datetime.now(pytz.timezone('Chile/Continental')).strftime("%d/%m/%Y")
	report = [[]]
	prices = [0, 0, 0, 0, 0, 0, 0, 0, 0]
	report[0].append(date)

	for i in range(0, competitors):
		product = row[0]
		url = row[i + 7].replace(' ', '')
		parsed_url = urlparse(url)

		domain_parts = parsed_url.netloc.split('.')

		if 'www' in domain_parts:
			domain_parts.remove('www')

		if len(domain_parts) > 2:
			# Hay un subdominio, obtener el dominio principal
			company = domain_parts[-2]
		elif len(domain_parts) == 2:
			# No hay subdominio
			company = domain_parts[0]
		else:
			continue

		price = scrape_product(url)

		if not price:
			price = 'Sin Stock'
		elif price != 'Sin Stock':
			price = int(price)

		if 'beautycreation' in url:
			price_b = row[6]
			price_b = re.sub(r'[a-zA-Z\s,.$:]', '', price_b)
			extraction_b = [[product, brand, date, price_b, url, 'beauty']]

			if row[7] == ' - ':
				prices[i - 1] = price_b

			sheet.values().append(spreadsheetId=SPREADSHEET_ID,
								  range='EXTRACC!A:F', valueInputOption='USER_ENTERED',
								  body={'values': extraction_b}).execute()
	
		extraction = [[product, brand, date, price, url, company]]
		prices[i] = price
		print(extraction)

		try:
			sheet.values().append(spreadsheetId=SPREADSHEET_ID,
								  range='EXTRACC!A:F', valueInputOption='USER_ENTERED',
								  body={'values': extraction}).execute()
		except:
			sleep(30)

	count_non_zero = sum(
		1 for x in prices if isinstance(x, (int, str)) and (isinstance(x, int) or x.isdigit()) and int(x) != 0)

	if count_non_zero > 1:
		numeric_data = [int(x) for x in prices if
						isinstance(x, (int, str)) and (isinstance(x, int) or x.isdigit()) and int(x) != 0]

	max_price = max(numeric_data)
	min_price = min(numeric_data)
	avg_price = statistics.mean(numeric_data)

	report[0].extend(prices)
	report[0].append(avg_price)
	report[0].append(max_price)
	report[0].append(min_price)

	print(report)

	report_result = sheet.values().get(spreadsheetId=SPREADSHEET_ID,
									   range='REPORTE AJ!I3:U').execute()
	report_values = report_result.get('values', [])

	sheet.values().append(spreadsheetId=SPREADSHEET_ID,
						  range=f'REPORTE AJ!I{3 + len(report_values)}:U{3 + len(report_values)}',
						  valueInputOption='USER_ENTERED',
						  body={'values': report}).execute()
