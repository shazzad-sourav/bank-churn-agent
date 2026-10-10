# Data dictionary: Credit Card Customers

## Source
The dataset is the public "Credit Card Customers" dataset from Kaggle (sakshigoyal7/credit-card-customers). It is a single snapshot of 10,127 credit card customers of a consumer bank. There are no dates, so it cannot show trends over time. Customer ids are anonymised numbers, and the dataset contains no names or contact details.

## Target
`churned` is 1 when the customer has closed their credit card account ("Attrited Customer") and 0 when they are still a customer ("Existing Customer"). 1,627 of 10,127 customers churned, an overall churn rate of 16.1%.

## Demographic columns
- `customer_age`: age in years (26 to 73). Binned into `age_group`: Under 30, 30-39, 40-49, 50-59, 60+.
- `gender`: Female or Male.
- `dependent_count`: number of dependents.
- `education_level`: Uneducated, High School, College, Graduate, Post-Graduate, Doctorate, Unknown.
- `marital_status`: Married, Single, Divorced, Unknown.
- `income_category`: < $40K, $40K - $60K, $60K - $80K, $80K - $120K, $120K +, Unknown. Income is a band, not an exact number.

## Relationship columns
- `card_category`: Blue, Silver, Gold or Platinum. Blue is by far the most common card (about 93% of customers).
- `months_on_book`: how long the customer has held the card, in months.
- `total_relationship_count`: number of bank products the customer holds, from 1 to 6.
- `months_inactive_12_mon`: months with no activity in the last 12 months.
- `contacts_count_12_mon`: number of contacts with the bank's service team in the last 12 months.

## Card usage columns
- `credit_limit`: credit limit in dollars.
- `total_revolving_bal`: balance carried from month to month. 0 means the customer pays in full or does not use the card.
- `avg_open_to_buy`: unused credit (credit limit minus balance), averaged over 12 months.
- `avg_utilization_ratio`: share of the credit limit in use, between 0 and 1.
- `total_trans_amt`: total amount spent in the last 12 months.
- `total_trans_ct`: number of transactions in the last 12 months. Binned into `txn_count_band`: Under 40, 40-59, 60-79, 80+.
- `total_amt_chng_q4_q1`: spend in Q4 divided by spend in Q1.
- `total_ct_chng_q4_q1`: transaction count in Q4 divided by Q1. Values below 1 mean activity is dropping.

## Derived columns
- `status`: "Churned" or "Active", a readable version of `churned`.
- `carries_balance`: "Carries balance" or "No balance".
- Six `flag_*` columns, `risk_score` and `risk_tier`: see the risk score document.
