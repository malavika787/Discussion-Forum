# Discussion-Forum
UDP client-server discussion forum for concurrent multi-client chatting


This is a command-line based discussion forum application built using **Python**. The server communicates with clients via **UDP**, while file transfers (uploads/downloads) are handled using **TCP**. The system supports **concurrent client connections**, thread-safe operations, and a dispatcher that routes commands from multiple clients to appropriate handlers.

## Features

- User authentication (via `credentials.txt`)
- Thread creation and listing
- Post messages in threads
- Edit and delete messages
- Upload and download files using TCP
- Concurrent clients using dispatcher thread and per-client queues
- Thread-safe operations with locks
