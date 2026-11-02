export type Severity = "critical" | "high" | "medium" | "low" | "info";

export interface AppSummary {
  id: string;
  institution_name: string;
  institution_id: string;
  application_type: string;
  state: string;
  academic_year: string;
  submitted_at: string;
  processing_status: string;
  review_status: string;
  risk_score: number | null;
  risk_band: "Low" | "Medium" | "High" | null;
  is_demo: boolean;
  document_count: number;
  finding_count: number;
  open_finding_count: number;
  outcome_counts: Record<string, number>;
}

export interface DocSummary {
  id: string;
  application_id: string;
  declared_category: string;
  declared_category_label: string;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  sha256: string;
  page_count: number;
  processing_status: "Uploaded" | "Processed" | "Failed";
  processing_error: string | null;
  extraction_method: string | null;
  ocr_engine: string | null;
  ocr_confidence: number | null;
  detected_type: string | null;
  detected_type_label: string | null;
  classification_confidence: number | null;
  document_status: string;
  issuer_verification: string;
  is_demo: boolean;
  uploaded_at: string;
  processed_at: string | null;
}

export interface FieldValue {
  value: string | null;
  normalized: string | null;
  status: "detected" | "uncertain" | "missing";
  page: number | null;
  evidence: string | null;
  method?: string;
  note: string | null;
}

export interface DocDetail extends DocSummary {
  pages: { page: number; text: string; method: string; confidence: number | null }[];
  fields: Record<string, FieldValue>;
  screening: Record<string, unknown>;
  classification_scores: Record<string, number>;
  findings: Finding[];
}

export interface Finding {
  id: string;
  application_id: string;
  document_id: string | null;
  rule_id: string;
  rule_version: number;
  outcome: string;
  severity: Severity;
  title: string;
  description: string;
  expected: string | null;
  actual: string | null;
  evidence: string | null;
  evidence_source: string | null;
  page: number | null;
  recommended_action: string;
  factor: string;
  status: "Open" | "Reviewed";
  reviewer_note: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  created_at: string;
}

export interface ScoreBreakdown {
  score: number;
  band: string;
  raw_total: number;
  factors: Record<string, { label: string; count: number; points: number }>;
  items: { finding_id: string; rule_id: string; severity: Severity; factor: string; points: number; title: string }[];
  formula: string;
  severity_points: Record<string, number>;
  factor_weights: Record<string, number>;
  bands: { medium: number; high: number };
  disclaimer: string;
  scoring_version: number;
}

export interface Review {
  id: number;
  action: string;
  action_label: string;
  notes: string;
  officer_name: string;
  created_at: string;
}

export interface AppDetail extends AppSummary {
  documents: DocSummary[];
  findings: Finding[];
  reviews: Review[];
  score_breakdown: ScoreBreakdown | null;
  applied_rules: { id: string; version: number; name: string; group: string }[] | null;
  ruleset_fingerprint: string | null;
  last_evaluated_at: string | null;
}

export interface AuditEvent {
  id: number;
  application_id: string | null;
  event_type: string;
  actor: string;
  details: Record<string, unknown>;
  created_at: string;
  prev_hash: string;
  hash: string;
}

export interface Rule {
  id: string;
  name: string;
  description: string;
  rule_type: string;
  rule_type_label: string;
  group: string;
  params: Record<string, unknown>;
  severity: Severity;
  enabled: boolean;
  version: number;
  is_builtin: boolean;
  updated_at: string;
}

export interface Meta {
  document_categories: Record<string, string>;
  application_types: string[];
  review_actions: Record<string, { label: string; resulting_status: string | null }>;
  fields: Record<string, string>;
  rule_types: Record<string, string>;
  custom_rule_types: string[];
  severities: Severity[];
  max_upload_mb: number;
  accepted_types: string[];
}

export interface Dashboard {
  totals: Record<string, number>;
  risk_distribution: { band: string; count: number }[];
  document_status: Record<string, number>;
  findings_by_outcome: Record<string, number>;
  recent_applications: AppSummary[];
  recent_activity: AuditEvent[];
}
