from tqdm import tqdm
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from pandas.tseries.offsets import BDay

# Define the tickers and the date range
tickers = ['UPRO', 'SSO', 'VOO', 'GOLD', 'UBT', 'IOO']
start_date = '2015-05-01'
end_date = '2024-10-09'

# Load the historical price data
data = yf.download(tickers, start=start_date, end=end_date)['Adj Close']

# Ensure data index is timezone-naive
data.index = data.index.tz_localize(None)

# Define the investment parameters
investment_periods = [5]  # in years
weekly_investment = 500  # Weekly DCA
num_weeks_per_year = 52
initial_investment = 5000

# Prepare the results list to store the data
results = []



# Iterate over each period (e.g., 1 year, 3 years, etc.)
for period in tqdm(investment_periods, desc="Investment Periods"):
    
    # Iterate over each start date within the available data range, excluding weekends
    for start_date in tqdm(pd.date_range(start=data.index[0], end=data.index[-1], freq='B'), desc=f"Period {period} years", leave=False):
        # Define the rolling end date for the period
        end_date = start_date + pd.DateOffset(years=period)

        # Ensure that the end_date doesn't exceed the available data
        if end_date > data.index[-1]:
            continue

        # Ensure the end_date is a business day
        if end_date.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
            end_date = end_date + BDay(1)

        # Adjust the end_date to the previous business day if it is not in the data index
        while end_date not in data.index:
            end_date = end_date - BDay(1)

        # Initialize total units and total investment
        total_units = {
            'UPRO': 0, 
            'GOLD': 0, 
            'SSO': 0, 
            'UBT': 0,
            'VOO': 0,
            'IOO': 0
        }
        portfolio_units = {
            '60% UPRO, 40% GOLD': {'UPRO': 0, 'GOLD': 0},
            '50% SSO, 50% UBT': {'SSO': 0, 'UBT': 0}
        }
        total_investment = initial_investment

        # Calculate the number of units purchased with the initial investment
        if start_date in data.index:
            total_units['UPRO'] += initial_investment / data['UPRO'].loc[start_date]
            total_units['GOLD'] += initial_investment / data['GOLD'].loc[start_date]
            total_units['SSO'] += initial_investment / data['SSO'].loc[start_date]
            total_units['UBT'] += initial_investment / data['UBT'].loc[start_date]
            total_units['VOO'] += initial_investment / data['VOO'].loc[start_date]
            total_units['IOO'] += initial_investment / data['IOO'].loc[start_date]


            portfolio_units['60% UPRO, 40% GOLD']['UPRO'] += (initial_investment * 0.6) / data['UPRO'].loc[start_date]
            portfolio_units['60% UPRO, 40% GOLD']['GOLD'] += (initial_investment * 0.4 ) / data['GOLD'].loc[start_date]
            portfolio_units['50% SSO, 50% UBT']['SSO'] += (initial_investment / 2) / data['SSO'].loc[start_date]
            portfolio_units['50% SSO, 50% UBT']['UBT'] += (initial_investment / 2) / data['UBT'].loc[start_date]

        # Iterate over each week and make contributions, excluding weekends
        for week in range(num_weeks_per_year * period):
            contribution_date = start_date + pd.DateOffset(weeks=week)
            
            # Ensure the contribution_date is a business day
            if contribution_date.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
                continue
            
            # Ensure the contribution_date is within the data range
            if contribution_date > end_date or contribution_date not in data.index:
                continue

            # Add the weekly investment to the total
            total_investment += weekly_investment
            # Check if the contribution date and end date are within the data index
            if contribution_date in data.index and end_date in data.index:
                # Calculate the number of units of stock owned based on weekly DCA
                total_units['UPRO'] += weekly_investment / data['UPRO'].loc[contribution_date]
                total_units['GOLD'] += weekly_investment / data['GOLD'].loc[contribution_date]
                total_units['SSO'] += weekly_investment / data['SSO'].loc[contribution_date]
                total_units['UBT'] += weekly_investment / data['UBT'].loc[contribution_date]
                total_units['VOO'] += weekly_investment / data['VOO'].loc[contribution_date]
                total_units['IOO'] += weekly_investment / data['IOO'].loc[contribution_date]


                portfolio_units['60% UPRO, 40% GOLD']['UPRO'] += (weekly_investment * 0.6 ) / data['UPRO'].loc[contribution_date]
                portfolio_units['60% UPRO, 40% GOLD']['GOLD'] += (weekly_investment * 0.4 ) / data['GOLD'].loc[contribution_date]
                portfolio_units['50% SSO, 50% UBT']['SSO'] += (weekly_investment / 2) / data['SSO'].loc[contribution_date]
                portfolio_units['50% SSO, 50% UBT']['UBT'] += (weekly_investment / 2) / data['UBT'].loc[contribution_date]

                # Rebalance the 50/50 portfolios at the end of each quarter
                #TODO Fix this i doubt it working correctly
                if (contribution_date + BDay(1) in data.index) and ((contribution_date + BDay(1)).is_quarter_end):
                    # Rebalance 50% UPRO, 50% GOLD
                    total_value_upro_GOLD = (portfolio_units['60% UPRO, 40% GOLD']['UPRO'] * data['UPRO'].loc[contribution_date]) + (portfolio_units['60% UPRO, 40% GOLD']['GOLD'] * data['GOLD'].loc[contribution_date])
                    portfolio_units['60% UPRO, 40% GOLD']['UPRO'] = (total_value_upro_GOLD * 0.6) / data['UPRO'].loc[contribution_date]
                    portfolio_units['60% UPRO, 40% GOLD']['GOLD'] = (total_value_upro_GOLD * 0.4) / data['GOLD'].loc[contribution_date]

                    # Rebalance 50% SSO, 50% UBT
                    total_value_sso_ubt = (portfolio_units['50% SSO, 50% UBT']['SSO'] * data['SSO'].loc[contribution_date]) + (portfolio_units['50% SSO, 50% UBT']['UBT'] * data['UBT'].loc[contribution_date])
                    portfolio_units['50% SSO, 50% UBT']['SSO'] = (total_value_sso_ubt / 2) / data['SSO'].loc[contribution_date]
                    portfolio_units['50% SSO, 50% UBT']['UBT'] = (total_value_sso_ubt / 2) / data['UBT'].loc[contribution_date]

            else:
                #print(f"Date not found: contribution_date {contribution_date}, end_date {end_date}")
                continue

        # Calculate the final value of the portfolio based on the total units owned
        portfolio_results = {
            'UPRO': total_units['UPRO'] * data['UPRO'].loc[end_date],
            '60% UPRO, 40% GOLD': (portfolio_units['60% UPRO, 40% GOLD']['UPRO'] * data['UPRO'].loc[end_date]) + (portfolio_units['60% UPRO, 40% GOLD']['GOLD'] * data['GOLD'].loc[end_date]),
            'SSO': total_units['SSO'] * data['SSO'].loc[end_date],
            '50% SSO, 50% UBT': (portfolio_units['50% SSO, 50% UBT']['SSO'] * data['SSO'].loc[end_date]) + (portfolio_units['50% SSO, 50% UBT']['UBT'] * data['UBT'].loc[end_date]),
            'VOO': total_units['VOO'] * data['VOO'].loc[end_date],
            'IOO': total_units['IOO'] * data['IOO'].loc[end_date]

        }

        # Calculate the final CAGR and store the final value for each portfolio
        for key in portfolio_results:
            final_value = portfolio_results[key]  # This is the total value of the portfolio at the end date
            if total_investment > 0:
                cagr = (final_value / total_investment) ** (1 / period) - 1  # DCA-based CAGR calculation
            else:
                cagr = np.NaN  # Handle cases with no investment

            # Update portfolio_results to store both CAGR and final value
            portfolio_results[key] = {'CAGR': cagr, 'final_value': final_value}

            # Debug prints to check values
            # print(f"Period: {period}, Start Date: {start_date}, End Date: {end_date}, Stock: {key}, Final Value: {final_value}, Total Investment: {total_investment}, CAGR: {cagr}")

        # Store results for plotting
        result_entry = {'start_date': start_date, 'period': period}
        for key in portfolio_results:
            result_entry[f'{key}_CAGR'] = portfolio_results[key]['CAGR']
            result_entry[f'{key}_final_value'] = portfolio_results[key]['final_value']

        results.append(result_entry)

# Convert the results to a DataFrame for analysis and plotting
results_df = pd.DataFrame(results)
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.gridspec import GridSpec

# Plotting
fig = plt.figure(figsize=(15, len(investment_periods) * 5))
gs = GridSpec(len(investment_periods), 2, width_ratios=[3, 1], figure=fig)

fig.suptitle('DCA-Based CAGR and Money Gained for Different Investment Periods')

# Iterate over each investment period and plot the CAGR and money gained for each stock
for i, period in enumerate(investment_periods):
    # Plot for CAGR
    ax_cagr = fig.add_subplot(gs[i, 0])
    period_data = results_df[results_df['period'] == period]
    for stock in ['UPRO', '60% UPRO, 40% GOLD', 'SSO', '50% SSO, 50% UBT', 'VOO', 'IOO']:
        cagr_column = f'{stock}_CAGR'
        if cagr_column in period_data.columns:
            ax_cagr.plot(period_data['start_date'], 100 * period_data[cagr_column], label=stock)
        else:
            print(f"Stock '{stock}' not found in results for period {period}.")
    ax_cagr.set_title(f'{period} Year Investment Period')
    ax_cagr.set_ylabel('CAGR (%)')
    if i == 0:  # Only add legend to the topmost left subplot
        ax_cagr.legend()
    ax_cagr.xaxis.set_major_locator(mdates.YearLocator())
    ax_cagr.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    ax_cagr.grid(True)
    ax_cagr.set_ylim(-60, 60)
    ax_cagr.set_xlabel('Start Date')
    # Put solid line at 0
    ax_cagr.axhline(y=0, color='k', linestyle='-', linewidth=1)

    # Calculate total investment for the period
    total_investment = num_weeks_per_year * period * weekly_investment

    # Plot for Money Gained
    ax_money = fig.add_subplot(gs[i, 1])
    for stock in ['UPRO', '60% UPRO, 40% GOLD', 'SSO', '50% SSO, 50% UBT', 'VOO']:
        final_value_column = f'{stock}_final_value'
        if final_value_column in period_data.columns:
            money_gained = period_data[final_value_column] - total_investment
            ax_money.plot(period_data['start_date'], money_gained, label=stock)
        else:
            print(f"Stock '{stock}' not found in results for period {period}.")
    ax_money.set_title(f'{period} Year Gain on ${total_investment}')
    ax_money.set_ylabel('Money Gained')
    ax_money.xaxis.set_major_locator(mdates.YearLocator())
    ax_money.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    ax_money.grid(True)
    ax_money.set_xlabel('Start Date')

plt.tight_layout()
plt.show()