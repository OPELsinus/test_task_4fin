SELECT flag_l6m.client_id,
       gambling / total_amount AS
       'vendor_microfinance_gambling_payment_ratio_l12m',
       vendor_grocery_utilities_transaction_ratio_l9m,
       history_payment_delay_flag_l6m,
       history_payment_ratio_l9m_to_total,
       history_average_loan_profit_margin_l12m
FROM   (SELECT client_id,
               CASE
                 WHEN flag > 0 THEN true
                 ELSE false
               END AS 'history_payment_delay_flag_l6m'
        FROM   (SELECT l.client_id,
                       Sum(CASE
                             WHEN cf.scheduled_date < cf.payment_date THEN 1
                             ELSE 0
                           END) AS 'flag',
                       cf.scheduled_date,
                       cf.payment_date
                FROM   loans l
                       JOIN cash_flows cf
                         ON cf.loan_id = l.id
                WHERE  cf.type = 'income'
                       AND Date(cf.scheduled_date) >= Date('now', '-6 months')
                GROUP  BY l.client_id)) AS flag_l6m
		
       LEFT JOIN (SELECT DISTINCT( first.client_id ),
                                 Cast(last_9_months AS REAL) / total_payments AS
                                 'history_payment_ratio_l9m_to_total'
                  FROM   (SELECT l.client_id,
                                 Sum(cf.amount) AS 'last_9_months'
                          FROM   loans l
                                 JOIN cash_flows cf
                                   ON cf.loan_id = l.id
                          WHERE  cf.type = 'income'
                                 AND Date(cf.scheduled_date) >=
                                     Date('now', '-9 months')
                          GROUP  BY l.client_id) AS first
                         JOIN (SELECT l.client_id,
                                      Sum(cf.amount) AS 'total_payments'
                               FROM   cash_flows cf
                                      JOIN loans l
                                        ON cf.loan_id = l.id
                               WHERE  cf.type = 'income'
                               GROUP  BY l.client_id) AS second
                           ON first.client_id = second.client_id
                  GROUP  BY first.client_id) AS ratio_l9m_to_total
              ON ratio_l9m_to_total.client_id = flag_l6m.client_id
			 
       LEFT JOIN (SELECT client_id,
                         Avg(Cast(sum_for_that_loan AS REAL) / amount) AS
                         'history_average_loan_profit_margin_l12m'
                  FROM   (SELECT l.client_id,
                                 l.id,
                                 l.start_date,
                                 l.amount,
                                 Sum(cf.amount) AS 'sum_for_that_loan'
                          FROM   loans l
                                 JOIN cash_flows cf
                                   ON l.id = cf.loan_id
                          WHERE  type = 'income'
                                 AND Date(l.start_date) >=
                                     Date('now', '-12 months')
                          GROUP  BY cf.loan_id
                          ORDER  BY l.client_id)
                  GROUP  BY client_id) AS loan_profit_margin_l12m
              ON loan_profit_margin_l12m.client_id = flag_l6m.client_id
		
       LEFT JOIN (SELECT first.id,
                         Sum(CASE
                               WHEN ( category = 'gambling'
                                       OR category = 'microfinance' )
                                    AND Date(first.transaction_date) >=
                                        Date('now', '-12 months')
                             THEN
                               amount
                               ELSE NULL
                             END) AS 'gambling',
                         Sum(CASE
                               WHEN Date(first.transaction_date) >=
                                    Date('now', '-12 months')
                             THEN amount
                               ELSE NULL
                             END) AS 'total_amount'
                  FROM   (SELECT vt.phone_number,
                                 vt.amount,
                                 vt.merchant,
                                 vt.transaction_date,
                                 c.phone_number,
                                 c.id
                          FROM   vendor_transactions vt
                                 JOIN clients c
                                   ON c.phone_number = vt.phone_number) AS first
                         JOIN fake_merchants fm
                           ON Substr(Lower(first.merchant), -1) =
                              Substr(fm.merchant, -1)
                              AND Substr(Lower(first.merchant), 1, 2) =
                                  Substr(fm.merchant, 1, 2)
                  GROUP  BY first.phone_number) AS gambling
              ON gambling.id = flag_l6m.client_id
			
       LEFT JOIN (SELECT id,
                         utilities / total_amount AS
                        'vendor_grocery_utilities_transaction_ratio_l9m'
                  FROM   (SELECT first.id,
                                 Sum(CASE
                                       WHEN ( category = 'utilities'
                                               OR category = 'grocery' )
                                            AND Date(first.transaction_date) >=
                                                Date('now', '-9 months')
                                     THEN
                                       amount
                                       ELSE NULL
                                     END) AS 'utilities',
                                 Sum(CASE
                                       WHEN Date(first.transaction_date) >=
                                            Date('now', '-9 months') THEN
                                       amount
                                       ELSE NULL
                                     END) AS 'total_amount'
                          FROM   (SELECT vt.phone_number,
                                         vt.amount,
                                         vt.merchant,
                                         vt.transaction_date,
                                         c.phone_number,
                                         c.id
                                  FROM   vendor_transactions vt
                                         JOIN clients c
                                           ON c.phone_number = vt.phone_number)
                                 AS
                                 first
                                 JOIN fake_merchants fm
                                   ON Substr(Lower(first.merchant), -1) =
                                      Substr(fm.merchant, -1)
                                      AND Substr(Lower(first.merchant), 1, 2) =
                                          Substr(fm.merchant, 1, 2)
                          GROUP  BY first.phone_number)) AS utilities
              ON utilities.id = flag_l6m.client_id