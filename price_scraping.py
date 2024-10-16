from time import sleep
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
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options

SERVICE_ACCOUNT_FILE = 'creds.json'
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

RANGE_REPORT = 'I3:Y'
RANGE_EXTRACTION = 'A:F'

response = sheet.values().clear(
	spreadsheetId=SPREADSHEET_ID,
	range=f'REPORTE AJ!{RANGE_REPORT}',
	body=request_body
).execute()


def update_reporte_ac():
	reporte_ac = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range='REPORTE AJ!A3:U').execute()
	values_ac = reporte_ac.get('values', [])

	if not values_ac:
		print('No data found.')
		return

	sheet.values().append(
		spreadsheetId=SPREADSHEET_ID,
		range='REPORTE AC!A:Z',
		valueInputOption='USER_ENTERED',
		insertDataOption='INSERT_ROWS',
		body={'values': values_ac}
	).execute()


def get_page_source(url):
	webdriver_service = Service('geckodriver.exe')

	firefox_options = Options()
	if 'natura' not in url:
		firefox_options.add_argument("--headless")
	firefox_options.add_argument("--width=1920")
	firefox_options.add_argument("--height=1080")
	firefox_options.binary_location = r'C:\Program Files\Mozilla Firefox\firefox.exe'

	driver = webdriver.Firefox(service=webdriver_service, options=firefox_options)

	driver.get(url)
	sleep(4)
	page_source = driver.page_source
	driver.quit()

	return page_source


def scrape_product(url):
	response = requests.get(url)
	soup = BeautifulSoup(response.text, 'html.parser')

	selectors_and_functions = {
		'dbs': ('.price', None),
		'blush': ('', lambda prices: prices[0].text + prices[1].text),
		'sokobox': ('.product__price--regular', None),
		'preunic': ('', lambda soup: extract_preunic_price(soup)),
		'salcobrand': ('', lambda soup: soup.find('meta', itemprop="price")['content'] if soup.find('meta',
																									itemprop="price") else soup.select_one(
			'.normal-price').text),
		'beautycreation': ('.actual-price', None),
		'paris': ('', lambda soup: next(
			(
				re.sub(r'[a-zA-Z\s,.$:]', '', re.search(r'\$\d+.\d+', tag.parent.text).group())
				for tag in soup.find_all(string=re.compile("price", re.IGNORECASE))
				if re.search(r'\$\d+.\d+', tag.parent.text)
			),
			None
		)),
		'falabella': (
			'.price',
			lambda price_tag: re.sub(r'[a-zA-Z\s,.$:]', '', re.search(r'\d+[,.]?\d*', price_tag.text).group())),
		'simple.ripley': ('', lambda soup: extract_ripley_price(url)),
		'natura': ('', lambda soup: extract_natura_price(url)),
		'default': ('.price', None),
	}

	site_key = next((key for key in selectors_and_functions if key in url), 'default')
	selector, special_function = selectors_and_functions[site_key]
	try:
		if site_key == 'paris':  # Caso especial para 'paris'
			page_source = get_page_source(url)  # Reemplaza 'get_page_source' con tu función actual
			soup = BeautifulSoup(page_source, 'html.parser')

		if special_function:
			if selector:
				price_tag = soup.select_one(selector)
				if not price_tag:
					price_text = extract_falabella_price(url)
				else:
					price_text = special_function(price_tag)
					price_meta = soup.find('meta', itemprop="price")
					if price_meta:
						price = price_meta['content']
					elif not price_meta and site_key != 'falabella':
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

	except AttributeError as e:
		print(e)
		price = 'Sin Stock'

	return price


def extract_ripley_price(url):
	page_source = get_page_source(url)
	soup = BeautifulSoup(page_source, 'html.parser')

	internet_price_container = soup.find('div', class_='product-price-container product-internet-price')
	if internet_price_container:
		price = internet_price_container.select_one('.product-price').text
		return price
	else:
		normal_price_container = soup.find('div', class_='product-price-container product-normal-price')
		if normal_price_container:
			price = normal_price_container.select_one('.product-price').text
			return price
	return 'Sin Stock'


def extract_preunic_price(soup):
	price = soup.select_one('.offer-price')
	if price:
		return price.text
	price = soup.select_one('.discount-price-preunic')
	if price and 'Tarjeta' not in price.text:
		return price.text
	price = soup.select_one('.original-price')
	if price:
		return price.text
	return 'Sin Stock'


def extract_natura_price(url):
	page_source = get_page_source(url)
	soup = BeautifulSoup(page_source, 'html.parser')

	price_container = soup.find('div', class_=lambda x: x and 'Price-module__price--' in x)
	if price_container:
		price = price_container.select_one('.MuiTypography-root')

		return price.text
	else:
		return 'Sin Stock'


def extract_falabella_price(url):
	page_source = get_page_source(url)
	soup = BeautifulSoup(page_source, 'html.parser')

	discount_price = soup.find('li', {'data-internet-price': True})
	if discount_price:
		price = discount_price['data-internet-price']
		return price
	else:
		normal_price = soup.find('li', {'data-normal-price': True})
		if normal_price:
			price = normal_price['data-normal-price']
			return price
		else:
			return 'Sin Stock'
	return 'Sin Stock'
# if 'beauty.plus' in url:
# 	try:
# 		price = soup.select_one('.product-price__current-price').string.strip()
#
# 		price = re.sub(r'[a-zA-Z\s,.$:]', '', price)
# 	except:
# 		price = 'Sin Stock'
#
# 	return price
# elif 'dbs' in url:
# 	try:
# 		price = soup.select_one('.price').text
#
# 		price = re.sub(r'[a-zA-Z\s,.$:]', '', price)
# 	except:
# 		price = 'Sin Stock'
#
# 	return price
# elif 'blush' in url:
# 	try:
# 		prices = soup.find_all(class_='vtex-product-price-1-x-currencyInteger')
#
# 		price = prices[0].text + prices[1].text
#
# 		price = re.sub(r'[a-zA-Z\s,.$:]', '', price)
# 	except:
# 		price = 'Sin Stock'
#
# 	return price
# elif 'sokobox' in url:
# 	try:
# 		price = soup.select_one('.product__price--regular').text
#
# 		price = re.sub(r'[a-zA-Z\s,.$:]', '', price)
# 	except:
# 		price = 'Sin Stock'
#
# 	return price
# elif 'preunic' in url:
# 	try:
# 		price = soup.select_one('.offer-price')
#
# 		if price:
# 			price = re.sub(r'[a-zA-Z\s,.$:]', '', price.text)
# 		else:
# 			price = soup.select_one('.original-price').text
# 		return price
# 		price = soup.select_one('.original-price').text
#
# 		price = re.sub(r'[a-zA-Z\s,.$:]', '', price)
# 	except:
# 		price = 'Sin Stock'
#
# 	return price
# elif 'salcobrand' in url:
# 	try:
# 		price_meta = soup.find('meta', itemprop="price")
#
# 		if price_meta:
# 			price = price_meta['content']
# 			price = re.sub(r'[a-zA-Z\s,.$:]', '', price)
# 		else:
# 			price = soup.select_one('.normal-price').text
#
# 			price = re.sub(r'[a-zA-Z\s,.$:]', '', price)
# 	except:
# 		price = 'Sin Stock'
#
# 	return price
# elif 'beautycreation' in url:
# 	try:
# 		price = soup.select_one('.actual-price').text
#
# 		price = re.sub(r'[a-zA-Z\s,.$:]', '', price)
# 	except:
# 		price = 'Sin Stock'
#
# 	return price
# elif 'pinklady' in url:
# 	try:
# 		price = soup.select_one('.product-price-final').text
#
# 		price = re.sub(r'[a-zA-Z\s,.$:]', '', price)
# 	except:
# 		price = 'Sin Stock'
#
# 	return price
# else:
# 	if 'paris' in url:
# 		try:
# 			page_source = get_page_source(url)
# 			soup = BeautifulSoup(page_source, 'html.parser')
# 			price_tag = soup.find(string=re.compile("price", re.IGNORECASE))
# 			price_text = price_tag.parent.text  # Obtener el texto completo del elemento padre
# 			price_match = re.search(r'\$\d+.\d+', price_text)
# 			price = price_match.group()
# 			price = re.sub(r'[a-zA-Z\s,.$:]', '', price)
#
# 			if not price:
# 				price = 'Sin Stock'
# 		except:
# 			price = 'Sin Stock'
# 	else:
# 		try:
# 			price_tag = soup.find(class_='price')
# 			price_text = price_tag.text
# 			match = re.search(r'\d+[,.]?\d*', price_text)
# 			price = match.group()
# 			price = re.sub(r'[a-zA-Z\s,.$:]', '', price)
#
# 			if not price:
# 				price = 'Sin Stock'
# 		except:
# 			price = 'Sin Stock'
#
# 	return price


for row in values:
	product = row[0]
	brand = row[1]

	competitors = 8
	date = datetime.now(pytz.timezone('Chile/Continental')).strftime("%d/%m/%Y")
	report = [[]]
	prices = [0, 0, 0, 0, 0, 0, 0, 0, 0]
	report[0].append(date)

	price_b = row[6]
	price_b = re.sub(r'[a-zA-Z\s,.$:]', '', price_b)
	prices[-1] = price_b

	for i in range(1, competitors):
		url = row[i + 7].replace(' ', '')
		parsed_url = urlparse(url)
		if 'natura' in url:
			print('natura')
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

		if 'beauty.plus' not in url:
			price = scrape_product(url)

			if not price:
				price = 'Sin Stock'
			elif price != 'Sin Stock':
				price = int(price)

			extraction = [[product, brand, date, price, url, company]]
			prices[i-1] = price
			print(extraction)

		max_retries = 3
		for attempt in range(max_retries + 1):
			try:
				sheet.values().append(spreadsheetId=SPREADSHEET_ID,
									  range=f'EXTRACC!{RANGE_EXTRACTION}', valueInputOption='USER_ENTERED',
									  body={'values': extraction}).execute()
				break
			except Exception as e:
				print(f"Error durante la ejecución. Intento {attempt} de {max_retries}. Reintentando en 30 segundos...")
				sleep(30)

		if attempt == max_retries:
			raise e

	count_non_zero = sum(
		1 for x in prices if isinstance(x, (int, str)) and (isinstance(x, int) or x.isdigit()) and int(x) != 0)

	if count_non_zero > 1:
		numeric_data = [int(x) for i, x in enumerate(prices)
						if i != 8 and isinstance(x, (int, str)) and (isinstance(x, int) or x.isdigit()) and int(x) != 0]
		price_beauty = prices[-1]
	else:
		numeric_data = [0]
		price_beauty = 0

	max_price = max(numeric_data)
	min_price = min(numeric_data)
	avg_price = statistics.mean(numeric_data)

	dif_avg = int(price_beauty) - int(avg_price)
	dif_max = int(price_beauty) - int(max_price)
	dif_min = int(price_beauty) - int(min_price)

	report[0].extend(prices)
	report[0].append(avg_price)
	report[0].append(max_price)
	report[0].append(min_price)
	report[0].append(dif_avg)
	report[0].append(dif_max)
	report[0].append(dif_min)

	print(report)

	report_result = sheet.values().get(spreadsheetId=SPREADSHEET_ID,
									   range=f'REPORTE AJ!{RANGE_REPORT}').execute()
	report_values = report_result.get('values', [])

	for attempt in range(max_retries + 1):
		try:
			sheet.values().append(spreadsheetId=SPREADSHEET_ID,
								  range=f'REPORTE AJ!I{3 + len(report_values)}:Y{3 + len(report_values)}',
								  valueInputOption='USER_ENTERED',
								  body={'values': report}).execute()
			break
		except Exception as e:
			print(f"Error durante la ejecución. Intento {attempt} de {max_retries}. Reintentando en 30 segundos...")
			sleep(30)

	if attempt == max_retries:
		raise e

update_reporte_ac()
