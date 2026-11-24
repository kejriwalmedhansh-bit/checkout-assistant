-- Dealo's own buyer list (Supabase, Mumbai). Run once in Supabase → SQL Editor.
-- Only Dealo's server touches these tables, using the secret key. Row level
-- security is on with no policies, so the public key can read nothing.

create table if not exists public.buyers (
  id uuid primary key default gen_random_uuid(),
  firebase_uid text unique not null,
  phone text not null,
  name text,
  email text,
  marketing_optin boolean not null default false,
  marketing_optin_at timestamptz,
  created_at timestamptz not null default now(),
  last_login_at timestamptz not null default now()
);

-- One row per Hubble order. Voucher codes and PINs are never stored here.
create table if not exists public.purchases (
  id uuid primary key default gen_random_uuid(),
  hubble_ref text unique not null,
  firebase_uid text references public.buyers (firebase_uid),
  brand text,
  amount numeric,
  discount numeric,
  status text,
  environment text not null default 'staging',
  created_at timestamptz not null default now()
);

alter table public.buyers enable row level security;
alter table public.purchases enable row level security;

-- 24 Nov 2026: where each buyer and each purchase came from.
-- first_*: the visit in which we first saw the buyer, written once.
-- heard_from: their own one-tap answer after buying (google | chatgpt |
-- instagram | friend | other). Buyers from before this date get
-- first_source_at = created_at with no source, so a later visit is not
-- mistaken for their first.
alter table public.buyers
  add column if not exists first_utm_source text,
  add column if not exists first_utm_medium text,
  add column if not exists first_utm_campaign text,
  add column if not exists first_referrer_domain text,
  add column if not exists first_landing_page text,
  add column if not exists first_source_at timestamptz,
  add column if not exists heard_from text,
  add column if not exists heard_from_at timestamptz;
update public.buyers set first_source_at = created_at where first_source_at is null;

alter table public.purchases
  add column if not exists utm_source text,
  add column if not exists utm_medium text,
  add column if not exists utm_campaign text,
  add column if not exists referrer_domain text,
  add column if not exists landing_page text;
