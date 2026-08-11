-- AU Deal Hunter Phase 5 database / admin schema
-- Run in Supabase SQL Editor once.

create table if not exists public.admin_users (
  user_id uuid primary key references auth.users(id) on delete cascade,
  username text unique not null,
  created_at timestamptz not null default now()
);

create table if not exists public.app_settings (
  key text primary key,
  value jsonb not null,
  updated_at timestamptz not null default now()
);

create table if not exists public.source_controls (
  source_key text primary key,
  label text not null,
  enabled boolean not null default true,
  updated_at timestamptz not null default now()
);

create table if not exists public.watchlist (
  id bigint generated always as identity primary key,
  query text not null,
  max_price_aud numeric,
  min_discount_percent numeric default 0,
  enabled boolean not null default true,
  created_at timestamptz not null default now()
);

create table if not exists public.blocked_deals (
  id bigint generated always as identity primary key,
  pattern text not null,
  reason text,
  created_at timestamptz not null default now()
);

insert into public.app_settings(key,value) values
 ('good_deal_score_threshold','75'::jsonb),
 ('discord_price_drop_percent','3'::jsonb),
 ('discord_score_improvement','8'::jsonb),
 ('scan_interval_hours','6'::jsonb),
 ('market','"AU"'::jsonb),
 ('currency','"AUD"'::jsonb)
on conflict (key) do nothing;

insert into public.source_controls(source_key,label,enabled) values
 ('ozbargain','OzBargain',true),('ebay_au','eBay AU',true),('amazon_au','Amazon AU',true),
 ('mwave','Mwave',true),('scorptec','Scorptec',true),('centrecom','Centre Com',true),('umart','Umart',true)
on conflict (source_key) do nothing;

alter table public.admin_users enable row level security;
alter table public.app_settings enable row level security;
alter table public.source_controls enable row level security;
alter table public.watchlist enable row level security;
alter table public.blocked_deals enable row level security;

create or replace function public.is_deal_admin()
returns boolean language sql stable security definer set search_path=public as $$
  select exists(select 1 from public.admin_users a where a.user_id=auth.uid());
$$;
revoke all on function public.is_deal_admin() from public;
grant execute on function public.is_deal_admin() to authenticated;

-- Only authenticated users explicitly listed in admin_users can read/write admin tables.
do $$ begin
  create policy "admins manage settings" on public.app_settings for all to authenticated using (public.is_deal_admin()) with check (public.is_deal_admin());
exception when duplicate_object then null; end $$;
do $$ begin
  create policy "admins manage sources" on public.source_controls for all to authenticated using (public.is_deal_admin()) with check (public.is_deal_admin());
exception when duplicate_object then null; end $$;
do $$ begin
  create policy "admins manage watchlist" on public.watchlist for all to authenticated using (public.is_deal_admin()) with check (public.is_deal_admin());
exception when duplicate_object then null; end $$;
do $$ begin
  create policy "admins manage blocks" on public.blocked_deals for all to authenticated using (public.is_deal_admin()) with check (public.is_deal_admin());
exception when duplicate_object then null; end $$;
do $$ begin
  create policy "admin can read self" on public.admin_users for select to authenticated using (user_id=auth.uid());
exception when duplicate_object then null; end $$;
