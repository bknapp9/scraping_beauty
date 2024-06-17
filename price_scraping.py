from googleapiclient.discovery import build
from google.oauth2 import service_account
from bs4 import BeautifulSoup
import requests
import re
from urllib.parse import urlparse
from datetime import datetime
import pytz
import statistics

SERVICE_ACCOUNT_FILE = 'creds.json'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

creds = None
creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)

# The ID and range of a sample spreadsheet.
SPREADSHEET_ID = '11BpReLHjk-2hq6QJm3FHOi6JGv9GETuvG9dfKo5fYiU'

service = build('sheets', 'v4', credentials=creds)

sheet = service.spreadsheets()

result = sheet.values().get(spreadsheetId=SPREADSHEET_ID,
							range=f'BASE URL!A2:H').execute()
values = result.get('values', [])

data = []


def scrape_product(url):
	response = requests.get(url)
	soup = BeautifulSoup(response.text, 'html.parser')
	if 'beauty' in url:
		try:
			price = soup.select_one('.product-price__current-price.product-price__current-price--highlight-sale').string.strip()

			price = re.sub(r'[a-zA-Z\s,.$:]', '', price)
		except:
			price = 'Sin Stock'

		product_info = soup.find('div', id='especificacionesContent').find('p')
		for strong_tag in product_info.find_all('strong'):
			if strong_tag.text.strip() == 'Marca:':
				brand = strong_tag.next_sibling.strip()
				break

		return price, brand
	elif 'dbs' in url:
		price = soup.select_one('.price').text

		price = re.sub(r'[a-zA-Z\s,.$:]', '', price)

		brand = soup.select_one('.product-brand').text.strip()

		return price, brand
	elif 'preunic' in url:
		try:
			price = soup.select_one('.original-price').text

			price = re.sub(r'[a-zA-Z\s,.$:]', '', price)
		except:
			price = 'Sin Stock'

		brand = soup.select_one('.product__brand').text.strip()

		return price, brand
	else:
		try:
			price_element = soup.find('span', class_='value')

			price = price_element.get('content')
			price = re.sub(r'[a-zA-Z\s,.$:]', '', price)
		except:
			price = 'Sin Stock'

		brand = soup.select_one('.product-brand').text.strip()

		return price, brand


for row in values:
	date = datetime.now(pytz.timezone('Chile/Continental')).strftime("%Y:%m:%d %H:%M:%S")
	report = [[]]
	prices = []
	report[0].append(row[0])
	report[0].append(date)

	for i in range(0, 4):
		product = row[i + i]
		url = row[i+i+1]
		parsed_url = urlparse(url)

		if 'www' in url:
			company = parsed_url.netloc.split('.')[1]
		else:
			company = parsed_url.netloc.split('.')[0]

		price, brand = scrape_product(url)

		if not price:
			price = 'Sin Stock'
		elif price != 'Sin Stock':
			price = int(price)

		extraction = [[product, brand, date, price, url, company]]
		prices.append(price)

		sheet.values().append(spreadsheetId=SPREADSHEET_ID,
							range='EXTRACC!A:F', valueInputOption='USER_ENTERED', body={'values':extraction}).execute()

	numeric_data = [x for x in prices if isinstance(x, (int, float))]
	max_price = max(numeric_data)
	min_price = min(numeric_data)
	avg_price = statistics.mean(numeric_data)

	report[0].extend(prices)
	report[0].append(avg_price)
	report[0].append(max_price)
	report[0].append(min_price)

	sheet.values().append(spreadsheetId=SPREADSHEET_ID,
						range='REPORTE!A:F', valueInputOption='USER_ENTERED', body={'values':report}).execute()

	# product = row[0]
	# beauty_url = row[1]
	# beauty_price, brand = scrape_product(beauty_url)
	#
	# compA_url = row[3]
	# compA_price, brand = scrape_product(compA_url)
	#
	# compB_url = row[5]
	# compB_price, brand = scrape_product(compB_url)
	#
	# compC_url = row[7]
	# compC_price, brand = scrape_product(compC_url)
	#
	# if compC_price == '' or compC_price == 'Sin Stock':
	# 	compC_price = 0
	# if compB_price == 'Sin Stock':
	# 	compB_price = 0
	# if compA_price == 'Sin Stock':
	# 	compA_price = 0
	# if beauty_price == 'Sin Stock':
	# 	beauty_price = 0
	# average_price = round((int(compA_price) + int(compB_price) + int(compC_price)) / 3)
	# max_price = max(int(beauty_price), int(compA_price), int(compB_price), int(compC_price))
	# min_price = min(int(beauty_price), int(compA_price), int(compB_price), int(compC_price))
	#
	# report = [[product, date, beauty_price, compA_price, compB_price, compC_price, average_price, max_price, min_price]]
	# sheet.values().append(spreadsheetId=SPREADSHEET_ID,
	# 					  range='REPORTE!A:F', valueInputOption='USER_ENTERED', body={'values': report}).execute()