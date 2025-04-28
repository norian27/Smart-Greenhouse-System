import uio
import ssl

# Remove references to `create_default_context`
def wrap_socket(sock, keyfile=None, certfile=None, ca_certs=None, server_hostname=None, **kw):
    """
    Wrap a socket with SSL/TLS.
    Args:
        sock: Socket to wrap.
        keyfile: Private key file.
        certfile: Certificate file.
        ca_certs: CA certificate file.
        server_hostname: Server hostname for SNI.
    Returns:
        SSL-wrapped socket.
    """
    kw['keyfile'] = keyfile
    kw['certfile'] = certfile
    kw['ca_certs'] = ca_certs
    kw['server_hostname'] = server_hostname
    return ssl.wrap_socket(sock,server_hostname = server_hostname)
