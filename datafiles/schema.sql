-- OpenNSA SQL Schema (PostgreSQL)
-- consider some generic key-value thing for future usage

CREATE TYPE label AS (
    label_type      text,
    label_value     text
);


CREATE TABLE connections (
    id                      serial                      PRIMARY KEY,
    connection_id           text                        NOT NULL UNIQUE,
    revision                integer                     NOT NULL,
    global_reservation_id   text,
    description             text,
    nsa                     text                        NOT NULL,
    reservation_state       text                        NOT NULL,
    provision_state         text                        NOT NULL,
    activation_state        text                        NOT NULL,
    source_network          text                        NOT NULL,
    source_port             text                        NOT NULL,
    source_labels           label[],
    dest_network            text                        NOT NULL,
    dest_port               text                        NOT NULL,
    dest_labels             label[],
    start_time              timestamp with time zone    NOT NULL,
    end_time                timestamp with time zone    NOT NULL,
    bandwidth               integer                     NOT NULL -- mbps
);


CREATE TABLE subconnections (
    id                      serial                      PRIMARY KEY,
    provider_nsa            text                        NOT NULL,
    connection_id           integer                     NOT NULL ,
    revision                integer                     NOT NULL,
    parent_connection_id    integer                     NOT NULL REFERENCES connections(id),
    source_network          text                        NOT NULL,
    source_port             text                        NOT NULL,
    source_labels           label[],
    dest_network            text                        NOT NULL,
    dest_port               text                        NOT NULL,
    dest_labels             label[],
    UNIQUE (provider_nsa, connection_id)
);

