

create extension if not exists "pgcrypto";

create table if not exists subscribers (
  id uuid primary key default gen_random_uuid(),
  endpoint text unique not null,
  p256dh text not null,
  auth text not null,
  created_at timestamptz not null default now()
);


create table if not exists listings (
  id uuid primary key default gen_random_uuid(),
  url text unique not null,
  company text not null,
  created_at timestamptz not null default now()
);

create index if not exists listings_url_idx on listings (url);


alter table subscribers enable row level security;
alter table listings enable row level security;
