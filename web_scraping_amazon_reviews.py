import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import re
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Set up the Selenium WebDriver with headless option
options = webdriver.ChromeOptions()
options.add_argument('--headless')  # Run browser in headless mode
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# Define the base URL for product search results
pages_to_scrape = 5  # Number of product pages to scrape

# Initialize a list to store the scraped data
all_reviews = []

# Function to extract ASIN from the product URL
def extract_asin(url):
    match = re.search(r"/(dp|gp/product)/([A-Z0-9]{10})", url)
    if match:
        return match.group(2)
    return None

# Function to scrape all reviews from the paginated review pages
def scrape_all_reviews(product_url):
    driver.get(product_url)
    time.sleep(3)  # Wait for the page to load

    # Click the "See more reviews" link if present
    see_more_reviews = driver.find_elements(By.XPATH, "//a[contains(text(), 'See more reviews')]")
    if see_more_reviews:
        see_more_reviews[0].click()
        time.sleep(3)  # Wait for the reviews page to load
        soup = BeautifulSoup(driver.page_source, 'html.parser')

    # Extract the ASIN (Product ID)
    asin = extract_asin(product_url)

    # Loop to handle pagination in reviews
    while True:
        try:
            # Find all product review sections on the current page
            reviews = soup.find_all('div', {'data-hook': 'review'})
        except Exception as e:
            print(f"Error initializing soup on new page for {product_url}: {e}")
            break  # Break the loop if soup fails to re-initialize

        print(f"scraping reviews...")
        # Scrape review data
        for idx, review in enumerate(reviews):
            review_text = review.find('span', {'data-hook': 'review-body'}).text.strip()  # Extract review text
            helpful_votes = review.find('span', {'data-hook': 'helpful-vote-statement'})  # Extract helpful votes
            review_date = review.find('span', {'data-hook': 'review-date'}).text.strip()  # Extract review date
            reviewer = review.find('span', {'class': 'a-profile-name'}).text.strip()  # Extract reviewer's name

            # Verified Purchase Flag (Check if 'Verified Purchase' exists in the review)
            verified_flag = bool(review.find('span', {'data-hook': 'avp-badge'}))  # Look for 'Verified Purchase' tag

            # Vine Voice Flag (Check if the review is marked as a Vine Voice review)
            vine_flag = 1 if review.find('span', {'data-hook': 'linkless-vine-review-badge'}) or review.find('span', string='Vine Customer Review of Free Product') else 0
            
            # Handle missing helpful votes
            helpful_votes = helpful_votes.text.strip() if helpful_votes else '0'

            # Extract rating stars
            rating_element = review.find('i', {'data-hook': 'review-star-rating'})
            if rating_element:
                rating_str = rating_element.text.strip()
                rating = float(re.search(r'(\d+\.\d+|\d+)', rating_str).group())
            else:
                rating = None  # Rating not found

            # Append to the list of all reviews
            all_reviews.append({
                'Product Identifier (ASIN)': asin,
                'Review Text': review_text,
                'Helpful Votes': helpful_votes,
                'Review Date': review_date,
                'Reviewer': reviewer,
                'Vine Voice Flag': vine_flag,
                'Verified Purchase Flag': verified_flag,
                'Rating': rating  # Extra flag for rating
            })

        # Check if there is a "Next" button on the review pages
        next_button = driver.find_elements(By.XPATH, "//li[@class='a-last']/a")
        if next_button and "disabled" not in next_button[0].get_attribute("class"):
            next_button[0].click()  # Click the "Next" button
            time.sleep(3)  # Wait for the next page to load
            soup = BeautifulSoup(driver.page_source, 'html.parser')  # Update the soup with the new page content
        else:
            print("No more review pages to scrape.")
            break  # Break the loop if there are no more review pages or the button is disabled


# Function to scrape the product URLs and filter by price
def scrape_product_urls(search_url):
    driver.get(search_url)
    time.sleep(3)  # Wait for the page to load
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    # Find product sections
    products = soup.find_all('div', {'data-component-type': 's-search-result'})

    product_urls = []
    for idx, product in enumerate(products):
        price_whole = product.find('span', {'class': 'a-price-whole'})
        price_fraction = product.find('span', {'class': 'a-price-fraction'})
        
        if price_whole and price_fraction:
            # Combine price whole and fraction
            price_str = price_whole.text.replace('.', '') + '.' + price_fraction.text.strip()
            # Clean the price string
            price_str_clean = re.sub(r'[^0-9.]', '', price_str)
            
            try:
                # Convert the cleaned price string to float
                price = float(price_str_clean)
                if 50 <= price <= 100:
                    # Get the product URL
                    link = product.find('a', {'class': 'a-link-normal s-no-outline'})
                    if link:
                        product_url = 'https://www.amazon.com' + link['href']
                        product_urls.append(product_url)
                        print(f"Product {idx + 1}: URL added for scraping")
                else:
                    print(f"Product {idx + 1}: Price found - ${price}")
                    print(f"Product {idx + 1}: Price out of range - ${price}")
            except ValueError:
                # If price cannot be converted, default to using the whole part
                price_fallback = int(re.sub(r'[^0-9]', '', price_whole.text.strip()))
                print(f"Product {idx + 1}: Price conversion failed, fallback price - ${price_fallback}")
                if 50 <= price_fallback <= 100:
                    link = product.find('a', {'class': 'a-link-normal s-no-outline'})
                    if link:
                        product_url = 'https://www.amazon.com' + link['href']
                        product_urls.append(product_url)
                        print(f"Product {idx + 1}: URL added using fallback price")
        else:
            print(f"Product {idx + 1}: No price found, skipping product.")

    return product_urls


# Define the base URL (common part) for all pages
base_url = 'https://www.amazon.com/s?k=cameras&i=electronics&rh=n%3A281052%2Cp_36%3A1253505011&dc&crid=AG4A0ZGEGT7G&qid=1727485610&rnid=386442011&sprefix=cameras%2Celectronics%2C84&ref=sr_pg_'

# Function to generate URLs for pages 1 to 5
def generate_urls(base_url, num_pages):
    urls = []
    for page in range(1, num_pages + 1):
        if page == 1:
            # For page 1, the URL does not include the &page parameter
            urls.append(f"{base_url}{page}")
        else:
            # For pages 2 and beyond, include the &page=<number> parameter
            urls.append(f"{base_url}{page}&page={page}")
    return urls

# Generate URLs for pages 1 to 5
page_urls = generate_urls(base_url, pages_to_scrape)

# Iterate through product pages and scrape product URLs
for page in page_urls:
    print(f"Scraping page {page}")
    search_url = page
    product_urls = scrape_product_urls(search_url)  
    print(f"Scraped {len(product_urls)} product URLs on page {page}")

    cnt = 0
    # Scrape reviews for each product
    for product_url in product_urls:
        print(f"Scraping reviews for product {cnt + 1}: {product_url}")
        cnt += 1
        scrape_all_reviews(product_url)

# Convert the scraped data into a DataFrame and save to an Excel file
df = pd.DataFrame(all_reviews)
df.to_excel('amazon_reviews_all_products.xlsx', index=False)  # Save as Excel file
print("Scraping complete. Data saved to amazon_reviews_all_products.xlsx")

# Close the WebDriver
driver.quit()
