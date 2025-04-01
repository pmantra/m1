-- get cancellation_policy by product_id
SELECT
    cp.id,
    cp.name,
    cp.refund_0_hours,
    cp.refund_2_hours,
    cp.refund_6_hours,
    cp.refund_12_hours,
    cp.refund_24_hours,
    cp.refund_48_hours
FROM product pr
LEFT OUTER JOIN practitioner_profile pp ON pr.user_id = pp.user_id
LEFT OUTER JOIN cancellation_policy cp ON cp.id = pp.default_cancellation_policy_id 
WHERE pr.id = :product_id;