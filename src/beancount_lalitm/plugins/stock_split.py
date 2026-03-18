"""Plugin to adjust historical transactions for stock splits.

When a stock split occurs, this plugin retroactively adjusts the units
and prices of all historical transactions before the split date so that
quantities and prices are consistent with post-split values.

Usage in beancount:
  plugin "plugins.stock_split" "
    splits:
      - symbol: GOOG
        date: 2022-07-15
        ratio: 20
  "

This will multiply all GOOG units before 2022-07-15 by 20 and divide
the price by 20, keeping the total value unchanged.
"""
from beancount.core.data import Cost, Entries, Transaction, Posting, Amount, Price, Balance, Price as PriceEntry
from dataclasses import dataclass
import collections
from datetime import timedelta, datetime, date
from decimal import Decimal
import sys
from typing import Callable, Any, Union
import yaml

__plugins__ = ['stock_split']

ZERO = Decimal('0')


def stock_split(entries: Entries, _: dict, plugin_config: str):
  config: dict = yaml.safe_load(plugin_config)
  splits: dict[str, Any] = {l['symbol']: l for l in config['splits']}
  errors: list[str] = []
  
  new_entries = []
  for entry in entries:
    if isinstance(entry, Transaction):
      new_postings = []
      modified = False
      for posting in entry.postings:
        if posting.units.currency not in splits:
          new_postings.append(posting)
          continue
        
        s = splits[posting.units.currency]
        split_date = s['date']
        if entry.date >= split_date:
          new_postings.append(posting)
          continue
        
        ratio = Decimal(s['ratio'])
        new_units = Amount(posting.units.number * ratio, posting.units.currency)
        
        new_cost = posting.cost
        if posting.cost is not None:
          new_cost = posting.cost._replace(number=posting.cost.number / ratio)
        
        new_price = posting.price
        if posting.price is not None:
          new_price = posting.price._replace(number=posting.price.number / ratio)
        
        new_postings.append(posting._replace(units=new_units, cost=new_cost, price=new_price))
        modified = True
      
      if modified:
        new_entries.append(entry._replace(postings=new_postings))
      else:
        new_entries.append(entry)
        
    elif isinstance(entry, Balance):
       if entry.amount.currency in splits:
         s = splits[entry.amount.currency]
         if entry.date < s['date']:
           ratio = Decimal(s['ratio'])
           new_amount = Amount(entry.amount.number * ratio, entry.amount.currency)
           new_entries.append(entry._replace(amount=new_amount))
           continue
       new_entries.append(entry)
       
    elif isinstance(entry, PriceEntry):
       if entry.currency in splits:
         s = splits[entry.currency]
         if entry.date < s['date']:
           ratio = Decimal(s['ratio'])
           new_amount = Amount(entry.amount.number / ratio, entry.amount.currency)
           new_entries.append(entry._replace(amount=new_amount))
           continue
       new_entries.append(entry)
       
    else:
      new_entries.append(entry)

  return new_entries, errors
