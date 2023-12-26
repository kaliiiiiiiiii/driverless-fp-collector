Run server:

1. Start a mongodb server locally
2. `python3 server.py`

- more than 30 entries in the last hour on a IP will make you ignored and add a flag-point
- more than 10 flag-points will get your IP flagged permanently

# DataBase endpoints:
`/api/v1/paths?collection=windows`
valid collections are:
```json
[
"a_paths","bots","windows",
 "linux","ios","android","mac","other"
]
```


## Todos
- [x] add path endpoints for each platform
- [ ] add similarity endpoint 