PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS schema_meta(schema_version TEXT PRIMARY KEY, applied_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS business(
 business_id TEXT PRIMARY KEY,name TEXT NOT NULL,normalized_name TEXT NOT NULL,sector TEXT,website TEXT,
 created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS location(
 location_id TEXT PRIMARY KEY,business_id TEXT NOT NULL REFERENCES business(business_id),name TEXT,branch_type TEXT,
 address TEXT,phone TEXT,email TEXT,opening_hours TEXT,source_url TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS channel(
 channel_id TEXT PRIMARY KEY,business_id TEXT NOT NULL REFERENCES business(business_id),name TEXT NOT NULL,channel_type TEXT,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS canonical_product(
 canonical_product_id TEXT PRIMARY KEY,product_family TEXT,brand TEXT,canonical_name TEXT NOT NULL,category TEXT,
 product_type TEXT,variant_key TEXT,gtin TEXT,manufacturer_sku TEXT,attributes_json TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS entity_resolution_map(
 resolution_id TEXT PRIMARY KEY,canonical_product_id TEXT NOT NULL REFERENCES canonical_product(canonical_product_id),
 business_id TEXT REFERENCES business(business_id),platform TEXT,raw_name TEXT NOT NULL,normalized_name TEXT NOT NULL,
 raw_sku TEXT,source_url TEXT,match_method TEXT,match_score REAL,match_status TEXT,attributes_json TEXT,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS listing(
 listing_id TEXT PRIMARY KEY,business_id TEXT NOT NULL REFERENCES business(business_id),
 canonical_product_id TEXT REFERENCES canonical_product(canonical_product_id),platform TEXT,seller_name TEXT,
 raw_name TEXT NOT NULL,raw_sku TEXT,variant_text TEXT,source_url TEXT NOT NULL,channel_scope TEXT,location_scope TEXT,
 first_seen_at TEXT NOT NULL,last_seen_at TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1,
 UNIQUE(business_id,platform,source_url));
CREATE TABLE IF NOT EXISTS price_version(
 price_version_id TEXT PRIMARY KEY,listing_id TEXT NOT NULL REFERENCES listing(listing_id),price_type TEXT NOT NULL,
 price REAL NOT NULL,currency TEXT NOT NULL,regular_price REAL,promo_price REAL,member_price REAL,
 promotion_mechanic TEXT,valid_from TEXT,valid_to TEXT,first_seen_at TEXT NOT NULL,last_seen_at TEXT NOT NULL,
 current INTEGER NOT NULL DEFAULT 1,fingerprint TEXT NOT NULL,source_evidence_id TEXT);
CREATE TABLE IF NOT EXISTS promotion(
 promotion_id TEXT PRIMARY KEY,business_id TEXT NOT NULL REFERENCES business(business_id),campaign_name TEXT,
 promotion_type TEXT,description TEXT,valid_from TEXT,valid_to TEXT,valid_time_from TEXT,valid_time_to TEXT,
 days_of_week TEXT,published_at TEXT,first_seen_at TEXT NOT NULL,last_seen_at TEXT NOT NULL,current INTEGER NOT NULL DEFAULT 1,
 fingerprint TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS promotion_offer(
 offer_id TEXT PRIMARY KEY,promotion_id TEXT NOT NULL REFERENCES promotion(promotion_id),offer_type TEXT,product_scope TEXT,
 category_scope TEXT,regular_price REAL,promo_price REAL,discount_amount REAL,discount_percent REAL,minimum_spend REAL,
 minimum_quantity REAL,free_item TEXT,promo_code TEXT,usage_limit TEXT,quota TEXT,stackable TEXT,terms TEXT,exclusions TEXT,
 availability_scope_json TEXT,eligibility_json TEXT,payment_condition_json TEXT);
CREATE TABLE IF NOT EXISTS evidence(
 evidence_id TEXT PRIMARY KEY,business_id TEXT REFERENCES business(business_id),source_url TEXT,source_image TEXT,
 source_document TEXT,source_type TEXT,extraction_method TEXT,source_tag TEXT,published_at TEXT,collected_at TEXT NOT NULL,
 content_hash TEXT NOT NULL,raw_text TEXT,raw_json TEXT,confidence REAL,schema_version TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS uq_evidence ON evidence(content_hash,source_url,extraction_method);
CREATE TABLE IF NOT EXISTS marketplace_signal(
 signal_id TEXT PRIMARY KEY,canonical_product_id TEXT REFERENCES canonical_product(canonical_product_id),platform TEXT NOT NULL,
 listing_url TEXT,price REAL,currency TEXT,sold_display TEXT,sold_lower_bound INTEGER,sold_exact INTEGER,rating REAL,
 review_count INTEGER,rank_value INTEGER,bestseller_flag INTEGER,flash_sale INTEGER,observed_at TEXT NOT NULL,
 evidence_id TEXT REFERENCES evidence(evidence_id));
CREATE INDEX IF NOT EXISTS idx_price_listing_current ON price_version(listing_id,current);
CREATE INDEX IF NOT EXISTS idx_promo_business_current ON promotion(business_id,current);
CREATE INDEX IF NOT EXISTS idx_listing_canonical ON listing(canonical_product_id);

CREATE TABLE IF NOT EXISTS entity_resolution_review(
  review_id TEXT PRIMARY KEY,
  business_id TEXT REFERENCES business(business_id),
  raw_name TEXT NOT NULL,
  platform TEXT,
  source_url TEXT,
  brand TEXT,
  category TEXT,
  extracted_attributes_json TEXT,
  candidate_product_id TEXT REFERENCES canonical_product(canonical_product_id),
  candidate_name TEXT,
  match_score REAL,
  conflicts_json TEXT,
  status TEXT NOT NULL DEFAULT 'pending',
  reviewer_note TEXT,
  created_at TEXT NOT NULL,
  reviewed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_resolution_review_status ON entity_resolution_review(status,created_at);

CREATE TABLE IF NOT EXISTS acquisition_run(
  run_id TEXT PRIMARY KEY,
  business_id TEXT REFERENCES business(business_id),
  adapter_key TEXT,
  source_url TEXT,
  page_type TEXT,
  started_at TEXT,
  completed_at TEXT,
  raw_record_count INTEGER DEFAULT 0,
  useful_record_count INTEGER DEFAULT 0,
  quality_score REAL,
  status TEXT,
  diagnostics_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_acquisition_run_business ON acquisition_run(business_id,completed_at);

CREATE TABLE IF NOT EXISTS content_item(
  content_id TEXT PRIMARY KEY,
  business_id TEXT REFERENCES business(business_id),
  source_type TEXT,
  content_type TEXT NOT NULL,
  title TEXT,
  author TEXT,
  channel TEXT,
  source_url TEXT NOT NULL,
  published_at TEXT,
  collected_at TEXT NOT NULL,
  language TEXT,
  authority_class TEXT,
  raw_text TEXT,
  content_hash TEXT NOT NULL,
  evidence_id TEXT REFERENCES evidence(evidence_id),
  UNIQUE(source_url,content_hash)
);

CREATE TABLE IF NOT EXISTS content_segment(
  segment_id TEXT PRIMARY KEY,
  content_id TEXT NOT NULL REFERENCES content_item(content_id),
  segment_index INTEGER,
  start_seconds REAL,
  end_seconds REAL,
  text TEXT NOT NULL,
  segment_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS topic(
  topic_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  parent_topic_id TEXT REFERENCES topic(topic_id),
  domain TEXT,
  status TEXT DEFAULT 'controlled',
  UNIQUE(name,domain)
);

CREATE TABLE IF NOT EXISTS content_topic(
  content_id TEXT NOT NULL REFERENCES content_item(content_id),
  topic_id TEXT NOT NULL REFERENCES topic(topic_id),
  confidence REAL,
  method TEXT,
  PRIMARY KEY(content_id,topic_id)
);

CREATE TABLE IF NOT EXISTS opinion(
  opinion_id TEXT PRIMARY KEY,
  content_id TEXT NOT NULL REFERENCES content_item(content_id),
  segment_id TEXT REFERENCES content_segment(segment_id),
  topic_id TEXT REFERENCES topic(topic_id),
  entity_text TEXT,
  statement TEXT NOT NULL,
  sentiment TEXT,
  opinion_type TEXT,
  confidence REAL,
  evidence_text TEXT
);

CREATE TABLE IF NOT EXISTS claim(
  claim_id TEXT PRIMARY KEY,
  content_id TEXT NOT NULL REFERENCES content_item(content_id),
  segment_id TEXT REFERENCES content_segment(segment_id),
  topic_id TEXT REFERENCES topic(topic_id),
  statement TEXT NOT NULL,
  claim_type TEXT,
  authority_class TEXT,
  confidence REAL,
  evidence_text TEXT
);

CREATE TABLE IF NOT EXISTS learning_journey_step(
  step_id TEXT PRIMARY KEY,
  domain TEXT NOT NULL,
  sequence_no INTEGER NOT NULL,
  name TEXT NOT NULL,
  description TEXT,
  UNIQUE(domain,sequence_no)
);

CREATE TABLE IF NOT EXISTS content_journey_link(
  content_id TEXT NOT NULL REFERENCES content_item(content_id),
  step_id TEXT NOT NULL REFERENCES learning_journey_step(step_id),
  relevance REAL,
  method TEXT,
  PRIMARY KEY(content_id,step_id)
);

CREATE TABLE IF NOT EXISTS place(
  place_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  place_type TEXT,
  country TEXT,
  region TEXT,
  latitude REAL,
  longitude REAL,
  attributes_json TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS equipment_knowledge(
  equipment_id TEXT PRIMARY KEY,
  canonical_product_id TEXT REFERENCES canonical_product(canonical_product_id),
  equipment_family TEXT NOT NULL,
  name TEXT,
  beginner_relevance TEXT,
  fit_considerations TEXT,
  buy_or_rent TEXT,
  safety_notes TEXT,
  attributes_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_content_item_type ON content_item(content_type,source_type,published_at);
CREATE INDEX IF NOT EXISTS idx_opinion_topic ON opinion(topic_id);
CREATE INDEX IF NOT EXISTS idx_claim_topic ON claim(topic_id);

CREATE TABLE IF NOT EXISTS knowledge_entity(
  entity_id TEXT PRIMARY KEY,
  entity_type TEXT NOT NULL,
  canonical_name TEXT NOT NULL,
  normalized_name TEXT NOT NULL,
  attributes_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(entity_type,normalized_name)
);
CREATE TABLE IF NOT EXISTS entity_mention(
  mention_id TEXT PRIMARY KEY,
  content_id TEXT NOT NULL REFERENCES content_item(content_id),
  entity_id TEXT NOT NULL REFERENCES knowledge_entity(entity_id),
  mention_text TEXT,
  mention_count INTEGER DEFAULT 1,
  confidence REAL,
  method TEXT,
  UNIQUE(content_id,entity_id,method)
);
CREATE TABLE IF NOT EXISTS claim_entity(
  claim_id TEXT NOT NULL REFERENCES claim(claim_id),
  entity_id TEXT NOT NULL REFERENCES knowledge_entity(entity_id),
  PRIMARY KEY(claim_id,entity_id)
);
CREATE TABLE IF NOT EXISTS emerging_topic(
  emerging_id TEXT PRIMARY KEY,
  domain TEXT NOT NULL,
  term TEXT NOT NULL,
  document_frequency INTEGER,
  status TEXT DEFAULT 'candidate',
  examples_json TEXT,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  UNIQUE(domain,term)
);
CREATE INDEX IF NOT EXISTS idx_knowledge_entity_type ON knowledge_entity(entity_type,normalized_name);
CREATE INDEX IF NOT EXISTS idx_entity_mention_entity ON entity_mention(entity_id);

CREATE TABLE IF NOT EXISTS verification_claim(
  verification_claim_id TEXT PRIMARY KEY,
  domain TEXT NOT NULL,
  claim_text TEXT NOT NULL,
  normalized_claim TEXT NOT NULL,
  claim_type TEXT,
  subject_entity_type TEXT,
  subject_entity_name TEXT,
  status TEXT DEFAULT 'candidate',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(domain,normalized_claim)
);
CREATE TABLE IF NOT EXISTS claim_evidence_link(
  link_id TEXT PRIMARY KEY,
  verification_claim_id TEXT NOT NULL REFERENCES verification_claim(verification_claim_id),
  evidence_claim_id TEXT NOT NULL REFERENCES claim(claim_id),
  stance TEXT NOT NULL,
  stance_confidence REAL,
  relevance REAL,
  authority_weight REAL,
  independence_weight REAL DEFAULT 1.0,
  recency_weight REAL DEFAULT 1.0,
  evidence_quality REAL DEFAULT 0.5,
  weighted_score REAL,
  cluster_id TEXT,
  method TEXT,
  created_at TEXT NOT NULL,
  UNIQUE(verification_claim_id,evidence_claim_id)
);
CREATE TABLE IF NOT EXISTS evidence_cluster(
  cluster_id TEXT PRIMARY KEY,
  verification_claim_id TEXT NOT NULL REFERENCES verification_claim(verification_claim_id),
  fingerprint TEXT NOT NULL,
  representative_claim_id TEXT,
  member_count INTEGER DEFAULT 1,
  independent_source_count INTEGER DEFAULT 1,
  created_at TEXT NOT NULL,
  UNIQUE(verification_claim_id,fingerprint)
);
CREATE TABLE IF NOT EXISTS source_assessment(
  assessment_id TEXT PRIMARY KEY,
  source_type TEXT NOT NULL,
  claim_type TEXT NOT NULL,
  authority_weight REAL NOT NULL,
  rationale TEXT,
  UNIQUE(source_type,claim_type)
);
CREATE INDEX IF NOT EXISTS idx_verification_claim_norm ON verification_claim(domain,normalized_claim);
CREATE INDEX IF NOT EXISTS idx_claim_evidence_stance ON claim_evidence_link(verification_claim_id,stance);

CREATE TABLE IF NOT EXISTS evidence_search_run(
  search_run_id TEXT PRIMARY KEY,
  verification_claim_id TEXT,
  claim_text TEXT NOT NULL,
  claim_type TEXT,
  query_plan_json TEXT NOT NULL,
  candidate_count INTEGER DEFAULT 0,
  bias_guard_pass INTEGER DEFAULT 0,
  diagnostics_json TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence_candidate_url(
  candidate_id TEXT PRIMARY KEY,
  search_run_id TEXT NOT NULL REFERENCES evidence_search_run(search_run_id),
  url TEXT NOT NULL,
  title TEXT,
  snippet TEXT,
  source_family TEXT,
  found_by_stances_json TEXT,
  found_by_queries_json TEXT,
  acquisition_status TEXT DEFAULT 'discovered',
  UNIQUE(search_run_id,url)
);

CREATE TABLE IF NOT EXISTS acquisition_job(
  acquisition_job_id TEXT PRIMARY KEY,
  profile_id TEXT NOT NULL,
  domain TEXT NOT NULL,
  purpose TEXT NOT NULL,
  source_url TEXT,
  source_type TEXT,
  status TEXT DEFAULT 'planned',
  discovered_from TEXT,
  metadata_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS acquired_document(
  acquired_document_id TEXT PRIMARY KEY,
  acquisition_job_id TEXT,
  source_url TEXT NOT NULL,
  canonical_url TEXT,
  title TEXT,
  source_type TEXT,
  domain TEXT,
  purpose TEXT,
  raw_text TEXT,
  content_hash TEXT,
  fetched_at TEXT NOT NULL,
  http_status INTEGER,
  parser_method TEXT,
  metadata_json TEXT
);
CREATE TABLE IF NOT EXISTS evidence_passage(
  passage_id TEXT PRIMARY KEY,
  acquired_document_id TEXT NOT NULL REFERENCES acquired_document(acquired_document_id),
  verification_claim_id TEXT,
  passage_index INTEGER,
  passage_text TEXT NOT NULL,
  relevance REAL,
  stance TEXT,
  stance_confidence REAL,
  method TEXT,
  char_start INTEGER,
  char_end INTEGER,
  UNIQUE(acquired_document_id,verification_claim_id,passage_index)
);
CREATE INDEX IF NOT EXISTS idx_acquisition_job_purpose ON acquisition_job(domain,purpose,status);
CREATE INDEX IF NOT EXISTS idx_acquired_document_url ON acquired_document(source_url,fetched_at);
CREATE INDEX IF NOT EXISTS idx_evidence_passage_claim ON evidence_passage(verification_claim_id,stance);
