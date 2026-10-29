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
