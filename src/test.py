import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

import pandas as pd

import ingest

DB_PATH = "./database.db"

d = ingest.DataManager(DB_PATH)
df = d._create_due_dates()

df.to_csv('dues.csv')
# Step 4: Count members owing dues per cycle
dues_counts = df.groupby('PeriodStart')['GBId'].nunique().reset_index(name='MemberCount')

# Add a CycleLabel column
dues_counts['CycleLabel'] = dues_counts['PeriodStart'].dt.strftime('%b %Y')

plt.figure(figsize=(12,6))
plt.plot(dues_counts['CycleLabel'], dues_counts['MemberCount'], marker='o')

plt.title("Members Owing Dues Per Cycle")
plt.xlabel("Cycle")
plt.ylabel("Number of Members")

# Force integer ticks on y-axis
ax = plt.gca()
ax.yaxis.set_major_locator(MaxNLocator(integer=True))

plt.grid(True)
plt.xticks(rotation=45)

# Annotate each point with the count
for x, y in zip(dues_counts['CycleLabel'], dues_counts['MemberCount']):
    plt.text(x, y + 0.2, str(y), ha='center', va='bottom', fontsize=9)

dues_amount = df.groupby('PeriodStart')[''].sum()
print(dues_amount)

plt.tight_layout()
plt.show()