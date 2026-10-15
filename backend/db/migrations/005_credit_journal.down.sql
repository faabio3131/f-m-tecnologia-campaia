-- Destructive rollback: export/preserve all commercial evidence before authorization.
-- Code rollback may leave this additive table untouched; never auto-drop real usage.
DROP TABLE IF EXISTS campaia_runtime.credit_journal;
DROP FUNCTION IF EXISTS campaia_runtime.reject_credit_journal_mutation();
