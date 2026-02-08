# Build stage
FROM rust:slim AS builder
RUN cargo install agate

# Final stage
FROM debian:bookworm-slim
COPY --from=builder /usr/local/cargo/bin/agate /usr/local/bin/agate
WORKDIR /app
COPY content/ ./content/
# Create a directory for certificates
RUN mkdir certs
VOLUME ["/app/certs"]

# Expose Gemini port
EXPOSE 1965

# Start agate using the entrypoint script
COPY entrypoint.sh /app/entrypoint.sh
ENTRYPOINT ["/app/entrypoint.sh"]
