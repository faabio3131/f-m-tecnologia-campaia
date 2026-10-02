DROP TRIGGER IF EXISTS billing_charges_tenant_immutable
    ON campaia_runtime.billing_charges;
DROP TRIGGER IF EXISTS billing_subscriptions_tenant_immutable
    ON campaia_runtime.billing_subscriptions;

DROP TABLE IF EXISTS campaia_runtime.billing_charges;
DROP TABLE IF EXISTS campaia_runtime.billing_subscriptions;
