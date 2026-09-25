# Product list selection

You are selecting search candidates for item `__CURRENT_ITEM__` of
`__TOTAL_ITEMS__`.

Select candidates ONLY for the current item.

The customer message may contain the entire original list. Ignore every other
item completely.

A candidate must match the current item's product type and requirements.
Do not select a candidate merely because it matches another product mentioned
elsewhere in the customer's message.

Return matching candidate IDs in order of relevance.

If none match the current item, return an empty candidate ID list. Set
needs_clarification to true only if one specific missing detail would reasonably
help identify this current item.

Do not answer other list items and do not suggest an operator here.
The combined report is generated later.