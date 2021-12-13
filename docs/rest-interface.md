
# OpenNSA rest interface

The rest interface is an easy to use alternative interface to the NSI SOAP api.

## URL design

```
List connections (filter)       GET     /connections
Create new connection           POST    /connections
Get connection information      GET     /connections/{connection_id}
Get connection status (stream)  GET     /connections/{connection_id}/status
Change status                   POST    /connections/{connection_id}/status
```

The /status GET is a stream that updates continously (server won't close connection and will emit new status each time it updates).

## Enabling rest

In [service] section add `rest=true`

## Usage

### Create a connection

Example minimal json payload to create connection:

```json
{
  "source"        : "nordu.net:topology:s1",
  "destination"   : "surfnet.nl:topology:ps",
}
```

Additional fields:

- `start_time` in iso8601 format
- `end_time` in iso8601 format
- `capacity` - bandwidth (megabits)
- `auto_commit` - Used to enable auto commit of reservation request. Defaults `true`.
- `auto_provision` - Used to auto provision the link after the reservation is done. Default `false`.

Date format is ISO8601, e.g., "2015-12-13T08:08:08Z"

Create a connection using curl:

```
curl -i -X POST -d '{"source": "TestNetwork:topology:port1?vlan=1781", "destination": "TestNetwork:topology:port2?vlan=1782"}' http://localhost:9080/connections
```

You will get a location header back that contains the connection id.

### Provision a reserved connection

```
curl -X POST -d "PROVISION" http://localhost:9080/connections/TE-03b16eea46/status
```

It will return an ACK, and start working on provisioning the link.
The link will be up and ready to use when the `provision_state` is `Provisioned` and `data_plane_active` is `true`.

### Terminating a connection

```
curl -X POST -d "TERMINATE" http://localhost:9080/connections/TE-03b16eea46/status
```

The connection will then go into `lifecycle_state` `Terminating`, and when everything is released it will end up in `lifecycle_state` `Terminated`.

### Other supported status operations

- `COMMIT` confirms the reserve commit (used if you set `auto_commit` to `false`).
- `ABORT` aborts the reservation.
- `RELEASE` used to release a provisioned connection, and return to it just being reserved.
- `PROVISION` described above
- `TERMINATE` described above

## Other features

No:

- nsa identity (b0rked concept anyway)
- global reservation id
- Possibility to designate connection id
- Time zones in datetime, always utc (end with Z)

### Todo

Maybe:

- client correlation id
