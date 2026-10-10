# Key findings and recommendations

These findings come from the companion Power BI dashboard project (bank-churn-powerbi).

## Finding 1: Demographics barely move churn
Churn by income band only ranges from 13.5% ($60K - $80K) to 17.3% ($120K +). Age, gender, education and marital status show similarly small differences. Female customers churn at 17.4% and male customers at 14.6%. Who the customer is matters much less than how they use the card.

## Finding 2: Low card activity is the strongest signal
Customers with fewer than 60 transactions a year churn at about 35%, while customers with 60 or more churn at about 4%. By band: Under 40 transactions 30.1%, 40-59 39.1%, 60-79 6.2%, 80+ 1.3%.

## Finding 3: Customers with no revolving balance leave
Customers with a revolving balance of 0 churn at 36.2%, compared with 9.6% for customers who carry a balance, about 3.8 times higher.

## Finding 4: Repeated service contacts come before churn
Churn rises with the number of service contacts in the last 12 months: 1.8% at 0 contacts, 7.2% at 1, 12.5% at 2, 20.1% at 3, 22.6% at 4, 33.5% at 5, and 100% at 6 (only 54 customers).

## Finding 5: Fewer products means a weaker relationship
Customers with 1 or 2 bank products churn at about 27%, compared with about 11% for customers with 4 or more.

## Recommendations
1. Trigger outreach when a customer's quarterly transaction count drops, before inactivity sets in.
2. Treat a third or later service contact in 12 months as an escalation, not a routine ticket.
3. Cross-sell a second or third product to customers who hold only one or two.
4. Use the High risk tier as a retention call list: 1,137 customers are still active in the High tier and hold about $10.7M in credit limits.
5. Re-check the score monthly and compare any predictive model against this rule-based baseline.
