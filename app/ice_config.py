def merge_ice_servers(local, remote):
    servers = []
    seen = set()
    for server in [*remote, *local]:
        if not isinstance(server, dict):
            continue
        urls = server.get("urls", [])
        urls = [urls] if isinstance(urls, str) else urls
        if not isinstance(urls, list):
            continue
        key = (tuple(urls), server.get("username", ""), server.get("credential", ""))
        if key not in seen:
            seen.add(key)
            servers.append(server)
    return servers
