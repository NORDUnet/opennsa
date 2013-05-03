-- OpenNSA SQL Schema (PostgreSQL)
-- consider some generic key-value thing for future usage
-- ALL timestamps must be in utc

CREATE TYPE label AS (
    label_type      text,
    label_value     text
);


-- publically reachable connections
CREATE TABLE service_connections (
    id                      serial                      PRIMARY KEY,
    connection_id           text                        NOT NULL UNIQUE,
    revision                integer                     NOT NULL,
    global_reservation_id   text,
    description             text,
    nsa                     text                        NOT NULL,
    reserve_time            timestamp                   NOT NULL,
    reservation_state       text                        NOT NULL,
    provision_state         text                        NOT NULL,
    activation_state        text                        NOT NULL,
    lifecycle_state         text                        NOT NULL,
    source_network          text                        NOT NULL,
    source_port             text                        NOT NULL,
    source_labels           label[],
    dest_network            text                        NOT NULL,
    dest_port               text                        NOT NULL,
    dest_labels             label[],
    start_time              timestamp                   NOT NULL,
    end_time                timestamp                   NOT NULL,
    bandwidth               integer                     NOT NULL -- mbps
);

-- internal references to connections that are part of a service connection
CREATE TABLE subconnections (
    id                      serial                      PRIMARY KEY,
    service_connection_id   integer                     NOT NULL REFERENCES service_connections(id),
    connection_id           text                        NOT NULL,
    provider_nsa            text                        NOT NULL,
    local_link              boolean                     NOT NULL,
    revision                integer                     NOT NULL,
    order_id                integer                     NOT NULL,
    source_network          text                        NOT NULL,
    source_port             text                        NOT NULL,
    source_labels           label[],
    dest_network            text                        NOT NULL,
    dest_port               text                        NOT NULL,
    dest_labels             label[],
    UNIQUE (provider_nsa, connection_id)
);


-- move this into the backend sometime
CREATE TABLE simplebackendconnections (
    id                      serial                      PRIMARY KEY,
    connection_id           text                        NOT NULL UNIQUE,
    revision                integer                     NOT NULL,
    global_reservation_id   text,
    description             text,
    nsa                     text                        NOT NULL,
    reserve_time            timestamp                   NOT NULL,
    reservation_state       text                        NOT NULL,
    provision_state         text                        NOT NULL,
    activation_state        text                        NOT NULL,
    lifecycle_state         text                        NOT NULL,
    source_network          text                        NOT NULL,
    source_port             text                        NOT NULL,
    source_labels           label[],
    dest_network            text                        NOT NULL,
    dest_port               text                        NOT NULL,
    dest_labels             label[],
    start_time              timestamp                   NOT NULL,
    end_time                timestamp                   NOT NULL,
    bandwidth               integer                     NOT NULL -- mbps
);

