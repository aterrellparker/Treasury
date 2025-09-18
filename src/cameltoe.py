import camelot
import matplotlib.pyplot as plt
import glob
import os
import numpy as np
import re
from decimal import Decimal
import pandas as pd

for file in glob.glob('./Statements/Tables/*.csv'):
    os.remove(file)

transactionTable = pd.DataFrame(columns=['Date', 'Description', 'Amount'])
for file in glob.glob('./Statements/*.pdf'):
    # print(file)
    tables = camelot.read_pdf(file, pages='2', flavor='stream')  
    for table in tables:
        if(np.any(table.df.to_numpy() == 'Transaction history')):
            # name = './Tables/' + file+ ' ' + str(i) +'.csv'
            # print(name)
            # table.to_csv(name)

            dateIndex = table.df.index[table.df[0].str.contains('Date')].tolist()
            if(len(dateIndex) > 0):
                # starting from the row after the header row
                for row in range(dateIndex[0]+1, len(table.df)):
                    dateString = str(table.df.iloc[row, 0]).strip()
                    # print(table.df.iloc[row, 0])
                    #check if cell contains Ending
                    if 'Ending' in str(dateString) or 'Totals' in str(dateString):
                        break
                    elif dateString != '' and dateString is not None:
                        date = str(dateString).strip()
                        m = re.search(r"(\d{1,2}/\d{1,2})([^)]*)", date)
                        date = m.group(1) if m else None

                        year = re.search(r'(\d{4})(\d{2})', file)
                        # print(file)
                        date = date + '/' + year.group(2)

                        description = m.group(2).strip() if m else None

                        description += str(table.df.iloc[row, -4]).strip()

                        if row +1 <= len(table.df) and table.df.iloc[row +1 , 0] == '': # description is on two lines
                            description += ' ' + str(table.df.iloc[row + 1, -4]).strip()
                        #get last column in row
                        #convert to decimal
                        amount = 0
                        # get last last cell in row
                        deposits = table.df.iloc[row, -3]
                        if deposits != '' and deposits is not None:
                            amount += Decimal(re.sub(r'[^\d.]', '', deposits))
                                                    
                        withdrawals = table.df.iloc[row, -2]
                        if withdrawals != '' and withdrawals is not None:
                            amount -= Decimal(re.sub(r'[^\d.]', '', withdrawals))

                        transactionTable = pd.concat([transactionTable, pd.DataFrame({'Date': [date], 'Description': [description], 'Amount': [amount]})], ignore_index=True)
print(transactionTable)
transactionTable['Date'] = pd.to_datetime(transactionTable['Date'], format='%m/%d/%y')
transactionTable = transactionTable.sort_values(by=['Date'])
#remove duplicate dates after 27th
cutoff_date = '2023-03-27'
transactionTable = transactionTable[transactionTable['Date'] < cutoff_date]
transactionTable.to_csv('./Statements/checking_' + cutoff_date + '.csv', index=False, header=False)
transactionTable['Balance'] = transactionTable['Amount'].cumsum()
monthly_balance = (
    transactionTable.groupby(pd.Grouper(key="Date", freq="ME"))["Balance"]
      .last()
      .reset_index()
)
print(monthly_balance)