# -*- coding: utf-8 -*-
"""
Created on Sun Oct 26 15:21:27 2025

@author: user
"""

import json
import pandas as pd
import matplotlib.pyplot as plt

with open("ecm_results.json", "r") as f:
    results_dict = json.load(f)

## National
national_measure_stock = {}
national_stock_penetration = {}

for ecm in results_dict.keys():
    if ecm != 'On-site Generation':
        national_measure_stock[ecm] = results_dict[ecm]["Markets and Savings (Overall)"]["Max adoption potential"]["Measure Stock (Competed)(units equipment)"]
        national_stock_penetration[ecm] = {}

        for year in range(2025, 2051):
            national_stock_penetration[ecm][year] = results_dict[ecm]["Markets and Savings (Overall)"]["Max adoption potential"]["Measure Stock (Competed)(units equipment)"][str(year)] / results_dict[ecm]["Markets and Savings (Overall)"]["Max adoption potential"]["Baseline Stock (Uncompeted)(units equipment)"][str(year)]

# National measure stock
df_national_measure_stock = pd.DataFrame.from_dict(national_measure_stock)
df_national_measure_stock.index.name = 'Year'
df_national_measure_stock = df_national_measure_stock.drop('2024')

df_national_measure_stock.plot(figsize=(10, 6))

plt.title('National ECM Measure Stock over Time')
plt.xlabel('Year')
plt.ylabel('Measure Stock (Units of Equipment)')
plt.grid(True, linestyle='--', alpha=0.6)
plt.legend(title='ECMs')
plt.tight_layout() 
plt.savefig('national_ecm_measure_stock_over_time.png')
plt.show()

# National measure stock share
df_national_measure_stock['Total Measure Stock'] = df_national_measure_stock.sum(axis=1, numeric_only=True)
df_national_measure_stock_dummy = df_national_measure_stock.copy()
df_national_measure_share = df_national_measure_stock_dummy[['(R) ESTAR GSHP (NG Furnace)', '(R) ESTAR HP FS (NG Furnace)', '(R) Ref. Case NG Heat, No Cooling', '(R) Ref. Case NG Furnace & AC', '(R) ESTAR HP FS (NG Heat, No Cool)']].div(df_national_measure_stock['Total Measure Stock'], axis=0)

df_national_measure_share.plot(figsize=(10, 6))

ax = df_national_measure_share.plot(kind='bar', stacked=True, figsize=(12, 7), 
                    title='Share of Measures Over Years',
                    rot=45)

plt.title('National ECM Measure Share over Time')
plt.xlabel('Year')
plt.ylabel('Share')
plt.yticks([0, 0.2, 0.4, 0.6, 0.8, 1.0], ['0%', '20%', '40%', '60%', '80%', '100%']) 
plt.legend(title='Measures', bbox_to_anchor=(1.05, 1), loc='upper left')
plt.grid(axis='y', linestyle='--', alpha=0.7)
plt.tight_layout() 
plt.savefig('national_ecm_measure_share_over_time.png')
plt.show()

# National stock penetration
df_national_stock_penetration = pd.DataFrame.from_dict(national_stock_penetration)
df_national_stock_penetration.index.name = 'Year'
df_national_stock_penetration = df_national_stock_penetration*100

df_national_stock_penetration.plot(figsize=(10, 6))

plt.title('National ECM Stock Penetration over Time')
plt.xlabel('Year')
plt.ylabel('Stock Penetration (%)')
plt.grid(True, linestyle='--', alpha=0.6)
plt.legend(title='ECMs')
plt.tight_layout() 
plt.savefig('national_ecm_stock_penetration_over_time.png')
plt.show()

## By State
list_of_states = list(results_dict["(R) ESTAR GSHP (NG Furnace)"]["Markets and Savings (by Category)"]["Max adoption potential"]["Measure Stock (units equipment)"].keys())
#list_of_building_types = list(results_dict["(R) ESTAR GSHP (NG Furnace)"]["Markets and Savings (by Category)"]["Max adoption potential"]["Measure Stock (units equipment)"]['AL'].keys())
list_of_building_types = ['Single Family Homes (New)', 'Multi Family Homes (New)', 'Manufactured Homes (New)', 'Single Family Homes (Existing)', 'Multi Family Homes (Existing)', 'Manufactured Homes (Existing)']

state_measure_stock = {}
for state in list_of_states:
    state_measure_stock[state] = {}
    for ecm in results_dict.keys():
        if ecm != 'On-site Generation':            
            state_measure_stock[state][ecm] = {}
            for building_type in list_of_building_types:
                if ecm == '(R) Ref. Case NG Heat, No Cooling':
                    state_measure_stock[state][ecm][building_type] = results_dict[ecm]["Markets and Savings (by Category)"]["Max adoption potential"]["Measure Stock (units equipment)"][state][building_type]["Heating (Equip.)"]["Natural Gas"]    
                elif ecm == '(R) Ref. Case NG Furnace & AC':
                    state_measure_stock[state][ecm][building_type] = results_dict[ecm]["Markets and Savings (by Category)"]["Max adoption potential"]["Measure Stock (units equipment)"][state][building_type]["Heating (Equip.)"]["Natural Gas"]
                else:
                    state_measure_stock[state][ecm][building_type] = results_dict[ecm]["Markets and Savings (by Category)"]["Max adoption potential"]["Measure Stock (units equipment)"][state][building_type]["Heating (Equip.)"]["Electric"]

state_measure_stock_building_type_total = {}
for state in list_of_states:
    state_measure_stock_building_type_total[state] = {}
    for ecm in results_dict.keys():
        if ecm != 'On-site Generation':   
            state_measure_stock_building_type_total[state][ecm] = {}
            #state_measure_stock[state][ecm]["Building Type Total"] = {}
            for year in range(2025, 2051):
                state_measure_stock_building_type_total[state][ecm][year] = 0
                for building_type in list_of_building_types:
                    state_measure_stock_building_type_total[state][ecm][year] += state_measure_stock[state][ecm][building_type][str(year)]

def generate_state_measure_stock_and_share_graphs(state):
    # Measure Stock
    df_stock = pd.DataFrame.from_dict(state_measure_stock_building_type_total[state])
    df_stock.index.name = 'Year'

    df_stock.plot(figsize=(10, 6))

    plt.title(state + ' ECM Measure Stock over Time')
    plt.xlabel('Year')
    plt.ylabel('Measure Stock (Units of Equipment)')
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.legend(title='ECMs')
    plt.tight_layout() 
    plt.savefig(state+'_ecm_measure_stock_over_time.png')
    plt.show()
    
    # Measure share
    df_stock['Total Measure Stock'] = df_stock.sum(axis=1, numeric_only=True)
    df_stock_dummy = df_stock.copy()
    df_share = df_stock_dummy[['(R) ESTAR GSHP (NG Furnace)', '(R) ESTAR HP FS (NG Furnace)', '(R) Ref. Case NG Heat, No Cooling', '(R) Ref. Case NG Furnace & AC', '(R) ESTAR HP FS (NG Heat, No Cool)']].div(df_stock['Total Measure Stock'], axis=0)

    df_share.plot(figsize=(10, 6))

    ax = df_share.plot(kind='bar', stacked=True, figsize=(12, 7), 
                        title='Share of Measures Over Years',
                        rot=45)

    plt.title(state + ' ECM Measure Share over Time')
    plt.xlabel('Year')
    plt.ylabel('Share')
    plt.yticks([0, 0.2, 0.4, 0.6, 0.8, 1.0], ['0%', '20%', '40%', '60%', '80%', '100%']) 
    plt.legend(title='Measures', bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout() 
    plt.savefig(state+'_ecm_measure_share_over_time.png')
    plt.show()
    
    return [df_stock, df_share]

# 2050 results summary
summarized_results = {}
for state in list_of_states:
    summarized_results[state] = generate_state_measure_stock_and_share_graphs(state)

ASHP_FS_with_cooling_2050_measure_stock = {}
ASHP_FS_with_cooling_2050_measure_share = {}
for state in list_of_states:
    ASHP_FS_with_cooling_2050_measure_stock[state] = summarized_results[state][0].loc[2050, '(R) ESTAR HP FS (NG Furnace)']
    ASHP_FS_with_cooling_2050_measure_share[state] = summarized_results[state][1].loc[2050, '(R) ESTAR HP FS (NG Furnace)']

df_ASHP_FS_with_cooling_2050_measure_stock = pd.DataFrame.from_dict(ASHP_FS_with_cooling_2050_measure_stock, orient='index')
df_ASHP_FS_with_cooling_2050_measure_stock.index.name = 'State'
   
ax = df_ASHP_FS_with_cooling_2050_measure_stock.plot(kind='bar', figsize=(15, 6), legend=False)

plt.title('ASHP FS 2050 ECM Measure Stock by State')
plt.xlabel('State')
plt.ylabel('Measure Stock (Units of Equipment)')
plt.tight_layout()
plt.savefig('ASHP_FS_2050_measure_stock_by_state.png')
plt.show()


df_ASHP_FS_with_cooling_2050_measure_share = pd.DataFrame.from_dict(ASHP_FS_with_cooling_2050_measure_share, orient='index')
df_ASHP_FS_with_cooling_2050_measure_share.index.name = 'State'
df_ASHP_FS_with_cooling_2050_measure_share = df_ASHP_FS_with_cooling_2050_measure_share*100

ax = df_ASHP_FS_with_cooling_2050_measure_share.plot(kind='bar', figsize=(15, 6), legend=False)

plt.title('ASHP FS 2050 ECM Measure Share by State')
plt.xlabel('State')
plt.ylabel('Share (%)')
plt.tight_layout()
plt.savefig('ASHP_FS_2050_measure_share_by_state.png')
plt.show()

df_ASHP_FS_with_cooling_2050_scatter = df_ASHP_FS_with_cooling_2050_measure_stock
df_ASHP_FS_with_cooling_2050_scatter['Share'] = df_ASHP_FS_with_cooling_2050_measure_share
df_ASHP_FS_with_cooling_2050_scatter.rename(columns={0: 'Measure Stock'}, inplace=True)

df_ASHP_FS_with_cooling_2050_scatter.plot(
    kind='scatter', 
    x='Measure Stock', 
    y='Share', 
    figsize=(10, 6)
)

plt.title('Measure sotck and share by state')
plt.xlabel('Measure Stock (Units of Equipment)')
plt.ylabel('Share (%)')
plt.savefig('ASHP_FS_2050_scatter_plot_by_state.png')
plt.show()