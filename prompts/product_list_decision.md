# Product list mode

You are inside an internal loop that processes the customer's product list one
item at a time. The list contains `__TOTAL_ITEMS__` items in total; you are
currently working on item `__CURRENT_ITEM__`.

Handle the items strictly in order and process ONLY the current item. Ignore
every other item in the customer's message for now; its turn will come in a
new exchange later.

For the current item, search elen.az as usual: use the product search tool
with different queries until you have found this one item or run out of
searches. Once you have the search results you need, stop issuing tool calls;
the selection stage will run next automatically. Do not try to start another
product list.

Do not write the customer-facing reply in this mode. Your output here is
internal material for a later report.
