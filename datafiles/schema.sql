-- OpenNSA SQL Schema (PostgreSQL)
-- consider some generic key-value thing for future usage
-- ALL timestamps must be in utc

CREATE TYPE label AS (
    label_type      text,
    label_value     text
);

CREATE TYPE parameter AS (
    label_type      text,
    label_value     text
);

CREATE TYPE security_attribute AS (
    attribute_type  text,
    atribute_value  text
);

CREATE TYPE directionality AS ENUM ('Bidirectional', 'Unidirectional');


-- publically reachable connections
CREATE TABLE service_connections (
    id                      serial                      PRIMARY KEY,
    connection_id           text                        NOT NULL UNIQUE,
    revision                integer                     NOT NULL,
    global_reservation_id   text,
    description             text,
    requester_nsa           text                        NOT NULL,
    requester_url           text,
    reserve_time            timestamp                   NOT NULL,
    reservation_state       text                        NOT NULL,
    provision_state         text                        NOT NULL,
    lifecycle_state         text                        NOT NULL,
    source_network          text                        NOT NULL,
    source_port             text                        NOT NULL,
    source_label            label,
    dest_network            text                        NOT NULL,
    dest_port               text                        NOT NULL,
    dest_label              label,
    start_time              timestamp,                            -- null = immediate start
    end_time                timestamp,                            -- null = forever
    symmetrical             boolean                     NOT NULL,
    directionality          directionality              NOT NULL,
    bandwidth               integer                     NOT NULL, -- mbps
    parameter               parameter[],
    security_attributes     security_attribute[],
    connection_trace        text[],
    CHECK ( start_time < end_time)
);

-- internal references to connections that are part of a service connection
CREATE TABLE sub_connections (
    id                      serial                      PRIMARY KEY,
    service_connection_id   integer                     NOT NULL REFERENCES service_connections(id),
    connection_id           text                        NOT NULL,
    provider_nsa            text                        NOT NULL,
    revision                integer                     NOT NULL,
    order_id                integer                     NOT NULL,
    reservation_state       text                        NOT NULL,
    provision_state         text                        NOT NULL,
    lifecycle_state         text                        NOT NULL,
    data_plane_active       boolean                     NOT NULL,
    data_plane_version      int,
    data_plane_consistent   boolean,
    source_network          text                        NOT NULL,
    source_port             text                        NOT NULL,
    source_label            label,
    dest_network            text                        NOT NULL,
    dest_port               text                        NOT NULL,
    dest_label              label,
    UNIQUE (provider_nsa, connection_id)
);


-- move this into the backend sometime
CREATE TABLE generic_backend_connections (
    id                      serial                      PRIMARY KEY,
    connection_id           text                        NOT NULL UNIQUE,
    revision                integer                     NOT NULL,
    global_reservation_id   text,
    description             text,
    requester_nsa           text                        NOT NULL,
    reserve_time            timestamp                   NOT NULL,
    reservation_state       text                        NOT NULL,
    provision_state         text                        NOT NULL,
    lifecycle_state         text                        NOT NULL,
    data_plane_active       boolean                     NOT NULL,
    source_network          text                        NOT NULL,
    source_port             text                        NOT NULL,
    source_label            label,
    dest_network            text                        NOT NULL,
    dest_port               text                        NOT NULL,
    dest_label              label,
    start_time              timestamp,                            -- null = immediate start
    end_time                timestamp,                            -- null = forever
    symmetrical             boolean                     NOT NULL,
    directionality          directionality              NOT NULL,
    bandwidth               integer                     NOT NULL, -- mbps
    parameter               parameter[],
    allocated               boolean                     NOT NULL, -- indicated if the resources are actually allocated
    CHECK ( start_time < end_time)
);


-- Force this to only have a single row
-- generate new id with:
-- there needs to be a conflict check to see if the backend has a row (and insert corrosonding start value)
-- INSERT INTO backend_connection_id (connection_id) VALUES (190000)  ON CONFLICT DO NOTHING;
-- Generate new id with:
-- UPDATE backend_connection_id SET connection_id = connection_id + 1 RETURNING connection_id;
CREATE TABLE backend_connection_id (
    id                      integer                     PRIMARY KEY NOT NULL DEFAULT(1) CHECK (id = 1),
    connection_id           serial                      NOT NULL
);

