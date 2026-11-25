-- purplhrtz: shared guestbook notes + Stripe order fulfilment.
-- Tables are not readable or writable by anon/authenticated roles directly.
-- The Next.js server talks to them only through the SECURITY DEFINER functions
-- below, which require a server-only token stored in private.settings.

create schema if not exists private;
revoke all on schema private from public, anon, authenticated;

create table if not exists private.settings (
  key text primary key,
  value text not null
);
revoke all on private.settings from public, anon, authenticated;

-- ---------------------------------------------------------------- notes
create table if not exists public.guestbook_notes (
  id uuid primary key default gen_random_uuid(),
  display_name text check (display_name is null or char_length(display_name) between 1 and 32),
  body text not null check (char_length(body) between 1 and 280),
  ip_hash text not null check (ip_hash ~ '^[0-9a-f]{64}$'),
  hidden boolean not null default false,
  created_at timestamptz not null default now()
);
alter table public.guestbook_notes enable row level security;
revoke all on public.guestbook_notes from public, anon, authenticated;
create index if not exists guestbook_notes_ip_recent on public.guestbook_notes (ip_hash, created_at desc);
create index if not exists guestbook_notes_visible on public.guestbook_notes (created_at desc) where not hidden;

create or replace function private.check_server_token(p_token text)
returns void language plpgsql stable security definer set search_path = '' as $$
begin
  -- Only SHA-256 hashes of server tokens are stored (one row per environment:
  -- keys 'server_rpc_token_sha256', 'server_rpc_token_sha256:preview', ...).
  if p_token is null or not exists (
    select 1 from private.settings s
    where s.key like 'server_rpc_token_sha256%'
      and s.value = encode(sha256(convert_to(p_token, 'UTF8')), 'hex')
  ) then
    raise exception 'unauthorized' using errcode = '28000';
  end if;
end $$;
revoke all on function private.check_server_token(text) from public, anon, authenticated;

create or replace function public.list_guestbook_notes(p_limit int default 60)
returns table (id uuid, display_name text, body text, created_at timestamptz)
language sql stable security definer set search_path = '' as $$
  select n.id, n.display_name, n.body, n.created_at
  from public.guestbook_notes n
  where not n.hidden
  order by n.created_at desc
  limit least(greatest(coalesce(p_limit, 60), 1), 100);
$$;
revoke all on function public.list_guestbook_notes(int) from public;
grant execute on function public.list_guestbook_notes(int) to anon, authenticated;

create or replace function public.post_guestbook_note(
  p_token text, p_ip_hash text, p_display_name text, p_body text
)
returns table (id uuid, display_name text, body text, created_at timestamptz)
language plpgsql volatile security definer set search_path = '' as $$
declare
  v_name text := nullif(btrim(coalesce(p_display_name, '')), '');
  v_body text := btrim(coalesce(p_body, ''));
  v_recent int;
  v_global int;
begin
  perform private.check_server_token(p_token);
  if char_length(v_body) < 1 or char_length(v_body) > 280 then
    raise exception 'invalid_body' using errcode = '22023';
  end if;
  if v_name is not null and char_length(v_name) > 32 then
    raise exception 'invalid_name' using errcode = '22023';
  end if;
  select count(*) into v_recent from public.guestbook_notes g
    where g.ip_hash = p_ip_hash and g.created_at > now() - interval '10 minutes';
  select count(*) into v_global from public.guestbook_notes g
    where g.created_at > now() - interval '1 minute';
  if v_recent >= 3 or v_global >= 30 then
    raise exception 'rate_limited' using errcode = 'P0001';
  end if;
  return query
    insert into public.guestbook_notes as g (display_name, body, ip_hash)
    values (v_name, v_body, p_ip_hash)
    returning g.id, g.display_name, g.body, g.created_at;
end $$;
revoke all on function public.post_guestbook_note(text, text, text, text) from public;
grant execute on function public.post_guestbook_note(text, text, text, text) to anon, authenticated;

-- ---------------------------------------------------------------- orders
create table if not exists public.stripe_events (
  event_id text primary key,
  type text not null,
  received_at timestamptz not null default now()
);
alter table public.stripe_events enable row level security;
revoke all on public.stripe_events from public, anon, authenticated;

create table if not exists public.orders (
  checkout_session_id text primary key,
  product_ids text[] not null,
  amount_total integer,
  currency text,
  customer_email text,
  fulfilled_at timestamptz not null default now()
);
alter table public.orders enable row level security;
revoke all on public.orders from public, anon, authenticated;

-- Returns true only the first time a given Stripe event is seen, so repeat
-- webhook deliveries are acknowledged without granting anything twice.
create or replace function public.record_paid_order(
  p_token text, p_event_id text, p_event_type text, p_session_id text,
  p_product_ids text[], p_amount_total int, p_currency text, p_email text
)
returns boolean
language plpgsql volatile security definer set search_path = '' as $$
begin
  perform private.check_server_token(p_token);
  insert into public.stripe_events (event_id, type) values (p_event_id, p_event_type)
    on conflict (event_id) do nothing;
  if not found then
    return false;
  end if;
  insert into public.orders (checkout_session_id, product_ids, amount_total, currency, customer_email)
    values (p_session_id, p_product_ids, p_amount_total, p_currency, p_email)
    on conflict (checkout_session_id) do nothing;
  return found;
end $$;
revoke all on function public.record_paid_order(text, text, text, text, text[], int, text, text) from public;
grant execute on function public.record_paid_order(text, text, text, text, text[], int, text, text) to anon, authenticated;

create or replace function public.get_order(p_token text, p_session_id text)
returns table (checkout_session_id text, product_ids text[], fulfilled_at timestamptz)
language plpgsql stable security definer set search_path = '' as $$
begin
  perform private.check_server_token(p_token);
  return query select o.checkout_session_id, o.product_ids, o.fulfilled_at
    from public.orders o where o.checkout_session_id = p_session_id;
end $$;
revoke all on function public.get_order(text, text) from public;
grant execute on function public.get_order(text, text) to anon, authenticated;

-- After applying, register the server token hash (never the token itself):
--   insert into private.settings (key, value)
--   values ('server_rpc_token_sha256', '<sha256 hex of SUPABASE_SERVER_RPC_TOKEN>')
-- Use a distinct key suffix per environment, e.g. 'server_rpc_token_sha256:preview'.
--   on conflict (key) do update set value = excluded.value;
