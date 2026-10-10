# Churn risk score: method

## Why a rule-based score
The risk score is a transparent, rule-based score rather than a machine learning model. Each rule is a warning sign a business user can understand and check, so the retention team can see exactly why a customer was flagged. It is a baseline that any predictive model should be compared against.

## The six warning signs (one point each)
1. Low transactions (`flag_low_txn`): fewer than 60 transactions in the last 12 months.
2. Activity drop (`flag_activity_drop`): Q4-to-Q1 transaction count ratio below 0.6.
3. No revolving balance (`flag_no_balance`): revolving balance of 0.
4. High service contacts (`flag_high_contacts`): 4 or more contacts with the bank in 12 months.
5. Few products (`flag_few_products`): 2 or fewer bank products.
6. Inactivity (`flag_inactive`): 3 or more inactive months in the last 12 months.

`risk_score` is the number of warning signs, from 0 to 6.

## Risk tiers
- High: score of 3 or more.
- Medium: score of exactly 2.
- Low: score of 0 or 1.

## How well it separates churners
Churn rate rises steadily with the score: about 1% at score 0, 2.6% at 1, 10.6% at 2, 34.9% at 3, 76.3% at 4, 90.6% at 5 and 100% at 6. The High tier contains 2,342 customers with a 51.4% churn rate and captures 74% of all past churners (1,205 of 1,627).

## Limitations
- The thresholds were chosen by looking at this same dataset, and the score is evaluated on that same data. It needs validating on new months of data before it is used for real decisions.
- The data is a single snapshot, so the score shows association, not cause.
- Some groups are small: score 6 has only 36 customers, 6 service contacts has 54, and 0 inactive months has 29. Treat rates for these groups with care.
