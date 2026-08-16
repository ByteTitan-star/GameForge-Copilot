--
-- PostgreSQL database dump
--

\restrict PSTpav61TN6IPIjgrCxVP3dBTElOa9BycLBz2qJlpL5KycQNpWmYHihBxpYF5Qw

-- Dumped from database version 16.14 (Debian 16.14-1.pgdg13+1)
-- Dumped by pg_dump version 16.14 (Debian 16.14-1.pgdg13+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: gameforge
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


ALTER TABLE public.alembic_version OWNER TO gameforge;

--
-- Name: audit_logs; Type: TABLE; Schema: public; Owner: gameforge
--

CREATE TABLE public.audit_logs (
    id uuid NOT NULL,
    actor_id uuid NOT NULL,
    action character varying(32) NOT NULL,
    target character varying(255),
    detail json,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.audit_logs OWNER TO gameforge;

--
-- Name: email_verification; Type: TABLE; Schema: public; Owner: gameforge
--

CREATE TABLE public.email_verification (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    token_hash character varying(255) NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    used_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.email_verification OWNER TO gameforge;

--
-- Name: game_reactions; Type: TABLE; Schema: public; Owner: gameforge
--

CREATE TABLE public.game_reactions (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    game_id uuid NOT NULL,
    type character varying(16) NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.game_reactions OWNER TO gameforge;

--
-- Name: game_versions; Type: TABLE; Schema: public; Owner: gameforge
--

CREATE TABLE public.game_versions (
    id uuid NOT NULL,
    game_id uuid NOT NULL,
    version integer NOT NULL,
    artifact_path character varying(512) NOT NULL,
    design_doc json,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.game_versions OWNER TO gameforge;

--
-- Name: games; Type: TABLE; Schema: public; Owner: gameforge
--

CREATE TABLE public.games (
    id uuid NOT NULL,
    owner_id uuid NOT NULL,
    slug character varying(128),
    title character varying(255) NOT NULL,
    status character varying(24) DEFAULT 'draft'::character varying NOT NULL,
    current_version integer DEFAULT 0 NOT NULL,
    requirement text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    published_at timestamp with time zone,
    play_count integer DEFAULT 0 NOT NULL,
    scheduled_take_down_at timestamp with time zone,
    scheduled_publish_at timestamp with time zone,
    featured_rank integer
);


ALTER TABLE public.games OWNER TO gameforge;

--
-- Name: generation_runs; Type: TABLE; Schema: public; Owner: gameforge
--

CREATE TABLE public.generation_runs (
    id uuid NOT NULL,
    game_id uuid NOT NULL,
    user_id uuid NOT NULL,
    llm_config_id uuid,
    requirement text NOT NULL,
    status character varying(16) DEFAULT 'running'::character varying NOT NULL,
    phase character varying(16) DEFAULT 'plan'::character varying,
    checkpoint_ref character varying(255),
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    ended_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    entry_phase character varying(8) DEFAULT 'plan'::character varying NOT NULL
);


ALTER TABLE public.generation_runs OWNER TO gameforge;

--
-- Name: notifications; Type: TABLE; Schema: public; Owner: gameforge
--

CREATE TABLE public.notifications (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    kind character varying(32) NOT NULL,
    title character varying(255) NOT NULL,
    body text NOT NULL,
    read boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.notifications OWNER TO gameforge;

--
-- Name: oauth_accounts; Type: TABLE; Schema: public; Owner: gameforge
--

CREATE TABLE public.oauth_accounts (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    provider character varying(32) NOT NULL,
    provider_sub character varying(255) NOT NULL,
    email character varying(255),
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.oauth_accounts OWNER TO gameforge;

--
-- Name: password_reset_tokens; Type: TABLE; Schema: public; Owner: gameforge
--

CREATE TABLE public.password_reset_tokens (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    token_hash character varying(255) NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    used_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.password_reset_tokens OWNER TO gameforge;

--
-- Name: publish_requests; Type: TABLE; Schema: public; Owner: gameforge
--

CREATE TABLE public.publish_requests (
    id uuid NOT NULL,
    game_id uuid NOT NULL,
    version integer NOT NULL,
    status character varying(16) DEFAULT 'submitted'::character varying NOT NULL,
    note text,
    reviewer_id uuid,
    reject_reason text,
    reviewed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.publish_requests OWNER TO gameforge;

--
-- Name: system_settings; Type: TABLE; Schema: public; Owner: gameforge
--

CREATE TABLE public.system_settings (
    key character varying(64) NOT NULL,
    value json NOT NULL,
    updated_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.system_settings OWNER TO gameforge;

--
-- Name: user_llm_config; Type: TABLE; Schema: public; Owner: gameforge
--

CREATE TABLE public.user_llm_config (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    provider character varying(16) NOT NULL,
    model character varying(128) NOT NULL,
    apikey_enc text NOT NULL,
    is_default boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    base_url character varying(512)
);


ALTER TABLE public.user_llm_config OWNER TO gameforge;

--
-- Name: users; Type: TABLE; Schema: public; Owner: gameforge
--

CREATE TABLE public.users (
    id uuid NOT NULL,
    email character varying(255) NOT NULL,
    password_hash character varying(255) NOT NULL,
    role character varying(16) DEFAULT 'user'::character varying NOT NULL,
    email_verified boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    disabled boolean DEFAULT false NOT NULL,
    handle character varying(32),
    display_name character varying(64),
    profile_public boolean DEFAULT true NOT NULL
);


ALTER TABLE public.users OWNER TO gameforge;

--
-- Data for Name: alembic_version; Type: TABLE DATA; Schema: public; Owner: gameforge
--

COPY public.alembic_version (version_num) FROM stdin;
0011_batch_bc_social
\.


--
-- Data for Name: audit_logs; Type: TABLE DATA; Schema: public; Owner: gameforge
--

COPY public.audit_logs (id, actor_id, action, target, detail, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: email_verification; Type: TABLE DATA; Schema: public; Owner: gameforge
--

COPY public.email_verification (id, user_id, token_hash, expires_at, used_at, created_at, updated_at) FROM stdin;
455b59c6-91fc-4a0c-936b-6d1d7861352d	d7d318ae-9fca-4c16-9bc7-2870466d14b3	d7eb5dacbedbcf9549c0214919394f793b4ee67013f4cba419f71af3761ec585	2026-08-09 06:51:05.283312+00	\N	2026-08-09 06:41:05.703012+00	2026-08-09 06:41:05.703012+00
5888a5cf-6ec8-4447-b213-ca59b384525f	bf4e3a49-0307-43f6-befe-1053b133076b	6e7ed1f8858f7156bfa3e8fb5c0b59e6dee5478c9b84b2e91b489abd7f46e393	2026-08-10 13:21:46.440554+00	2026-08-10 13:12:14.372898+00	2026-08-10 13:11:46.447143+00	2026-08-10 13:12:14.376749+00
\.


--
-- Data for Name: game_reactions; Type: TABLE DATA; Schema: public; Owner: gameforge
--

COPY public.game_reactions (id, user_id, game_id, type, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: game_versions; Type: TABLE DATA; Schema: public; Owner: gameforge
--

COPY public.game_versions (id, game_id, version, artifact_path, design_doc, created_at, updated_at) FROM stdin;
2b63216e-0e40-4ac8-a0d1-c110b9f3be82	00000000-0000-4000-8000-0000000000a1	1	00000000-0000-4000-8000-0000000000a1/1/index.html	{"title": "\\u9713\\u8679\\u8d2a\\u5403\\u86c7", "gameplay": "\\u9713\\u8679\\u98ce\\u683c\\u8d2a\\u5403\\u86c7\\uff1a\\u65b9\\u5411\\u952e\\u63a7\\u5236\\uff0c\\u5403\\u98df\\u7269\\u53d8\\u957f\\uff0c\\u8ba1\\u5206\\uff0c\\u649e\\u5899 game over\\u3002", "controls": "\\u89c1\\u6e38\\u620f\\u5185\\u8bf4\\u660e", "levels": []}	2026-08-09 15:19:38.629359+00	2026-08-09 15:19:38.629359+00
b1469466-f7bb-41ad-8e58-6b550e3aabf3	00000000-0000-4000-8000-0000000000a2	1	00000000-0000-4000-8000-0000000000a2/1/index.html	{"title": "\\u50cf\\u7d20\\u8dd1\\u9177", "gameplay": "\\u50cf\\u7d20\\u98ce\\u6a2a\\u7248\\u8dd1\\u9177\\uff1a\\u7a7a\\u683c\\u8df3\\u8dc3\\uff0c\\u8eb2\\u907f\\u969c\\u788d\\uff0c\\u8ddd\\u79bb\\u8ba1\\u5206\\u3002", "controls": "\\u89c1\\u6e38\\u620f\\u5185\\u8bf4\\u660e", "levels": []}	2026-08-09 15:19:38.64381+00	2026-08-09 15:19:38.64381+00
bd78d12e-7ccb-4371-b073-990cf158a69d	00000000-0000-4000-8000-0000000000a3	1	00000000-0000-4000-8000-0000000000a3/1/index.html	{"title": "\\u5854\\u9632\\u96cf\\u5f62", "gameplay": "\\u6781\\u7b80\\u5854\\u9632\\uff1a\\u56fa\\u5b9a\\u8def\\u5f84\\uff0c\\u70b9\\u51fb\\u653e\\u5854\\uff0c\\u62e6\\u622a\\u654c\\u4eba\\u6ce2\\u6b21\\u3002", "controls": "\\u89c1\\u6e38\\u620f\\u5185\\u8bf4\\u660e", "levels": []}	2026-08-09 15:19:38.654248+00	2026-08-09 15:19:38.654248+00
\.


--
-- Data for Name: games; Type: TABLE DATA; Schema: public; Owner: gameforge
--

COPY public.games (id, owner_id, slug, title, status, current_version, requirement, created_at, updated_at, published_at, play_count, scheduled_take_down_at, scheduled_publish_at, featured_rank) FROM stdin;
00000000-0000-4000-8000-0000000000a1	00000000-0000-4000-8000-000000000001	official-neon-snake	霓虹贪吃蛇	published	1	霓虹风格贪吃蛇：方向键控制，吃食物变长，计分，撞墙 game over。	2026-08-09 15:19:38.629359+00	2026-08-10 06:48:59.196682+00	2026-08-09 15:19:36.890852+00	37	\N	\N	\N
00000000-0000-4000-8000-0000000000a3	00000000-0000-4000-8000-000000000001	official-tower-stub	塔防雏形	published	1	极简塔防：固定路径，点击放塔，拦截敌人波次。	2026-08-09 15:19:38.654248+00	2026-08-10 06:49:05.759922+00	2026-08-09 15:19:36.890852+00	7	\N	\N	\N
00000000-0000-4000-8000-0000000000a2	00000000-0000-4000-8000-000000000001	official-pixel-runner	像素跑酷	published	1	像素风横版跑酷：空格跳跃，躲避障碍，距离计分。	2026-08-09 15:19:38.64381+00	2026-08-10 06:56:21.346959+00	2026-08-09 15:19:36.890852+00	4	\N	\N	\N
3ce01cd5-dc99-448e-9c0a-c60b216f6310	bf4e3a49-0307-43f6-befe-1053b133076b	\N	做一个经典贪吃蛇：方向键移动，吃食物变长，撞墙或	draft	0	做一个经典贪吃蛇：方向键移动，吃食物变长，撞墙或自身失败，显示分数。	2026-08-10 13:12:32.013429+00	2026-08-10 13:12:32.013429+00	\N	0	\N	\N	\N
\.


--
-- Data for Name: generation_runs; Type: TABLE DATA; Schema: public; Owner: gameforge
--

COPY public.generation_runs (id, game_id, user_id, llm_config_id, requirement, status, phase, checkpoint_ref, started_at, ended_at, created_at, updated_at, entry_phase) FROM stdin;
42ea5225-486c-44ca-8be2-745fa59754f3	3ce01cd5-dc99-448e-9c0a-c60b216f6310	bf4e3a49-0307-43f6-befe-1053b133076b	\N	做一个经典贪吃蛇：方向键移动，吃食物变长，撞墙或自身失败，显示分数。	failed	plan	\N	2026-08-10 13:12:32.06238+00	2026-08-10 13:12:32.214199+00	2026-08-10 13:12:32.043947+00	2026-08-10 13:12:32.13089+00	plan
133fff35-4bb2-45e7-9d52-e49728a12a18	3ce01cd5-dc99-448e-9c0a-c60b216f6310	bf4e3a49-0307-43f6-befe-1053b133076b	\N	设计一款竖版复古街机射击游戏。\n\n核心目标：在无尽敌波中存活并刷新最高分。\n\n操作：方向键/WASD 移动飞船，空格连射，Shift 短距冲刺躲弹幕。\n\n必备功能：\n- 敌机按波次生成，弹幕密度与移速随波次递增\n- 击毁敌机随机掉落道具：火力升级、护盾、清屏炸弹\n- 连击计时加分；实时显示分数、波次、剩余生命\n- 被击中扣生命，生命归零游戏结束，展示本局得分并支持一键重开\n\n视觉：8-bit 像素风，深色星空背景，霓虹弹道与爆炸粒子。\n\n请实现可立刻试玩的完整单局循环（开始 → 战斗 → 结算 → 重开）。	failed	plan	\N	2026-08-10 13:12:49.039741+00	2026-08-10 13:12:49.158146+00	2026-08-10 13:12:49.039298+00	2026-08-10 13:12:49.15+00	plan
\.


--
-- Data for Name: notifications; Type: TABLE DATA; Schema: public; Owner: gameforge
--

COPY public.notifications (id, user_id, kind, title, body, read, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: oauth_accounts; Type: TABLE DATA; Schema: public; Owner: gameforge
--

COPY public.oauth_accounts (id, user_id, provider, provider_sub, email, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: password_reset_tokens; Type: TABLE DATA; Schema: public; Owner: gameforge
--

COPY public.password_reset_tokens (id, user_id, token_hash, expires_at, used_at, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: publish_requests; Type: TABLE DATA; Schema: public; Owner: gameforge
--

COPY public.publish_requests (id, game_id, version, status, note, reviewer_id, reject_reason, reviewed_at, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: system_settings; Type: TABLE DATA; Schema: public; Owner: gameforge
--

COPY public.system_settings (key, value, updated_by, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: user_llm_config; Type: TABLE DATA; Schema: public; Owner: gameforge
--

COPY public.user_llm_config (id, user_id, provider, model, apikey_enc, is_default, created_at, updated_at, base_url) FROM stdin;
3a5c68f5-e388-4822-ba52-24e41ed2b774	d7d318ae-9fca-4c16-9bc7-2870466d14b3	openai	qwen3.8-max	gAAAAABqeDJyFwWqg8fHtl1YZz-jDk9AD_3dZMMB49IpQ2dSoc48W23xuO4Fq14_nNToXiffdiMaqxo8jvuzymM4fdASZrNaTAIhSRBsYSASdaMwtQBKkTnq-Y6D8SkKaEQxSR2Pc4ob	t	2026-08-09 07:55:29.926406+00	2026-08-09 07:55:29.926406+00	https://dashscope.aliyuncs.com/compatible-mode/v1
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: gameforge
--

COPY public.users (id, email, password_hash, role, email_verified, created_at, updated_at, disabled, handle, display_name, profile_public) FROM stdin;
00000000-0000-4000-8000-000000000001	official@gameforge.internal	$argon2id$v=19$m=65536,t=3,p=4$1VqtjuxjPZ82IT9m2FHmyA$mSjJmec2NDbzAUnskWDUn+jksQsxnrFg0KDQLpPRIHI	user	t	2026-08-09 06:32:45.676468+00	2026-08-09 06:32:45.676468+00	f	\N	\N	t
d7d318ae-9fca-4c16-9bc7-2870466d14b3	wxcurry@163.com	$argon2id$v=19$m=65536,t=3,p=4$iq2JCSTXHVnjSISOZGGP2A$nMJFoHk2Gi5l7HVDVzU4OATUytplqgyYqnkz3lW8ync	user	f	2026-08-09 06:41:05.69528+00	2026-08-09 06:41:05.69528+00	f	\N	\N	t
00000000-0000-4000-8000-000000000002	demo@gameforge.dev	$argon2id$v=19$m=65536,t=3,p=4$4CtdSO7SGugoTVxOT8CSsA$D+XIHgyIBlAgX5YvVcegaeGRR2vVkoObsQ6b9HAIeXs	user	t	2026-08-09 06:42:17.581663+00	2026-08-09 06:42:17.581663+00	f	\N	\N	t
bf4e3a49-0307-43f6-befe-1053b133076b	2307067371@qq.com	$argon2id$v=19$m=65536,t=3,p=4$yeCKWAF9R/JlECy7Ietc1Q$n8PxRmkawAd+gvKv3zu3OTZST65phdJF1qvfqRtoA4Q	user	t	2026-08-10 13:11:46.433699+00	2026-08-10 13:12:14.376749+00	f	\N	\N	t
\.


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: gameforge
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: audit_logs audit_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: gameforge
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_pkey PRIMARY KEY (id);


--
-- Name: email_verification email_verification_pkey; Type: CONSTRAINT; Schema: public; Owner: gameforge
--

ALTER TABLE ONLY public.email_verification
    ADD CONSTRAINT email_verification_pkey PRIMARY KEY (id);


--
-- Name: email_verification email_verification_token_hash_key; Type: CONSTRAINT; Schema: public; Owner: gameforge
--

ALTER TABLE ONLY public.email_verification
    ADD CONSTRAINT email_verification_token_hash_key UNIQUE (token_hash);


--
-- Name: game_reactions game_reactions_pkey; Type: CONSTRAINT; Schema: public; Owner: gameforge
--

ALTER TABLE ONLY public.game_reactions
    ADD CONSTRAINT game_reactions_pkey PRIMARY KEY (id);


--
-- Name: game_versions game_versions_pkey; Type: CONSTRAINT; Schema: public; Owner: gameforge
--

ALTER TABLE ONLY public.game_versions
    ADD CONSTRAINT game_versions_pkey PRIMARY KEY (id);


--
-- Name: games games_pkey; Type: CONSTRAINT; Schema: public; Owner: gameforge
--

ALTER TABLE ONLY public.games
    ADD CONSTRAINT games_pkey PRIMARY KEY (id);


--
-- Name: generation_runs generation_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: gameforge
--

ALTER TABLE ONLY public.generation_runs
    ADD CONSTRAINT generation_runs_pkey PRIMARY KEY (id);


--
-- Name: notifications notifications_pkey; Type: CONSTRAINT; Schema: public; Owner: gameforge
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_pkey PRIMARY KEY (id);


--
-- Name: oauth_accounts oauth_accounts_pkey; Type: CONSTRAINT; Schema: public; Owner: gameforge
--

ALTER TABLE ONLY public.oauth_accounts
    ADD CONSTRAINT oauth_accounts_pkey PRIMARY KEY (id);


--
-- Name: password_reset_tokens password_reset_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: gameforge
--

ALTER TABLE ONLY public.password_reset_tokens
    ADD CONSTRAINT password_reset_tokens_pkey PRIMARY KEY (id);


--
-- Name: password_reset_tokens password_reset_tokens_token_hash_key; Type: CONSTRAINT; Schema: public; Owner: gameforge
--

ALTER TABLE ONLY public.password_reset_tokens
    ADD CONSTRAINT password_reset_tokens_token_hash_key UNIQUE (token_hash);


--
-- Name: publish_requests publish_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: gameforge
--

ALTER TABLE ONLY public.publish_requests
    ADD CONSTRAINT publish_requests_pkey PRIMARY KEY (id);


--
-- Name: system_settings system_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: gameforge
--

ALTER TABLE ONLY public.system_settings
    ADD CONSTRAINT system_settings_pkey PRIMARY KEY (key);


--
-- Name: game_reactions uq_game_reaction; Type: CONSTRAINT; Schema: public; Owner: gameforge
--

ALTER TABLE ONLY public.game_reactions
    ADD CONSTRAINT uq_game_reaction UNIQUE (user_id, game_id, type);


--
-- Name: oauth_accounts uq_oauth_provider_sub; Type: CONSTRAINT; Schema: public; Owner: gameforge
--

ALTER TABLE ONLY public.oauth_accounts
    ADD CONSTRAINT uq_oauth_provider_sub UNIQUE (provider, provider_sub);


--
-- Name: user_llm_config user_llm_config_pkey; Type: CONSTRAINT; Schema: public; Owner: gameforge
--

ALTER TABLE ONLY public.user_llm_config
    ADD CONSTRAINT user_llm_config_pkey PRIMARY KEY (id);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: gameforge
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: gameforge
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: ix_audit_logs_actor_id; Type: INDEX; Schema: public; Owner: gameforge
--

CREATE INDEX ix_audit_logs_actor_id ON public.audit_logs USING btree (actor_id);


--
-- Name: ix_email_verification_token_hash; Type: INDEX; Schema: public; Owner: gameforge
--

CREATE UNIQUE INDEX ix_email_verification_token_hash ON public.email_verification USING btree (token_hash);


--
-- Name: ix_email_verification_user_id; Type: INDEX; Schema: public; Owner: gameforge
--

CREATE INDEX ix_email_verification_user_id ON public.email_verification USING btree (user_id);


--
-- Name: ix_game_reactions_game_id; Type: INDEX; Schema: public; Owner: gameforge
--

CREATE INDEX ix_game_reactions_game_id ON public.game_reactions USING btree (game_id);


--
-- Name: ix_game_reactions_user_id; Type: INDEX; Schema: public; Owner: gameforge
--

CREATE INDEX ix_game_reactions_user_id ON public.game_reactions USING btree (user_id);


--
-- Name: ix_game_versions_game_id; Type: INDEX; Schema: public; Owner: gameforge
--

CREATE INDEX ix_game_versions_game_id ON public.game_versions USING btree (game_id);


--
-- Name: ix_games_featured_rank; Type: INDEX; Schema: public; Owner: gameforge
--

CREATE INDEX ix_games_featured_rank ON public.games USING btree (featured_rank);


--
-- Name: ix_games_owner_id; Type: INDEX; Schema: public; Owner: gameforge
--

CREATE INDEX ix_games_owner_id ON public.games USING btree (owner_id);


--
-- Name: ix_generation_runs_game_id; Type: INDEX; Schema: public; Owner: gameforge
--

CREATE INDEX ix_generation_runs_game_id ON public.generation_runs USING btree (game_id);


--
-- Name: ix_generation_runs_user_id; Type: INDEX; Schema: public; Owner: gameforge
--

CREATE INDEX ix_generation_runs_user_id ON public.generation_runs USING btree (user_id);


--
-- Name: ix_notifications_user_id; Type: INDEX; Schema: public; Owner: gameforge
--

CREATE INDEX ix_notifications_user_id ON public.notifications USING btree (user_id);


--
-- Name: ix_oauth_accounts_user_id; Type: INDEX; Schema: public; Owner: gameforge
--

CREATE INDEX ix_oauth_accounts_user_id ON public.oauth_accounts USING btree (user_id);


--
-- Name: ix_password_reset_tokens_token_hash; Type: INDEX; Schema: public; Owner: gameforge
--

CREATE UNIQUE INDEX ix_password_reset_tokens_token_hash ON public.password_reset_tokens USING btree (token_hash);


--
-- Name: ix_password_reset_tokens_user_id; Type: INDEX; Schema: public; Owner: gameforge
--

CREATE INDEX ix_password_reset_tokens_user_id ON public.password_reset_tokens USING btree (user_id);


--
-- Name: ix_publish_requests_game_id; Type: INDEX; Schema: public; Owner: gameforge
--

CREATE INDEX ix_publish_requests_game_id ON public.publish_requests USING btree (game_id);


--
-- Name: ix_user_llm_config_user_id; Type: INDEX; Schema: public; Owner: gameforge
--

CREATE INDEX ix_user_llm_config_user_id ON public.user_llm_config USING btree (user_id);


--
-- Name: ix_users_email; Type: INDEX; Schema: public; Owner: gameforge
--

CREATE UNIQUE INDEX ix_users_email ON public.users USING btree (email);


--
-- Name: ix_users_handle; Type: INDEX; Schema: public; Owner: gameforge
--

CREATE UNIQUE INDEX ix_users_handle ON public.users USING btree (handle);


--
-- Name: ux_games_slug; Type: INDEX; Schema: public; Owner: gameforge
--

CREATE UNIQUE INDEX ux_games_slug ON public.games USING btree (slug);


--
-- Name: audit_logs audit_logs_actor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gameforge
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: email_verification email_verification_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gameforge
--

ALTER TABLE ONLY public.email_verification
    ADD CONSTRAINT email_verification_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: game_reactions game_reactions_game_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gameforge
--

ALTER TABLE ONLY public.game_reactions
    ADD CONSTRAINT game_reactions_game_id_fkey FOREIGN KEY (game_id) REFERENCES public.games(id) ON DELETE CASCADE;


--
-- Name: game_reactions game_reactions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gameforge
--

ALTER TABLE ONLY public.game_reactions
    ADD CONSTRAINT game_reactions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: game_versions game_versions_game_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gameforge
--

ALTER TABLE ONLY public.game_versions
    ADD CONSTRAINT game_versions_game_id_fkey FOREIGN KEY (game_id) REFERENCES public.games(id) ON DELETE CASCADE;


--
-- Name: games games_owner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gameforge
--

ALTER TABLE ONLY public.games
    ADD CONSTRAINT games_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: generation_runs generation_runs_game_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gameforge
--

ALTER TABLE ONLY public.generation_runs
    ADD CONSTRAINT generation_runs_game_id_fkey FOREIGN KEY (game_id) REFERENCES public.games(id) ON DELETE CASCADE;


--
-- Name: generation_runs generation_runs_llm_config_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gameforge
--

ALTER TABLE ONLY public.generation_runs
    ADD CONSTRAINT generation_runs_llm_config_id_fkey FOREIGN KEY (llm_config_id) REFERENCES public.user_llm_config(id) ON DELETE SET NULL;


--
-- Name: generation_runs generation_runs_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gameforge
--

ALTER TABLE ONLY public.generation_runs
    ADD CONSTRAINT generation_runs_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: notifications notifications_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gameforge
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: oauth_accounts oauth_accounts_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gameforge
--

ALTER TABLE ONLY public.oauth_accounts
    ADD CONSTRAINT oauth_accounts_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: password_reset_tokens password_reset_tokens_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gameforge
--

ALTER TABLE ONLY public.password_reset_tokens
    ADD CONSTRAINT password_reset_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: publish_requests publish_requests_game_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gameforge
--

ALTER TABLE ONLY public.publish_requests
    ADD CONSTRAINT publish_requests_game_id_fkey FOREIGN KEY (game_id) REFERENCES public.games(id) ON DELETE CASCADE;


--
-- Name: publish_requests publish_requests_reviewer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gameforge
--

ALTER TABLE ONLY public.publish_requests
    ADD CONSTRAINT publish_requests_reviewer_id_fkey FOREIGN KEY (reviewer_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: system_settings system_settings_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gameforge
--

ALTER TABLE ONLY public.system_settings
    ADD CONSTRAINT system_settings_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: user_llm_config user_llm_config_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gameforge
--

ALTER TABLE ONLY public.user_llm_config
    ADD CONSTRAINT user_llm_config_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict PSTpav61TN6IPIjgrCxVP3dBTElOa9BycLBz2qJlpL5KycQNpWmYHihBxpYF5Qw

