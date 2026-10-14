# Laboratory transport protocol v1

FPGA UART is 115200 baud, 8N1, 3.3 V TTL logic. Send one request and wait for its complete reply. Request inter-byte timeout is approximately 10 ms; MCU reply timeout is 250 ms.

Request (13 bytes): **A5 5A**, one-byte sequence, one-byte command, eight challenge bytes most significant first, CRC-8 over sequence/command/challenge (10 bytes).

Commands: 00 PING; 01 EVALUATE; 02 LOOP. A sequence is only a transport correlation value, not a cryptographic nonce.

Reply (6 bytes): **5A A5**, echoed sequence, status, payload, CRC-8 over sequence/status/payload (3 bytes).

Statuses: 00 successful PING/EVALUATE; 10 PING in communication-only build; 20 LOOP; E1 request CRC failure; E2 unknown command; E3 EVALUATE disabled. PING payload is 40 hex (64 stages); EVALUATE is 00 or 01; LOOP is the challenge's low byte. LOOP results are never enrolled as PUF responses.

CRC-8: polynomial 07, initial 00, no reflection, no final XOR. ASCII 123456789 has check value F4. CRC detects corruption and is not authentication.

Laptop USB messages are ASCII newline-terminated commands: PING; LOOP + 16 hex digits; READ + 16 hex digits + an odd repetition count 1–31; VERDICT + 0 or 1. Replies begin OK; errors begin ERR. No startup banners appear on the protocol. READ returns all raw bits; voting and the identity decision occur on the laptop. USB and UART are separate peripherals on the ESP32-C3.
