import time
import requests
from requests.exceptions import RequestException, HTTPError

def format_price(price_in_millions):
    """
    Formats a price in millions into a more readable string with 'M' or 'B',
    and removes trailing .00 if zero.
    """
    if price_in_millions >= 1000:
        price_str = f"{price_in_millions / 1000:.3f}".rstrip('0').rstrip('.')
        return f"{price_str}B"
    else:
        price_str = f"{price_in_millions:.2f}".rstrip('0').rstrip('.')
        return f"{price_str}M"

def calculate_net_value(item_id, items_data, market_prices, memo):
    if item_id in memo:
        return memo[item_id]

    item = items_data.get(item_id)
    if not item:
        return market_prices.get(item_id, {}).get('lbin_price', 0), 0

    total_points = item.get('points', 0)
    total_cost_in_coins = 0

    prerequisites = item.get('prerequisites', [])
    for prereq in prerequisites:
        prereq_id = prereq['item_id']
        amount = prereq['amount']
        prereq_value = market_prices.get(prereq_id, {}).get('lbin_price', 0)
        total_cost_in_coins += prereq_value * amount

    memo[item_id] = (total_cost_in_coins, total_points)
    return total_cost_in_coins, total_points

def fetch_market_prices():
    market_prices = {}
    base_url = "https://sky.coflnet.com/api/auctions/tag"
    item_tags_to_fetch = {
        "BINGO_TALISMAN": "BINGO_TALISMAN",
        "BINGO_RING": "BINGO_RING",
        "BINGO_ARTIFACT": "BINGO_ARTIFACT",
        "BINGO_RELIC": "BINGO_RELIC",
        "BINGO_DISPLAY": "BINGO_DISPLAY",
        "COLLECTION_DISPLAY": "COLLECTION_DISPLAY",
        "BONZO_STATUE": "BONZO_STATUE",
        "BOOK_OF_STATS": "BOOK_OF_STATS",
        "SPRING_BOOTS": "SPRING_BOOTS",
        "GOLDEN_DANTE_STATUE": "GOLDEN_DANTE_STATUE",
        "DITTO_SKULL": "DITTO_SKULL",
        "DITTO_SKIN": "DITTO_SKIN",
        "BINGO_BLUE_DYE": "DYE_BINGO_BLUE",
    }

    print("Fetching lowest BIN prices from CoflNet API...")
    
    for item_id, item_tag in item_tags_to_fetch.items():
        market_prices[item_id] = {'lbin_price': 0, 'last_week_lbin': 0, 'last_week_avg': 0, 'last_month_lbin': 0, 'last_month_avg': 0}
        
        try:
            url = f"{base_url}/{item_tag}/active/bin"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            if data and isinstance(data, list) and 'startingBid' in data[0]:
                lowest_price = data[0]['startingBid']
                market_prices[item_id]['lbin_price'] = lowest_price / 1_000_000
                print(f"  - Found active BIN for {item_id} (tag: {item_tag}). Price: {format_price(market_prices[item_id]['lbin_price'])} coins")
            else:
                print(f"  - No active BIN auction found for {item_id}. Checking last week's sales...")
                sold_url_week = f"{base_url}/{item_tag}/sold"
                sold_response_week = requests.get(sold_url_week, timeout=5)
                sold_response_week.raise_for_status()
                sold_data_week = sold_response_week.json()
                
                if sold_data_week and isinstance(sold_data_week, list):
                    prices_week = [sale['highestBidAmount'] for sale in sold_data_week if sale.get('bin')]
                    if prices_week:
                        last_week_lbin = min(prices_week) / 1_000_000
                        last_week_avg = (sum(prices_week) / len(prices_week)) / 1_000_000
                        market_prices[item_id]['last_week_lbin'] = last_week_lbin
                        market_prices[item_id]['last_week_avg'] = last_week_avg
                        print(f"    - Found last week's sales. Lowest: {format_price(last_week_lbin)}, Average: {format_price(last_week_avg)}")
                    else:
                        print("    - Last week's sales not found. Checking last month's sales...")
                        sold_url_month = f"{base_url}/{item_tag}/sold?page=last&count=1000"
                        sold_response_month = requests.get(sold_url_month, timeout=5)
                        sold_response_month.raise_for_status()
                        sold_data_month = sold_response_month.json()
                        
                        if sold_data_month and isinstance(sold_data_month, list):
                            prices_month = [sale['highestBidAmount'] for sale in sold_data_month if sale.get('bin')]
                            if prices_month:
                                last_month_lbin = min(prices_month) / 1_000_000
                                last_month_avg = (sum(prices_month) / len(prices_month)) / 1_000_000
                                market_prices[item_id]['last_month_lbin'] = last_month_lbin
                                market_prices[item_id]['last_month_avg'] = last_month_avg
                                print(f"    - Found last month's sales. Lowest: {format_price(last_month_lbin)}, Average: {format_price(last_month_avg)}")
                            else:
                                print("    - No BIN sales found in the last month.")
                        else:
                            print("    - No sales data found for the last month.")
                else:
                    print("    - No sales data found for the last week.")
        except HTTPError as e:
            if e.response.status_code == 400:
                print(f"Error fetching data for {item_id} (tag: {item_tag}): {e.response.status_code} - Bad Request.")
            else:
                print(f"Error fetching data for {item_id}: {e}")
        except RequestException as e:
            print(f"Error fetching data for {item_id}: {e}")

    print("Market data fetched successfully.")
    return market_prices

def calculate_and_print_results(items_data, market_prices):
    memo = {}
    print("\n" + "="*50)
    print("Hypixel SkyBlock Bingo Item Value Calculator")
    print(f"Data last updated at: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}")
    print("="*50)
    for item_id, item_details in items_data.items():
        market_data = market_prices.get(item_id, {})
        market_price = market_data.get('lbin_price', 0)
        total_prereq_cost, total_points = calculate_net_value(item_id, items_data, market_prices, memo)
        direct_points = item_details.get('points', 0)
        net_profit = market_price - total_prereq_cost

        if direct_points > 0:
            if market_price > 0:
                coins_per_point = net_profit / direct_points
                if net_profit > 0:
                    print(f"Item: {item_id}")
                    print(f"  Market Price: {format_price(market_price)} coins")
                    print(f"  Cost of Prerequisites: {format_price(total_prereq_cost)} coins")
                    print(f"  Net Profit: {format_price(net_profit)} coins")
                    print(f"  Points Spent: {direct_points} points")
                    print(f"  Coins per point: {format_price(coins_per_point)}")
                else:
                    print(f"Item: {item_id} - Not Profitable (Net Profit: {format_price(net_profit)})")
            else:
                print(f"Item: {item_id} - No Active BIN Auctions Found.")
                if market_data.get('last_week_lbin', 0) > 0:
                    print(f"  Last week's lowest BIN was: {format_price(market_data['last_week_lbin'])} coins")
                    print(f"  Last week's average BIN price was: {format_price(market_data['last_week_avg'])} coins")
                elif market_data.get('last_month_lbin', 0) > 0:
                    print(f"  Last week's sales not found. Checking last month's sales...")
                    print(f"  Last month's lowest BIN was: {format_price(market_data['last_month_lbin'])} coins")
                    print(f"  Last month's average BIN price was: {format_price(market_data['last_month_avg'])} coins")
            print("-" * 50)

def main():
    items_data = {
        "BINGO_DISPLAY": {"points": 50, "prerequisites": []},
        "COLLECTION_DISPLAY": {"points": 30, "prerequisites": []},
        "BONZO_STATUE": {"points": 30, "prerequisites": []},
        "BOOK_OF_STATS": {"points": 5, "prerequisites": []},
        "SPRING_BOOTS": {"points": 150, "prerequisites": []},
        "GOLDEN_DANTE_STATUE": {"points": 100, "prerequisites": []},
        "DITTO_SKULL": {"points": 50, "prerequisites": []},
        "BINGO_TALISMAN": {"points": 100, "prerequisites": []},
        "BINGO_RING": {"points": 150, "prerequisites": [{"item_id": "BINGO_TALISMAN", "amount": 1}]},
        "BINGO_ARTIFACT": {"points": 150, "prerequisites": [{"item_id": "BINGO_RING", "amount": 1}]},
        "BINGO_RELIC": {"points": 200, "prerequisites": [{"item_id": "BINGO_ARTIFACT", "amount": 1}]},
        "BINGO_BLUE_DYE": {"points": 500, "prerequisites": []},
        "DITTO_SKIN": {"points": 100, "prerequisites": []}
    }

    last_updated_time = 0
    market_prices = {}
    
    while True:
        current_time = time.time()
        if current_time - last_updated_time > 60:
            new_prices = fetch_market_prices()
            if new_prices:
                market_prices = new_prices
                last_updated_time = current_time
            else:
                print("Failed to fetch new data. Using old data if available.")
        
        if market_prices:
            calculate_and_print_results(items_data, market_prices)
        else:
            print("No market data available. Please check the API and your internet connection.")
            
        print("\nWaiting 60 seconds before next check...")
        time.sleep(60)

if __name__ == "__main__":
    main()
