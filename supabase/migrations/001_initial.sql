create extension if not exists pgcrypto;

create table if not exists posts (
  id uuid primary key default gen_random_uuid(), created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  news_title text not null, news_summary text, news_url text not null, news_source text, news_published_at timestamptz,
  ai_score integer, credibility_score integer, usefulness_score integer, novelty_score integer,
  headline text, short_explanation text, why_it_matters text, key_takeaway text, linkedin_caption text, instagram_caption text,
  hashtags text[], image_storage_path text, image_public_url text, status text not null, approval_status text not null default 'PENDING',
  linkedin_status text, linkedin_post_id text, linkedin_error text, instagram_status text, instagram_post_id text, instagram_error text,
  published_at timestamptz, run_id uuid not null unique, error_message text
);
create unique index if not exists posts_news_url_key on posts(news_url);
create index if not exists posts_created_at_idx on posts(created_at);
create index if not exists posts_status_idx on posts(status);
create index if not exists posts_published_at_idx on posts(published_at);

insert into storage.buckets (id, name, public) values ('social-posts', 'social-posts', true) on conflict (id) do nothing;
