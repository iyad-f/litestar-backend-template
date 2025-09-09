CREATE TABLE IF NOT EXISTS users (
    id BIGINT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    hashed_password TEXT NOT NULL,
    locked_notes_secret_hash TEXT NOT NULL,
    disabled BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
    -- TODO: Add a virtually generated deleted column when pg 18 releases.
);
-- An index on disabled, which is a boolean field makes sense here because
-- the distribution of disabled will be highly skewed towards "FALSE" (90-99%)
CREATE INDEX IF NOT EXISTS idx_users_disabled ON users(disabled);
CREATE INDEX IF NOT EXISTS idx_users_deleted_at ON users(deleted_at);


CREATE TABLE IF NOT EXISTS roles (
    id BIGINT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    slug VARCHAR(150) NOT NULL UNIQUE,
    description VARCHAR(255),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


CREATE TABLE IF NOT EXISTS user_roles (
    id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE ON UPDATE CASCADE,
    role_id BIGINT NOT NULL REFERENCES roles(id) ON DELETE CASCADE ON UPDATE CASCADE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, role_id)
);
CREATE INDEX IF NOT EXISTS idx_user_roles_user_id ON user_roles(user_id);
CREATE INDEX IF NOT EXISTS idx_user_roles_role_id ON user_roles(role_id);


CREATE TABLE IF NOT EXISTS notes (
    id BIGINT PRIMARY KEY,
    owner_id BIGINT NOT NULL REFERENCES users(id) ON UPDATE CASCADE ON DELETE CASCADE,
    title VARCHAR(100) NOT NULL,
    content VARCHAR(50000) NOT NULL,
    locked BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_notes_owner_id ON notes(owner_id);
CREATE INDEX IF NOT EXISTS idx_notes_deleted_at ON notes(deleted_at);
-- This can be wrong, but in most real world notes taking apps
-- most of the notes will be unlocked, and hence its okay to
-- bet on the fact that the distribution of the locked boolean
-- will be skewed towards "FALSE".
CREATE INDEX IF NOT EXISTS idx_notes_locked ON notes(locked);


CREATE TABLE IF NOT EXISTS refresh_tokens (
    id BIGINT NOT NULL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE ON UPDATE CASCADE,
    token_prefix VARCHAR(24) NOT NULL, -- should be anywhere between 16-24, depending upon scale
    hashed_token TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (user_id, hashed_token)
);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_token_prefix ON refresh_tokens(token_prefix);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_expires_at ON refresh_tokens(expires_at);
-- Reason for indexing revoked is the same as for users.disabled.
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_revoked ON refresh_tokens(revoked);


CREATE TABLE IF NOT EXISTS active_access_tokens (
    id BIGINT NOT NULL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE ON UPDATE CASCADE,
    jti VARCHAR(50) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    UNIQUE (user_id, jti)
);
CREATE INDEX IF NOT EXISTS idx_active_access_tokens_user_id ON active_access_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_active_access_tokens_expires_at ON active_access_tokens(expires_at);
