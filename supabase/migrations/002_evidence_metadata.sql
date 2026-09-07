alter table posts add column if not exists evidence_verified boolean not null default false;
alter table posts add column if not exists evidence_reason text;