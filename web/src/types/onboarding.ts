import type { SessionUser } from "./session";

export interface OrganizationSummary {
  tenant_id: string;
  name: string;
  document: string | null;
  segment: string;
  language: string;
  timezone: string;
  entry_mode: "TRIAL" | "PURCHASE" | string;
  plan_id: string | null;
  status: string;
  default_business_unit_id: string | null;
  created_at: string;
}

export interface CommercialMembership {
  id: string;
  tenant_id: string;
  email: string;
  roles: string[];
  business_unit_id: string | null;
  status: "ACTIVE" | "INACTIVE" | string;
  created_at: string;
  updated_at: string;
  deactivated_at: string | null;
}

export interface TenantOnboardingInput {
  company_name: string;
  document?: string | null;
  segment: string;
  language: string;
  timezone: string;
  entry_mode: "TRIAL" | "PURCHASE";
  plan_id?: string | null;
}

export interface TenantOnboardingResponse {
  session: SessionUser;
  organization: OrganizationSummary;
  membership: CommercialMembership;
}

export interface MemberInvitation {
  id: string;
  email: string;
  roles: string[];
  business_unit_id: string | null;
  status: string;
  created_at: string;
  expires_at: string;
  accepted_by: string | null;
  accept_token: string | null;
}
